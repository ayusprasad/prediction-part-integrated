# Port Land Lease MMS

A source-backed application for document search, billing forecasts, and guided tender preparation for port land lease operations.

[![CI](https://github.com/ayusprasad/prediction-part-integrated/actions/workflows/ci.yml/badge.svg)](https://github.com/ayusprasad/prediction-part-integrated/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776ab?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-data-4169e1?logo=postgresql&logoColor=white)
![React](https://img.shields.io/badge/React-frontend-149eca?logo=react&logoColor=white)

## Overview

Port Land Lease MMS brings document retrieval, billing context, and tender preparation into a single workflow. The FastAPI service serves a browser interface, coordinates document and language-model services, reads configured PostgreSQL sources, and generates downloadable working documents.

The billing forecast uses an exported model artifact and explicit calculation rules. Results outside the model's validation range are labeled as extrapolations. Tender values are populated only when the selected record matches the verified source data; missing values remain user-entered.

## Capabilities

- Search and summarize configured source documents with citations.
- Process uploads through an OCR and document-ingestion pipeline.
- Prepare billing forecasts from available records and a versioned model artifact.
- Guide tender preparation through configured workflow stages.
- Generate downloadable LAC, Board Note, and Tender/RFP documents.
- Run in a local development setup without committing secrets or user data.

## Architecture

```text
Sujit/
  app/
    api_server.py              FastAPI application and HTTP routes
    services/                  ingestion, retrieval, billing, and tender services
  config/                      billing and tender workflow rules
  data2/                       reference data and source documents
  scripts/                     import and export utilities
  sql/                         PostgreSQL schema and queries
  .env.example                 local configuration template
new predictionm/frontend/      standalone billing model interface
```

The API and its services are the primary application. Database-backed and local-model features require their configured services; unavailable dependencies return an error state rather than fabricated results.

## Prerequisites

- Python 3.11+
- PostgreSQL for database-backed retrieval and billing features
- Ollama and the configured model for local LLM features
- Node.js 22.13+ and npm for the optional frontend project
- System OCR/PDF tools required by the selected document-processing dependencies

## Run the API locally

From the repository root:

```powershell
cd Sujit
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
.\start_app.ps1
```

The service listens on `http://127.0.0.1:8000`. On macOS/Linux, create and activate the virtual environment with `python3.11 -m venv .venv` and `source .venv/bin/activate`, then start it with `python -m uvicorn app.api_server:app --host 127.0.0.1 --port 8000`.

## Environment configuration

Copy `Sujit/.env.example` to `Sujit/.env`, then set the database connection and any local data paths required by your environment.

| Variable | Purpose |
| --- | --- |
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | PostgreSQL connection |
| `POSTGRES_SCHEMA` | Application schema |
| `BILLING_TAX_MAPPING_CSV` | Optional source file for billing tax mappings |
| `OLLAMA_MODEL` | Local generation model |
| `EMBEDDING_BACKEND` | Select embedding implementation |
| `RAG_USER_ID` | Local application user context |
| `CORS_ALLOW_ORIGINS` | Comma-separated allowed browser origins |

Use placeholder values from the template for local development. Keep real credentials in an untracked `.env` file or deployment secret manager.

## Optional frontend

```bash
cd "new predictionm/frontend"
npm ci
npm run dev
```

Run its checks with `npm run lint`, `node --test tests/rendered-html.test.mjs`, and `npm run build`.

## Quality checks

The GitHub Actions pipeline runs Python linting, isolated backend unit tests, and syntax compilation. It also installs, lints, tests, and builds the standalone frontend on pushes and pull requests.
