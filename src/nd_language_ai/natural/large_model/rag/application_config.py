from pathlib import Path


class ApplicationConfig:
    def __init__(self) -> None:
        repo_root = Path(__file__).resolve().parents[6]
        self.settings_path = repo_root / "data" / "nd_language_ai_project" / "rag_settings.yaml"
        self.default_root_folder = repo_root
        self.default_extensions = [".tex", ".pdf"]
        self.default_embedding_model_path = (
            repo_root
            / "data"
            / "nd_gen_ai_project"
            / "language"
            / "natural"
            / "large_model"
            / "nomic-embed-text-v1.5.Q2_K.gguf"
        )
        self.default_chat_model_path = (
            repo_root
            / "data"
            / "nd_gen_ai_project"
            / "language"
            / "natural"
            / "large_model"
            / "Qwen3-4B-Q6_K.gguf"
        )
        self.chunk_size_chars = 1400
        self.chunk_overlap_chars = 250
        self.top_k = 4
        self.max_context_chunks = 2
        self.retrieval_candidate_count = 8
        self.chat_context_size = 2048
        self.chat_max_tokens = 256
        self.chat_temperature = 0.15
        self.chat_top_p = 0.9
        self.chat_repeat_penalty = 1.08
        self.embedding_context_size = 2048
        self.embedding_batch_size = 4
        self.n_threads = 8
        self.ignored_directories = {
            ".git",
            "__pycache__",
            ".venv",
            "venv",
            "node_modules",
            "build",
            "dist",
            "out",
        }
