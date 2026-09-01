from typing import List


class RagSettings:
    def __init__(
        self,
        root_folder: str,
        extensions: List[str],
        embedding_model_path: str,
        chat_model_path: str,
    ) -> None:
        self.root_folder = str(root_folder)
        self.extensions = [str(extension) for extension in extensions]
        self.embedding_model_path = str(embedding_model_path)
        self.chat_model_path = str(chat_model_path)
