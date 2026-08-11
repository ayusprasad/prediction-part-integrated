# Port Land Lease MMS

An internal Port Land Lease Management System that combines document RAG, PostgreSQL-backed billing forecasts, and a source-backed Tender Publication Workflow.

The runnable application is in [`Sujit/`](Sujit/). It provides a FastAPI backend and a browser-based interface at `http://127.0.0.1:8000`.

## What the application does

- Answers questions over uploaded/local documents and configured PostgreSQL/pgvector data.
- Creates a billing forecast from an exported XGBoost model, present-bill inputs, applicable tax rates, and the documented tax formulas.
- Auto-fills billing inputs by tenancy ID only when the required public-data sources contain a value.
- Guides the Tender Publication process from eligible vacant-plot selection through LAC evidence, Board Note, tender drafting, and PDF download.
- Produces formatted PDF versions of LAC, Board Note, and Tender/RFP drafts.

## Main workflows

### Billing Forecast

1. Select a tenancy ID.
2. The application loads available billing history, plot area, frequency, structure type, and applicable formula-tax rates from the configured PostgreSQL/CSV sources.
3. Complete any field that the authoritative source does not provide.
4. Choose the target period and run the forecast.
5. The result is added to the chat with its calculation breakdown and tax lines.

The interface prevents negative numeric inputs. Formula taxes are scheduled by the rules in [`Sujit/config/billing_rules.json`](Sujit/config/billing_rules.json); a zero formula-tax result outside a scheduled month is therefore expected.

Forecasts outside the model validation period are marked as extrapolations. They are calculations, not a guarantee of future billing accuracy.

### Tender Publication Workflow

1. Select an eligible vacant plot and LAC checklist.
2. Enter approved commercial terms: Tender/Nominal, Lease/Licence, optional verified structure area, Annual Rent/Upfront Premium, G-Sec date/rate, and optional service charge.
3. Enter only approved financial inputs that are not present in the verified source records.
4. Calculate the annual rent or discounted upfront premium.
5. Save the LAC draft, continue through workflow stages, and download LAC, Board Note, or Tender/RFP PDFs.

Tender values are deliberately not inferred from a similarly named case. Workbook values are prefilled only when the selected plot identity and recorded area both match the source workbook. This prevents an unrelated rate from being used for a different plot.

## Repository layout

```text
project2/
├── README.md                     # This GitHub overview
├── Sujit/                        # Runnable FastAPI application
│   ├── app/                      # API, services, frontend assets
│   ├── config/                   # Billing and tender workflow rules
│   ├── data/                     # Local runtime data (ignored by Git)
│   ├── data2/                    # Tender source documents, workbook, CSV exports
│   ├── scripts/                  # Data export helpers
│   ├── sql/                      # PostgreSQL and workflow SQL queries
│   ├── requirements.txt
│   ├── .env.example
│   └── start_app.ps1
├── new predictionm/              # XGBoost model and manifest used by billing
└── new folder/                   # Original supplied source documents/workbooks
```

## Prerequisites

- Windows with PowerShell
- Python 3.11 or later
- PostgreSQL with the required `public` billing and property tables
- Access to the source CSV named by `BILLING_TAX_MAPPING_CSV`
- Ollama when using the RAG chat features

The Tender workflow also requires the source documents and workbook under `Sujit/data2/`, including the generated files in `Sujit/data2/tender_exports/`.

## Setup

From the repository root:

```powershell
cd .\Sujit
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` with local, non-secret placeholders replaced by your environment values:

```dotenv
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-local-password
POSTGRES_SCHEMA=rag
BILLING_TAX_MAPPING_CSV=C:/absolute/path/to/applicant_tax_mapping.csv
OLLAMA_MODEL=qwen2.5:7b
```

Do not commit `.env`, database passwords, customer exports, or confidential source documents to a public repository.

### Billing model portability

By default, the billing service looks for the model and manifest in the sibling `new predictionm/frontend/public/` folder. For a different folder structure, set these variables in `.env`:

```dotenv
BILLING_MODEL_PATH=C:/absolute/path/to/billing_xgb_model.json
BILLING_MODEL_MANIFEST_PATH=C:/absolute/path/to/billing_model_manifest.json
BILLING_RULES_PATH=C:/absolute/path/to/billing_rules.json
```

## What must be available on the other computer

The Git repository contains the application code, configuration, SQL files, tender source pack, tender workbook, and the tracked billing model files. The following items are intentionally local or external and must be prepared separately:

| Item | Git status | Action on the other computer |
| --- | --- | --- |
| `Sujit/.env` | Ignored | Create it from `.env.example`; add local PostgreSQL and file paths. |
| `Sujit/.venv/` | Ignored | Create a new virtual environment and install `Sujit/requirements.txt`. |
| PostgreSQL database rows | Not stored in Git | Connect to the same database or restore an approved dump with the required `public` tables and `pgvector` schema. |
| Billing tax-mapping CSV | Not currently tracked | Copy it through a secure channel and set `BILLING_TAX_MAPPING_CSV` to its new absolute path. |
| Ollama model | Not stored in Git | Install Ollama and make the configured model available locally if RAG chat is required. |
| `Sujit/data/` runtime data | Ignored | Recreate it by starting the app and re-ingesting documents; do not copy production sessions or vectors blindly. |
| `Sujit/data2/` and `Sujit/data2/tender_exports/` | Tracked | Keep them with the clone if the supplied tender source pack is approved for that machine. |
| `new predictionm/frontend/public/billing_xgb_model.json` and manifest | Tracked | Keep the sibling folder structure, or set `BILLING_MODEL_PATH` and `BILLING_MODEL_MANIFEST_PATH`. |

Therefore, pushing the repository is necessary but not sufficient by itself for a fully working clone. The second computer also needs Python dependencies, PostgreSQL access/data, the private tax-mapping CSV, and Ollama if the RAG features are used.

## Recommended GitHub handoff

From `C:\Users\kumar\Desktop\project2`:

```powershell
git status
git add README.md Sujit/README.md Sujit/app Sujit/config Sujit/data2 Sujit/requirements.txt Sujit/scripts Sujit/sql Sujit/start_app.ps1 Sujit/start_app.cmd "new predictionm"
git commit -m "Document portable billing and tender workflows"
git push origin main
```

Review `git status` before committing. Do not stage `.env`, `.venv`, `Sujit/data/`, database dumps, passwords, or unapproved confidential documents. If this repository is public, remove or relocate sensitive source documents and customer exports before pushing.

## Run the application

From `Sujit/` with the virtual environment activated:

```powershell
.\start_app.ps1
```

Or run Uvicorn directly:

```powershell
python -m uvicorn app.api_server:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000.

## Tender source-data refresh

The Tender workflow uses the named read-only SQL queries in:

- [`Sujit/sql/tender_workflow/tender_source_export.sql`](Sujit/sql/tender_workflow/tender_source_export.sql)
- [`Sujit/sql/tender_workflow/eligible_vacant_plot_dropdown.sql`](Sujit/sql/tender_workflow/eligible_vacant_plot_dropdown.sql)

To refresh the configured CSV pack from PostgreSQL:

```powershell
cd .\Sujit
.\.venv\Scripts\Activate.ps1
python .\scripts\export_tender_sources.py
```

The exported files are written to `Sujit/data2/tender_exports/`, as configured in [`Sujit/config/tender_export_manifest.json`](Sujit/config/tender_export_manifest.json).

## Key API endpoints

| Purpose | Endpoint |
| --- | --- |
| Health | `GET /api/health` |
| Billing status and rules | `GET /api/billing/status`, `GET /api/billing/rules` |
| Billing tenancy auto-fill | `GET /api/billing/tenancies/{tenancy_id}/prefill` |
| Billing forecast | `POST /api/billing/predict` |
| Tender configuration and plots | `GET /api/tender/config`, `GET /api/tender/plots` |
| Tender calculation | `POST /api/tender/calculate` |
| Tender workflows | `GET/POST /api/tender/workflows` |
| Tender document PDF | `GET /api/tender/workflows/{workflow_id}/documents/{kind}` |

`kind` is one of `lac`, `board-note`, or `tender`.

## Verification performed

The current application was checked for:

- Billing tenancy auto-fill, non-negative field constraints, XGBoost forecast output, and scheduled formula-tax calculations.
- Tender plot loading, commercial setup fields, structure-area branch, annual-rent branch, upfront-premium branch, G-Sec/discount calculation, and service-charge calculation.
- Formatted LAC PDF output, including the Commercial setup section.

## Security and GitHub guidance

- Keep this repository private unless all customer, billing, plot, and tender data has been formally approved for public release.
- Keep `.env` local. Use `.env.example` only for variable names and safe placeholder values.
- Review `data2/` before pushing: it may contain confidential office documents, database exports, and commercial calculations.
- Do not commit generated local runtime files from `Sujit/data/`, virtual environments, or temporary QA output.

## License

No license has been assigned to this repository yet. Treat it as internal project code unless the Port Authority provides an approved license.
