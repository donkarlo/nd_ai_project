from typing import List
from llama_cpp import Llama


class Chat:
    def __init__(self, model_path: str, n_ctx: int, n_threads: int):
        self._llm = Llama(
            model_path=str(model_path),
            n_ctx=int(n_ctx),
            n_threads=int(n_threads),
            verbose=False
        )

    def answer(self, question: str, context_chunks: List[str], max_tokens: int, temperature: float, top_p: float, repeat_penalty: float) -> str:
        context_text = "\n\n---\n\n".join(context_chunks)

        prompt = (
            "Answer using the provided context.\n"
            "If the exact answer is not explicitly stated, provide the closest relevant information from the context.\n"
            "Be concise.\n\n"
            f"Context:\n{context_text}\n\n"
            f"Question:\n{question}\n\n"
            "Answer:"
        )

        output = self._llm(
            prompt,
            max_tokens=int(max_tokens),
            temperature=float(temperature),
            top_p=float(top_p),
            repeat_penalty=float(repeat_penalty),
            stop=["\n\nQuestion:"]
        )

        return output["choices"][0]["text"].strip()
