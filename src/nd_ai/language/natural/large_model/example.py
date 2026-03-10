from llama_cpp import Llama

llm = Llama(
    model_path="/llama/qwen2.5-3b-instruct-q4_k_m.gguf",
    chat_format="qwen",  # <= این را اصلاح کن
    n_ctx=4096,
    temperature=0.2,
    top_p=0.9,
    repeat_penalty=1.1,
    n_threads=0,  # 0 یعنی auto بر اساس CPU
)

messages = [
    {"role": "system", "content":
        "You rewrite or translate any user text into three outputs in this exact order and format:\n[EN]\n...\n[FA]\n...\n[DE]\n...\nNo explanations."},
    {"role": "user", "content": "دوباره می‌خوام بگم من در گراتس زندگی می‌کنم."}
]

out = llm.create_chat_completion(messages=messages)
print(out["choices"][0]["message"]["content"])
