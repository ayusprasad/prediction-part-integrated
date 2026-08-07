import os


class LLMService:
    def __init__(self):
        self.model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        self.backend = "fallback"
        self.ollama = None
        try:
            import ollama
            available = ollama.list()
            model_names = [item.get("name", item.get("model", "")) for item in available.get("models", [])]
            if any(name == self.model or name.startswith(self.model.split(":")[0] + ":") for name in model_names):
                self.ollama = ollama
                self.backend = "ollama"
            else:
                print(f"[WARN] Ollama is running but {self.model} is not installed; using extractive fallback.")
        except Exception as error:
            print(f"[WARN] Ollama unavailable; using extractive fallback ({error}).")

    @staticmethod
    def _fallback(prompt):
        marker = "Context:\n"
        context = prompt.split(marker, 1)[1] if marker in prompt else prompt
        context = context.strip()
        if not context:
            return "I could not find indexed context for that question."
        return "Based on the available indexed context:\n\n" + context[:1800]

    def generate(self, prompt):
        return "".join(self.generate_stream(prompt))

    def generate_stream(self, prompt):
        if self.ollama is None:
            yield self._fallback(prompt)
            return
        try:
            stream = self.ollama.chat(model=self.model, messages=[{"role": "user", "content": prompt}], stream=True)
            for chunk in stream:
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content
        except Exception as error:
            yield f"The local language model is unavailable. Retrieved context: {error}"
