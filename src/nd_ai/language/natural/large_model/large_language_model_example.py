from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple, Optional, Set, Dict
import os
import re
import json
import hashlib
import time

os.environ.setdefault("LLAMA_LOG_LEVEL", "ERROR")
os.environ.setdefault("GGML_LOG_LEVEL", "ERROR")

import faiss
import numpy as np
import yaml
from llama_cpp import Llama


# -----------------------------
# Domain objects
# -----------------------------
@dataclass(frozen=True)
class Chunk:
    doc_path: str
    chunk_id: int
    text: str


@dataclass(frozen=True)
class RetrievalHit:
    score: float
    chunk: Chunk


# -----------------------------
# Runtime trainer_config (NO CLI)
# -----------------------------
@dataclass(frozen=True)
class RuntimeConfig:
    root: Path
    instructions_yaml: Path
    embed_model_gguf: Path
    chat_model_gguf: Path

    extensions: Tuple[str, ...] = (".schema.yaml", ".yml", ".builder", ".md", ".txt")
    max_files: int = 5000
    include_roots: Optional[List[Path]] = None

    cache_dir: Optional[Path] = None

    max_chunks_total: int = 12000
    chunk_size_chars: int = 1500
    chunk_overlap_chars: int = 150

    embed_n_ctx: int = 2048
    chat_n_ctx: int = 2048
    n_threads: int = 4
    embed_n_batch: int = 64
    chat_n_batch: int = 32

    embed_batch_size: int = 8
    embed_token_margin: int = 64


# -----------------------------
# Policy + instructions
# -----------------------------
class AnswerPolicy:
    def __init__(
            self,
            vector_min_score: float = 0.22,
            keyword_min_score: float = 0.6,
            allow_general_fallback: bool = True,
            show_sources: bool = True,
            max_sources: int = 6,
    ):
        self._vector_min_score = float(vector_min_score)
        self._keyword_min_score = float(keyword_min_score)
        self._allow_general_fallback = bool(allow_general_fallback)
        self._show_sources = bool(show_sources)
        self._max_sources = int(max_sources)

    def should_answer_with_context(self, vec_hits: List[RetrievalHit], kw_hits: List[RetrievalHit]) -> bool:
        if not vec_hits and not kw_hits:
            return False
        best_vec = vec_hits[0].score if vec_hits else None
        best_kw = kw_hits[0].score if kw_hits else None
        vec_ok = (best_vec is not None) and (best_vec >= self._vector_min_score)
        kw_ok = (best_kw is not None) and (best_kw >= self._keyword_min_score)
        return bool(vec_ok or kw_ok)

    def allow_general_fallback(self) -> bool:
        return self._allow_general_fallback

    def show_sources(self) -> bool:
        return self._show_sources

    def max_sources(self) -> int:
        return self._max_sources


class Instructions:
    def __init__(self, path: Path):
        self._path = path
        self._data: Dict[str, object] = {}
        self.reload()

    def reload(self) -> None:
        try:
            raw = self._path.read_text(encoding="utf-8", errors="ignore")
            data = yaml.safe_load(raw)
            self._data = data if isinstance(data, dict) else {}
        except Exception:
            self._data = {}

    def system_prompt(self) -> str:
        sp = self._data.get("system_prompt")
        if isinstance(sp, str) and sp.strip():
            return sp.strip()
        return (
            "Use CONTEXT if it helps. If CONTEXT is irrelevant or weak, answer directly. "
            "Be concise and actionable."
        )

    def general_system_prompt(self) -> str:
        gsp = self._data.get("general_system_prompt")
        if isinstance(gsp, str) and gsp.strip():
            return gsp.strip()
        return "Answer concisely and actionably."


# -----------------------------
# File scanning
# -----------------------------
class FileScanner:
    def __init__(
            self,
            root: Path,
            extensions: Tuple[str, ...],
            exclude_dirs: Optional[Set[str]] = None,
            include_roots: Optional[List[Path]] = None,
            max_files: int = 500,
    ):
        self._root = root
        self._extensions = tuple(e.lower() for e in extensions)
        self._exclude_dirs = set(exclude_dirs) if exclude_dirs else {
            ".git", ".rag_cache", "__pycache__", ".venv", "venv",
            "node_modules", "builder", "dist", "out", ".idea", ".pytest_cache",
        }
        self._include_roots = include_roots
        self._max_files = int(max_files)

    def iter_files(self) -> Iterable[Path]:
        roots: List[Path] = []
        if not self._include_roots:
            roots.append(self._root)
        else:
            for r in self._include_roots:
                roots.append(r if r.is_absolute() else (self._root / r))

        seen = 0
        for base in roots:
            if not base.exists():
                continue

            for dirpath, dirnames, filenames in os.walk(str(base), followlinks=False):
                dirnames[:] = [d for d in dirnames if d not in self._exclude_dirs]
                dirnames.sort()
                filenames.sort()

                for fn in filenames:
                    if seen >= self._max_files:
                        return
                    p = Path(dirpath) / fn
                    if p.suffix.lower() not in self._extensions:
                        continue
                    yield p
                    seen += 1


# -----------------------------
# Document loading
# -----------------------------
class DocumentLoader:
    def __init__(self, max_chars_per_file: int = 250_000):
        self._max_chars_per_file = int(max_chars_per_file)

    def load_text(self, path: Path) -> str:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if len(raw) > self._max_chars_per_file:
            raw = raw[: self._max_chars_per_file]
        if path.suffix.lower() in (".schema.yaml", ".yml"):
            return self._load_yaml_as_pretty_text(raw)
        return raw

    def _load_yaml_as_pretty_text(self, raw: str) -> str:
        try:
            data = yaml.safe_load(raw)
        except Exception:
            return raw
        try:
            return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
        except Exception:
            return raw


# -----------------------------
# LinearAlgebra header injection
# -----------------------------
class DocumentNameHeaderBuilder:
    def __init__(self, root: Path):
        self._root = root

    def build_header(self, path: Path) -> str:
        rel = self._safe_relative(path).as_posix()
        stem = path.stem
        tokens = " ".join(self._tokenize_path(rel))
        lines = [f"__DOC_PATH__ {rel}", f"__DOC_STEM__ {stem}"]
        if tokens:
            lines.append(f"__DOC_TOKENS__ {tokens}")
        return "\n".join(lines) + "\n\n"

    def _safe_relative(self, path: Path) -> Path:
        try:
            return path.relative_to(self._root)
        except Exception:
            return path

    def _tokenize_path(self, rel_posix: str) -> List[str]:
        parts = re.split(r"[\/\._\-]+", rel_posix)
        return [p.lower() for p in parts if p]


# -----------------------------
# Chunking
# -----------------------------
class Chunker:
    def __init__(self, chunk_size_chars: int = 1500, overlap_chars: int = 150, max_chunks_total: int = 5000):
        self._chunk_size = int(chunk_size_chars)
        self._overlap = int(overlap_chars)
        self._max_chunks_total = int(max_chunks_total)

    def chunk_all(self, docs: List[Tuple[str, str]]) -> List[Chunk]:
        chunks: List[Chunk] = []
        for doc_path, text in docs:
            for ch in self.chunk(doc_path, text):
                chunks.append(ch)
                if len(chunks) >= self._max_chunks_total:
                    return chunks
        return chunks

    def chunk(self, doc_path: str, text: str) -> List[Chunk]:
        s = self._normalize(text)
        if not s.strip():
            return []
        out: List[Chunk] = []
        start = 0
        cid = 0
        n = len(s)
        while start < n:
            end = min(n, start + self._chunk_size)
            part = s[start:end].strip()
            if part:
                out.append(Chunk(doc_path=doc_path, chunk_id=cid, text=part))
                cid += 1
            if end == n:
                break
            start = max(0, end - self._overlap)
        return out

    def _normalize(self, s: str) -> str:
        s = s.replace("\r\n", "\n").replace("\r", "\n")
        s = re.sub(r"\n{3,}", "\n\n", s)
        return s


# -----------------------------
# Fingerprint
# -----------------------------
class RepoFingerprint:
    def __init__(
            self,
            root: Path,
            extensions: Tuple[str, ...],
            exclude_dirs: Set[str],
            include_roots: Optional[List[Path]],
            max_files: int,
    ):
        self._root = root
        self._extensions = tuple(e.lower() for e in extensions)
        self._exclude_dirs = set(exclude_dirs)
        self._include_roots = include_roots
        self._max_files = int(max_files)

    def compute(self) -> str:
        h = hashlib.sha256()
        scanned = 0
        scanner = FileScanner(
            root=self._root,
            extensions=self._extensions,
            exclude_dirs=self._exclude_dirs,
            include_roots=self._include_roots,
            max_files=self._max_files,
        )
        for p in scanner.iter_files():
            if scanned >= self._max_files:
                break
            try:
                st = p.stat()
            except FileNotFoundError:
                continue
            h.update(str(p).encode("utf-8", errors="ignore"))
            h.update(str(int(st.st_mtime)).encode("utf-8"))
            h.update(str(int(st.st_size)).encode("utf-8"))
            scanned += 1
        return h.hexdigest()


# -----------------------------
# Embedding
# -----------------------------
class LlamaEmbedder:
    def __init__(self, embed_llm: Llama, max_input_tokens: int, batch_size: int = 8):
        self._llm = embed_llm
        self._max_input_tokens = int(max_input_tokens)
        self._batch_size = max(1, int(batch_size))

    def embed(self, texts: List[str]) -> np.ndarray:
        safe = [self._truncate_by_tokens(t) for t in texts]
        try:
            mat = self._embed_batched(safe)
        except RuntimeError:
            mat = self._embed_one_by_one(safe)
        if mat.shape[0] != len(safe):
            raise RuntimeError(f"Embedding count mismatch: {mat.shape[0]} vs {len(safe)}")
        faiss.normalize_L2(mat)
        return mat

    def _embed_batched(self, texts: List[str]) -> np.ndarray:
        vecs: List[np.ndarray] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i:i + self._batch_size]
            out = self._llm.create_embedding(input=batch)
            data = out.get("data", [])
            if not isinstance(data, list) or len(data) != len(batch):
                raise RuntimeError("Embedding batch mismatch.")
            try:
                data = sorted(data, key=lambda x: int(x.get("index", 0)))
            except Exception:
                pass
            for item in data:
                vecs.append(np.asarray(item["embedding"], dtype=np.float32))
        return np.vstack(vecs).astype(np.float32)

    def _embed_one_by_one(self, texts: List[str]) -> np.ndarray:
        vecs: List[np.ndarray] = []
        for t in texts:
            out = self._llm.create_embedding(input=t)
            data = out.get("data", [])
            if not isinstance(data, list) or not data:
                raise RuntimeError("Embedding response is empty.")
            vecs.append(np.asarray(data[0]["embedding"], dtype=np.float32))
        return np.vstack(vecs).astype(np.float32)

    def _truncate_by_tokens(self, text: str) -> str:
        if not text:
            return text
        toks = self._llm.tokenize(text.encode("utf-8", errors="ignore"))
        if len(toks) <= self._max_input_tokens:
            return text
        toks = toks[: self._max_input_tokens]
        detok = self._llm.detokenize(toks)
        try:
            return detok.decode("utf-8", errors="ignore")
        except Exception:
            return text


# -----------------------------
# Index
# -----------------------------
class FaissIndex:
    def __init__(self):
        self._index: Optional[faiss.Index] = None
        self._chunks: List[Chunk] = []
        self._dim: Optional[int] = None

    def build(self, embeddings: np.ndarray, chunks: List[Chunk]) -> None:
        if embeddings.ndim != 2:
            raise ValueError("embeddings must be 2D.")
        if len(chunks) != embeddings.shape[0]:
            raise ValueError("chunks/embeddings mismatch.")
        self._dim = int(embeddings.shape[1])
        self._index = faiss.IndexFlatIP(self._dim)
        self._index.add(embeddings.astype(np.float32))
        self._chunks = chunks

    def search(self, query_emb: np.ndarray, k: int) -> List[RetrievalHit]:
        if self._index is None:
            raise RuntimeError("Index not built.")
        if query_emb.ndim == 1:
            query_emb = query_emb[None, :]
        faiss.normalize_L2(query_emb)
        scores, ids = self._index.search(query_emb.astype(np.float32), int(k))
        out: List[RetrievalHit] = []
        for score, idx in zip(scores[0], ids[0]):
            if idx < 0:
                continue
            out.append(RetrievalHit(score=float(score), chunk=self._chunks[int(idx)]))
        return out

    def save(self, index_path: Path, meta_path: Path) -> None:
        if self._index is None:
            raise RuntimeError("Index not built.")
        faiss.write_index(self._index, str(index_path))
        meta = {"dim": self._dim, "chunks": [c.__dict__ for c in self._chunks]}
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    def load(self, index_path: Path, meta_path: Path) -> None:
        self._index = faiss.read_index(str(index_path))
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self._dim = int(meta["dim"])
        self._chunks = [Chunk(**c) for c in meta["chunks"]]

    def chunks(self) -> List[Chunk]:
        return self._chunks


# -----------------------------
# Keyword retrieval
# -----------------------------
class KeywordRetriever:
    def __init__(self, chunks: List[Chunk]):
        self._chunks = chunks

    def search(self, query: str, k: int = 8) -> List[RetrievalHit]:
        q = (query or "").strip().lower()
        if not q:
            return []
        terms = [t for t in re.split(r"\s+", q) if t]

        scored: List[RetrievalHit] = []
        for ch in self._chunks:
            tl = ch.text.lower()
            path_lower = ch.doc_path.lower()
            stem_lower = Path(ch.doc_path).stem.lower()
            haystack = tl + "\n" + path_lower + "\n" + stem_lower

            if q in haystack:
                count = haystack.count(q)
                score = 2.0 + min(1.0, count * 0.1)
                scored.append(RetrievalHit(score=float(score), chunk=ch))
                continue

            if len(terms) == 1:
                t0 = terms[0]
                if t0 in haystack:
                    count = haystack.count(t0)
                    score = 1.0 + min(1.0, count * 0.05)
                    scored.append(RetrievalHit(score=float(score), chunk=ch))
                continue

            hit_count = sum(1 for t in terms if t in haystack)
            if hit_count > 0:
                score = hit_count / max(1, len(terms))
                scored.append(RetrievalHit(score=float(score), chunk=ch))

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[: int(k)]


# -----------------------------
# RAG engine
# -----------------------------
class RagEngine:
    def __init__(self, cfg: RuntimeConfig, policy: AnswerPolicy):
        self._cfg = cfg
        self._policy = policy

        self._exclude_dirs = {
            ".git", ".rag_cache", "__pycache__", ".venv", "venv",
            "node_modules", "builder", "dist", "out", ".idea", ".pytest_cache",
        }

        self._instructions = Instructions(self._cfg.instructions_yaml)

        if not self._cfg.root.exists():
            raise ValueError(f"Root does not exist: {self._cfg.root}")
        if not self._cfg.instructions_yaml.exists():
            raise ValueError(f"Instructions file does not exist: {self._cfg.instructions_yaml}")
        if not self._cfg.embed_model_gguf.exists():
            raise ValueError(f"Embed model does not exist: {self._cfg.embed_model_gguf}")
        if not self._cfg.chat_model_gguf.exists():
            raise ValueError(f"Chat model does not exist: {self._cfg.chat_model_gguf}")

        self._cache_dir = self._cfg.cache_dir or (self._cfg.root / ".rag_cache")
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        self._fp_path = self._cache_dir / "fingerprint.txt"
        self._faiss_path = self._cache_dir / "index.faiss"
        self._meta_path = self._cache_dir / "index.meta.json"

        self._embed_llm = Llama(
            model_path=str(self._cfg.embed_model_gguf),
            n_ctx=int(self._cfg.embed_n_ctx),
            n_threads=int(self._cfg.n_threads),
            n_batch=int(self._cfg.embed_n_batch),
            embedding=True,
            verbose=False,
        )
        self._chat_llm = Llama(
            model_path=str(self._cfg.chat_model_gguf),
            n_ctx=int(self._cfg.chat_n_ctx),
            n_threads=int(self._cfg.n_threads),
            n_batch=int(self._cfg.chat_n_batch),
            embedding=False,
            verbose=False,
        )

        max_input_tokens = max(128, int(self._cfg.embed_n_ctx) - int(self._cfg.embed_token_margin))

        self._scanner = FileScanner(
            root=self._cfg.root,
            extensions=self._cfg.extensions,
            exclude_dirs=self._exclude_dirs,
            include_roots=self._cfg.include_roots,
            max_files=int(self._cfg.max_files),
        )
        self._loader = DocumentLoader()
        self._name_header = DocumentNameHeaderBuilder(root=self._cfg.root)
        self._chunker = Chunker(
            chunk_size_chars=int(self._cfg.chunk_size_chars),
            overlap_chars=int(self._cfg.chunk_overlap_chars),
            max_chunks_total=int(self._cfg.max_chunks_total),
        )
        self._embedder = LlamaEmbedder(
            embed_llm=self._embed_llm,
            max_input_tokens=max_input_tokens,
            batch_size=int(self._cfg.embed_batch_size),
        )
        self._index = FaissIndex()
        self._fingerprint = RepoFingerprint(
            root=self._cfg.root,
            extensions=self._cfg.extensions,
            exclude_dirs=self._exclude_dirs,
            include_roots=self._cfg.include_roots,
            max_files=int(self._cfg.max_files),
        )
        self._kw: Optional[KeywordRetriever] = None

    def print_settings(self) -> None:
        print("RAG terminal is ready. Type a question and press Enter.", flush=True)
        print("Commands: :reload, :exit", flush=True)
        print(f"RAG root = {self._cfg.root}", flush=True)
        print(f"Instructions = {self._cfg.instructions_yaml}", flush=True)
        print(f"Embed model = {self._cfg.embed_model_gguf}", flush=True)
        print(f"Chat model = {self._cfg.chat_model_gguf}", flush=True)
        print(f"Cache dir = {self._cache_dir}", flush=True)
        print(f"Extensions = {self._cfg.extensions}", flush=True)
        print(f"Max files = {self._cfg.max_files}", flush=True)
        if self._cfg.include_roots:
            print(f"Include roots = {[str(p) for p in self._cfg.include_roots]}", flush=True)
        else:
            print("Include roots = (all)", flush=True)

    def _merge_hits(self, vec_hits: List[RetrievalHit], kw_hits: List[RetrievalHit], top_k: int) -> List[RetrievalHit]:
        seen: Set[Tuple[str, int]] = set()
        merged: List[RetrievalHit] = []

        for hit in vec_hits:
            key = (hit.chunk.doc_path, hit.chunk.chunk_id)
            if key in seen:
                continue
            seen.add(key)
            merged.append(hit)

        kw_boost = 0.05
        for hit in kw_hits:
            key = (hit.chunk.doc_path, hit.chunk.chunk_id)
            if key in seen:
                continue
            seen.add(key)
            merged.append(RetrievalHit(score=float(hit.score) + kw_boost, chunk=hit.chunk))

        merged.sort(key=lambda h: h.score, reverse=True)
        return merged[: int(top_k)]

    def ensure_index(self) -> None:
        current_fp = self._fingerprint.compute()
        cached_fp = self._fp_path.read_text(encoding="utf-8").strip() if self._fp_path.exists() else ""

        if self._faiss_path.exists() and self._meta_path.exists() and cached_fp == current_fp:
            self._index.load(self._faiss_path, self._meta_path)
            self._kw = KeywordRetriever(self._index.chunks())
            print("Index loaded from cache.", flush=True)
            return

        self.rebuild_index()
        self._fp_path.write_text(current_fp, encoding="utf-8")

    def rebuild_index(self) -> None:
        print("Building index...", flush=True)

        docs: List[Tuple[str, str]] = []
        paths = list(self._scanner.iter_files())
        print(f"Found {len(paths)} files to index.", flush=True)

        for i, path in enumerate(paths, 1):
            try:
                txt = self._loader.load_text(path)
            except Exception:
                continue

            header = self._name_header.build_header(path)
            docs.append((str(path), header + txt))

            if i % 50 == 0:
                print(f"Loaded {i}/{len(paths)} files...", flush=True)

        chunks = self._chunker.chunk_all(docs)
        print(f"Produced {len(chunks)} chunks.", flush=True)

        if not chunks:
            raise RuntimeError("No chunks produced. Check root/extensions/include_roots/max_files.")

        texts = [c.text for c in chunks]
        print("Embedding chunks...", flush=True)
        emb = self._embedder.embed(texts)
        print("Embedding done.", flush=True)

        self._index.build(embeddings=emb, chunks=chunks)
        self._index.save(self._faiss_path, self._meta_path)
        self._kw = KeywordRetriever(self._index.chunks())
        print("Index built and saved.", flush=True)

    def answer(self, question: str, top_k: int = 10, max_tokens: int = 200) -> str:
        q = (question or "").strip()
        if not q:
            return ""

        if self._kw is None:
            self._kw = KeywordRetriever(self._index.chunks())

        kw_hits = self._kw.search(q, k=max(8, int(top_k)))
        q_emb = self._embedder.embed([q])
        vec_hits = self._index.search(q_emb, k=max(8, int(top_k)))
        merged = self._merge_hits(vec_hits=vec_hits, kw_hits=kw_hits, top_k=int(top_k))

        use_context = self._policy.should_answer_with_context(vec_hits=vec_hits, kw_hits=kw_hits)
        if not use_context:
            if self._policy.allow_general_fallback():
                return self._general_answer(q=q, max_tokens=int(max_tokens))
            return "In indexed files, I cannot find it."

        if len(q.split()) == 1:
            hits = (kw_hits or merged)[: self._policy.max_sources()]
            return self._snippet_answer_from_hits(hits)

        return self._contextual_answer(q=q, hits=merged, max_tokens=int(max_tokens))

    def _snippet_answer_from_hits(self, hits: List[RetrievalHit]) -> str:
        lines: List[str] = []
        for hit in hits:
            ch = hit.chunk
            snippet = ch.text[:800]
            if self._policy.show_sources():
                lines.append(f"[source={ch.doc_path} chunk={ch.chunk_id} score={hit.score:.4f}]\n{snippet}")
            else:
                lines.append(snippet)
        return "\n\n".join(lines)

    def _general_answer(self, q: str, max_tokens: int) -> str:
        messages = [
            {"role": "system", "content": self._instructions.general_system_prompt()},
            {"role": "user", "content": q},
        ]
        out = self._chat_llm.create_chat_completion(
            messages=messages,
            max_tokens=int(max_tokens),
            temperature=0.2,
        )
        return out["choices"][0]["message"]["content"]

    def _contextual_answer(self, q: str, hits: List[RetrievalHit], max_tokens: int) -> str:
        kept = self._fit_context_to_n_ctx(q=q, hits=hits, max_tokens=int(max_tokens), per_chunk_char_limit=600)
        context_lines: List[str] = []
        for hit in kept[: self._policy.max_sources()]:
            ch = hit.chunk
            txt = ch.text[:600]
            if self._policy.show_sources():
                context_lines.append(f"[source={ch.doc_path} chunk={ch.chunk_id} score={hit.score:.4f}]\n{txt}")
            else:
                context_lines.append(txt)
        context = "\n\n".join(context_lines)

        messages = [
            {"role": "system", "content": self._instructions.system_prompt()},
            {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION:\n{q}"},
        ]

        # hard guard
        n_ctx = int(self._chat_llm.n_ctx())
        if self._count_chat_prompt_tokens(messages) + int(max_tokens) > n_ctx:
            if self._policy.allow_general_fallback():
                return self._general_answer(q=q, max_tokens=int(max_tokens))
            return "In indexed files, I cannot fit context into the model window."

        out = self._chat_llm.create_chat_completion(
            messages=messages,
            max_tokens=int(max_tokens),
            temperature=0.2,
        )
        return out["choices"][0]["message"]["content"]

    def _count_chat_prompt_tokens(self, messages: List[dict]) -> int:
        parts: List[str] = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            parts.append(f"{role.upper()}:\n{content}\n")
        prompt = "\n".join(parts)
        toks = self._chat_llm.tokenize(prompt.encode("utf-8", errors="ignore"))
        return len(toks)

    def _fit_context_to_n_ctx(
            self,
            q: str,
            hits: List[RetrievalHit],
            max_tokens: int,
            per_chunk_char_limit: int = 600,
            min_hits: int = 1,
    ) -> List[RetrievalHit]:
        if max_tokens < 1:
            max_tokens = 1
        n_ctx = int(self._chat_llm.n_ctx())

        def build_messages(candidate_hits: List[RetrievalHit], limit: int) -> List[dict]:
            lines: List[str] = []
            for hit in candidate_hits[: self._policy.max_sources()]:
                ch = hit.chunk
                lines.append(f"[source={ch.doc_path} chunk={ch.chunk_id} score={hit.score:.4f}]\n{ch.text[:limit]}")
            ctx = "\n\n".join(lines)
            return [
                {"role": "system", "content": self._instructions.system_prompt()},
                {"role": "user", "content": f"CONTEXT:\n{ctx}\n\nQUESTION:\n{q}"},
            ]

        candidate = hits[:]
        limit = int(per_chunk_char_limit)

        while True:
            msgs = build_messages(candidate, limit)
            prompt_tokens = self._count_chat_prompt_tokens(msgs)

            if prompt_tokens + max_tokens <= n_ctx:
                return candidate[:]

            if limit > 200:
                limit = max(200, int(limit * 0.8))
                continue

            if len(candidate) > min_hits:
                candidate = candidate[:-1]
                continue

            if limit > 80:
                limit = max(80, int(limit * 0.7))
                continue

            return candidate[:]


# -----------------------------
# Terminal app
# -----------------------------
class TerminalApp:
    def __init__(self, rag: RagEngine):
        self._rag = rag

    def run(self) -> None:
        self._rag.print_settings()
        self._rag.ensure_index()
        print("Ready for questions.", flush=True)

        while True:
            try:
                q = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                return

            if not q:
                continue
            if q == ":exit":
                return
            if q == ":reload":
                self._rag._instructions.reload()
                start = time.time()
                self._rag.rebuild_index()
                elapsed = time.time() - start
                print(f"Ready for questions. (reindex: {elapsed:.1f}s)", flush=True)
                continue

            ans = self._rag.answer(q, top_k=12, max_tokens=220)
            print("\n" + ans, flush=True)


# -----------------------------
# AppFactory (OOP)
# -----------------------------
class AppFactory:
    def __init__(self, cfg: RuntimeConfig, policy: AnswerPolicy):
        self._cfg = cfg
        self._policy = policy

    def build(self) -> TerminalApp:
        rag = RagEngine(cfg=self._cfg, policy=self._policy)
        return TerminalApp(rag=rag)


# -----------------------------
# main (NO CLI)
# -----------------------------
def main() -> None:
    cfg = RuntimeConfig(
        root=Path("/home/donkarlo/Dropbox/repo/"),
        instructions_yaml=Path("instructions.yaml"),
        embed_model_gguf=Path(
            "/llama/nomic-embed-text-v1.5.Q2_K.gguf"),
        chat_model_gguf=Path(
            "/llama/qwen2.5-3b-instruct-q4_k_m.gguf"),
        n_threads=min(4, os.cpu_count() or 4),
    )

    policy = AnswerPolicy(
        vector_min_score=0.22,
        keyword_min_score=0.6,
        allow_general_fallback=True,
        show_sources=True,
        max_sources=6,
    )

    app = AppFactory(cfg=cfg, policy=policy).build()
    app.run()


if __name__ == "__main__":
    main()
