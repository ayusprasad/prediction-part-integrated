import json
import os
import re


class RouterService:
    def __init__(self, model_name=None):
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        self.llm = None
        try:
            from langchain_community.llms import Ollama
            self.llm = Ollama(model=self.model_name)
        except Exception:
            pass

    def route_query(self, question: str) -> dict:
        if self.llm is not None:
            try:
                prompt = f'''Return JSON only with route DOCUMENT, DATABASE, or MULTI_HOP and table.
DOCUMENT means policy/manual text. DATABASE means structured records. MULTI_HOP means both.
Question: {question}'''
                raw = self.llm.invoke(prompt).strip().strip("`")
                data = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
                route = str(data.get("route", "DOCUMENT")).upper()
                return {"route": "MULTI_HOP" if "MULTI" in route else "DATABASE" if "DATABASE" in route else "DOCUMENT", "table": data.get("table")}
            except Exception:
                pass
        lowered = question.lower()
        database_terms = r"\b(customer|tenant|bill|billing|rent|amount|plot|zone|reservation|ledger|tax|property|database|record|rr\s*no)\b"
        document_terms = r"\b(policy|guideline|manual|circular|board note|agreement|clause|procedure|document)\b"
        has_db = bool(re.search(database_terms, lowered))
        has_doc = bool(re.search(document_terms, lowered))
        table = "plot" if "plot" in lowered else "tgeneralbill" if any(word in lowered for word in ("bill", "billing", "rent", "tax")) else None
        return {"route": "MULTI_HOP" if has_db and has_doc else "DATABASE" if has_db else "DOCUMENT", "table": table}
