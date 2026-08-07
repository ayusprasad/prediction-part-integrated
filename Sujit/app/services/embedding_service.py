"""Embedding service with a model-backed path and deterministic local fallback."""

import hashlib
import math
import os


class EmbeddingService:
    def __init__(self):
        self.dimension = 1024
        self.backend = "hashing-fallback"
        self.use_flag = False
        self.model = None
        if os.getenv("EMBEDDING_BACKEND", "hashing").lower() not in {"model", "bge", "auto"}:
            return
        try:
            from FlagEmbedding import BGEM3FlagModel
            self.model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=False)
            self.use_flag = True
            self.backend = "bge-m3-flag"
        except Exception as flag_error:
            try:
                import torch
                from transformers import AutoModel, AutoTokenizer
                self.tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-m3")
                self.model = AutoModel.from_pretrained("BAAI/bge-m3")
                self.model.eval()
                self.torch = torch
                self.backend = "bge-m3-transformers"
            except Exception as model_error:
                print(f"[WARN] BGE-M3 unavailable; using deterministic local embeddings ({model_error}).")

    @staticmethod
    def _hash_embedding(text: str, dimension: int = 1024):
        values = [0.0] * dimension
        tokens = (text or "").lower().split()
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % dimension
            values[index] += 1.0 if digest[4] % 2 else -1.0
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]

    def _embed_transformers(self, texts):
        inputs = self.tokenizer(texts, padding=True, truncation=True, max_length=1024, return_tensors="pt")
        with self.torch.no_grad():
            outputs = self.model(**inputs)
            embeddings = outputs[0][:, 0]
            embeddings = self.torch.nn.functional.normalize(embeddings, p=2, dim=1)
            return embeddings.cpu().numpy().tolist()

    def embed_text(self, text: str):
        if self.use_flag:
            result = self.model.encode([text], return_dense=True, return_sparse=False, return_colbert_vecs=False)
            return result["dense_vecs"][0].tolist()
        if self.backend == "bge-m3-transformers":
            return self._embed_transformers([text])[0]
        return self._hash_embedding(text, self.dimension)

    def embed_chunks(self, chunks: list[dict], batch_size: int = 16, status_dict: dict = None):
        texts = [chunk.get("text") or chunk.get("child_text") or "" for chunk in chunks]
        if self.use_flag:
            vectors = []
            for start in range(0, len(texts), batch_size):
                result = self.model.encode(texts[start:start + batch_size], return_dense=True, return_sparse=False, return_colbert_vecs=False)
                vectors.extend(result["dense_vecs"].tolist() if hasattr(result["dense_vecs"], "tolist") else result["dense_vecs"])
        elif self.backend == "bge-m3-transformers":
            vectors = self._embed_transformers(texts)
        else:
            vectors = [self._hash_embedding(text, self.dimension) for text in texts]
        for index, (chunk, vector) in enumerate(zip(chunks, vectors), start=1):
            chunk["embedding"] = vector.tolist() if hasattr(vector, "tolist") else vector
            if status_dict is not None:
                status_dict.update({"step": f"Embedding chunks ({index}/{len(chunks)})...", "progress": 70 + int(20 * index / max(1, len(chunks)))})
        return chunks
