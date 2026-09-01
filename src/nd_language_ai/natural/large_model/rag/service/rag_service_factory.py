from pathlib import Path

from nd_language_ai.natural.large_model.rag.application_config import ApplicationConfig
from nd_language_ai.natural.large_model.rag.document.file_crawler import FileCrawler
from nd_language_ai.natural.large_model.rag.model.llama_cpp_language_model import LlamaCppLanguageModel
from nd_language_ai.natural.large_model.rag.retrieval.cached_llama_cpp_embedding_model import (
    CachedLlamaCppEmbeddingModel,
)
from nd_language_ai.natural.large_model.rag.retrieval.chunker import Chunker
from nd_language_ai.natural.large_model.rag.retrieval.timed_persistent_hybrid_index import (
    TimedPersistentHybridIndex,
)
from nd_language_ai.natural.large_model.rag.service.persistent_rag_service import (
    PersistentRagService,
)
from nd_language_ai.natural.large_model.rag.service.rag_service import RagService


class RagServiceFactory:
    def __init__(self, config: ApplicationConfig) -> None:
        self._config = config

    def create(self, embedding_model_path: str, chat_model_path: str) -> RagService:
        embedding_model = CachedLlamaCppEmbeddingModel(
            Path(embedding_model_path).expanduser(),
            self._config.embedding_context_size,
            self._config.embedding_batch_size,
        )
        language_model = LlamaCppLanguageModel(
            Path(chat_model_path).expanduser(),
            self._config.chat_context_size,
            self._config.chat_max_tokens,
            self._config.chat_temperature,
            self._config.chat_top_p,
            self._config.chat_repeat_penalty,
            self._config.n_threads,
        )
        return PersistentRagService(
            FileCrawler(self._config.ignored_directories),
            Chunker(
                self._config.chunk_size_chars,
                self._config.chunk_overlap_chars,
            ),
            TimedPersistentHybridIndex(
                embedding_model,
                self._config.retrieval_candidate_count,
            ),
            language_model,
            self._config.top_k,
            self._config.max_context_chunks,
        )
