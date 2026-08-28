from nd_ai.knoweldge_representation.language.natural.large_model.rag.config import Config
from nd_ai.knoweldge_representation.language.natural.large_model.rag.rag import Rag


class RagTerminalApp:
    def __init__(self):
        repo_roots = [
            "/home/donkarlo/Dropbox/repo/nd_robotic_project/data",
            "/home/donkarlo/Dropbox/repo/nd_me_project/data",
            "/home/donkarlo/Dropbox/repo/nd_deutsch_learning_project/src",
            "/home/donkarlo/Dropbox/repo/nd_python_learning_project/src",
        ]

        embedding_model_path = "/data/language/natural/large_model/nomic-embed-tex-v1.5.Q2_K.gguf"
        chat_model_path = "/data/language/natural/large_model/qwen2.5-3b-instruct-q4_k_m.gguf"

        cache_dir = "/data/language/natural/large_model/chache"

        allowed_extensions = [".yaml", ".yml", ".md", ".txt", ".builder"]
        ignored_directories = [".git", "__pycache__", ".venv", "venv", "node_modules", "builder", "dist", "out"]

        self._rag = Rag(Config(repo_roots, embedding_model_path, chat_model_path, cache_dir, allowed_extensions,
                               ignored_directories))

    def run(self) -> None:
        self._rag.build_or_load()
        print("RAG terminal ready.")
        print("Type your question and press Enter. Type :exit to quit.")
        while True:
            question = input("Question: ").strip()
            if not question:
                continue
            if question == ":exit":
                break
            reply = self._rag.get_reply(question)
            print(reply)


def main():
    RagTerminalApp().run()


if __name__ == "__main__":
    main()
