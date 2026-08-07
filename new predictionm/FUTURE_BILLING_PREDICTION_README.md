# Future Billing Prediction Module

Copy `future_billing_prediction.py` into any Python chatbot project. It has no
required third-party packages and works when the LLM, PostgreSQL, PGVector, or
internet connection is unavailable.

## Add it before the existing RAG/SQL chain

```python
from future_billing_prediction import predict_from_chat_query


def chatbot(user_text: str):
    prediction_answer = predict_from_chat_query(
        user_text,
        data_source=my_billing_context_adapter,  # optional
        llm_extractor=my_json_llm_function,      # optional
        default_baseline_amount=10_000,
    )
    if prediction_answer is not None:
        return prediction_answer

    return existing_rag_or_sql_pipeline(user_text)
```

## Optional database/vector adapter

```python
class BillingContextAdapter:
    def get_baseline(self, request):
        # Query PostgreSQL for the latest amount and history, or use PGVector.
        return {"amount": 14000, "historical_amounts": [12000, 13000, 14000]}

    def get_rules(self, request):
        # Return decimal rates, or percentages such as 6 for 6%.
        return {
            "annual_growth_rate": 0.06,
            "cgst_rate": 0.09,
            "sgst_rate": 0.09,
            "additional_taxes": {"municipal cess": 0.01},
        }
```

## Included classes

- `PredictionRouter` routes future billing prompts away from normal RAG/SQL.
- `QueryExpander` extracts target date, bill type, amount, location, and property type. It uses an optional LLM first and deterministic regex fallback second.
- `PredictionEngine` retrieves optional context, applies compound growth, billing periods, GST, and additional taxes, and records fallback reasons.
- `ExplainablePredictor` formats the direct answer and step-by-step calculation.

If retrieval fails or returns incomplete data, the module continues with the
configured baseline and bill-type growth default. It never turns missing vector
or SQL context into a hard prediction failure.

Run a local smoke test with:

```bash
python future_billing_prediction.py
```
