from typing import List, Tuple

from nd_ai.knoweldge_representation.language.natural.large_model.rag.config import Config
from nd_ai.knoweldge_representation.language.natural.large_model.rag.crawler import Crawler
from nd_ai.knoweldge_representation.language.natural.large_model.rag.chunker import Chunker
from nd_ai.knoweldge_representation.language.natural.large_model.rag.yaml_naturalizer import YamlNaturalizer
from nd_ai.knoweldge_representation.language.natural.large_model.rag.embedder import Embedder
from nd_ai.knoweldge_representation.language.natural.large_model.rag.index import Index
from nd_ai.knoweldge_representation.language.natural.large_model.rag.chat import Chat


class Rag:
    def __init__(self, cfg: Config):
        self._cfg = cfg
        self._crawler = Crawler(cfg.repo_roots, cfg.allowed_extensions, cfg.ignored_directories)
        self._chunker = Chunker(cfg.chunk_size_chars, cfg.chunk_overlap_chars)
        self._yaml_naturalizer = YamlNaturalizer()
        self._embedder = Embedder(cfg.embedding_model_path, cfg.embedding_n_ctx, cfg.embedding_batch_size)
        self._index = Index(self._embedder, cfg.get_cache_dir_path())
        self._chat = Chat(cfg.chat_model_path, cfg.chat_n_ctx, cfg.n_threads)
        self._cache_dir = cfg.get_cache_dir_path()
        self._index_path = cfg.get_index_path()
        self._chunks_path = cfg.get_chunks_path()

    def build_or_load(self) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        can_reuse = self._index.has_cache(self._index_path, self._chunks_path)
        if can_reuse:
            user_answer = input("Reuse existing FAISS index? [y/N]: ").strip().lower()
            if user_answer == "y":
                self._index.load(self._index_path, self._chunks_path)
                return

        print("Building index (this will compute embeddings)...")
        chunks = self._build_chunks()
        self._index.build(chunks)
        self._index.save(self._index_path, self._chunks_path)
        print(f"Index saved to: {self._cache_dir}")

    def get_reply(self, question: str) -> str:
        expanded_queries = self._expand_question(question)
        hits = self._search_many(expanded_queries, self._cfg.top_k)

        context_chunks: List[str] = []
        for score, ch in hits[: self._cfg.max_context_chunks]:
            source_path = ch.get("source_path", "")
            text = ch.get("tex", "")
            context_chunks.append(f"source_path: {source_path}\n{text}")

        if not context_chunks:
            context_chunks = ["No relevant context found in indexed files."]

        return self._chat.answer(
            question=question,
            context_chunks=context_chunks,
            max_tokens=self._cfg.chat_max_tokens,
            temperature=self._cfg.chat_temperature,
            top_p=self._cfg.chat_top_p,
            repeat_penalty=self._cfg.chat_repeat_penalty
        )

    def _build_chunks(self) -> List[dict]:
        documents = self._crawler.load_documents()
        chunks: List[dict] = []
        for source_path, text in documents:
            lowered = source_path.lower()
            if lowered.endswith(".yaml") or lowered.endswith(".yml"):
                text_for_chunking = self._yaml_naturalizer.naturalize(source_path, text)
            else:
                text_for_chunking = f"source_path: {source_path}\n{text}"

            for chunk_text in self._chunker.chunk(text_for_chunking):
                chunks.append({"tex": chunk_text, "source_path": source_path})
        return chunks

    def _expand_question(self, question: str) -> List[str]:
        q = question.strip()
        queries: List[str] = [q]
        q_lower = q.lower()

        if "embassy" in q_lower and "consulate" not in q_lower:
            queries.append(q + " consulate")
        if "consulate" in q_lower and "embassy" not in q_lower:
            queries.append(q + " embassy")

        if "vienna" in q_lower and "wien" not in q_lower:
            queries.append(q.replace("vienna", "wien"))
        if "wien" in q_lower and "vienna" not in q_lower:
            queries.append(q.replace("wien", "vienna"))

        unique: List[str] = []
        for item in queries:
            if item and item not in unique:
                unique.append(item)
        return unique

    def _search_many(self, queries: List[str], top_k: int) -> List[Tuple[float, dict]]:
        all_hits: List[Tuple[float, dict]] = []
        seen = set()

        for q in queries:
            hits = self._index.search(q, top_k)
            for score, ch in hits:
                key = (ch.get("source_path", ""), ch.get("tex", "")[:80])
                if key in seen:
                    continue
                seen.add(key)
                all_hits.append((score, ch))

        all_hits.sort(key=lambda x: x[0], reverse=True)
        return all_hits
