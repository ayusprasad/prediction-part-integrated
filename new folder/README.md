# Prediction Part Integrated

Integrated billing prediction and Port Land RAG chatbot project.

## Project areas

- `Sujit/` — FastAPI RAG chatbot, billing API, PostgreSQL integration, and chatbot UI.
- `new predictionm/frontend/` — standalone billing prediction interface and model artifacts.

## Run the chatbot locally

```powershell
cd Sujit
.venv\Scripts\Activate.ps1
python -m uvicorn app.api_server:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

The local `.env` file is intentionally excluded from Git. Copy `.env.example` and provide local database credentials when setting up another machine.
