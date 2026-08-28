from pathlib import Path


class Config:
    def __init__(self, repo_roots, embedding_model_path, chat_model_path, cache_dir, allowed_extensions,
                 ignored_directories):
        self.repo_roots = repo_roots

        self.embedding_model_path = embedding_model_path
        self.chat_model_path = chat_model_path

        self.cache_dir = cache_dir

        self.allowed_extensions = allowed_extensions
        self.ignored_directories = ignored_directories

        self.chunk_size_chars = 1000
        self.chunk_overlap_chars = 200

        self.top_k = 8
        self.max_context_chunks = 8

        self.chat_n_ctx = 4096
        self.chat_max_tokens = 256
        self.chat_temperature = 0.2
        self.chat_top_p = 0.95
        self.chat_repeat_penalty = 1.15
        self.n_threads = 8

        self.embedding_n_ctx = 512
        self.embedding_batch_size = 8

    def get_cache_dir_path(self) -> Path:
        return Path(self.cache_dir)

    def get_index_path(self) -> Path:
        return self.get_cache_dir_path() / "faiss.index"

    def get_chunks_path(self) -> Path:
        return self.get_cache_dir_path() / "chunks.jsonl"
