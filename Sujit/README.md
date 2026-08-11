# Application folder

This directory contains the runnable FastAPI application for Port Land Lease MMS.

See the repository-level [README](../README.md) for setup, environment variables, billing forecast behaviour, Tender Publication Workflow, SQL exports, and GitHub guidance.

Quick start from this directory:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
.\start_app.ps1
```

Open http://127.0.0.1:8000 after the server starts.
