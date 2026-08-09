# Project SQL inventory

This directory is the portable SQL source directory for the project. It is safe to commit to Git because it contains no passwords or generated secrets.

## Run order on another laptop

1. Clone the repository and create `Sujit/.env` from `Sujit/.env.example`. Fill in the PostgreSQL password locally; do not commit `.env`.
2. Install PostgreSQL with the `pgvector` extension if the RAG vector store will use PostgreSQL.
3. In DBeaver, run `001_rag_schema.sql` once against the target PostgreSQL database. It creates only the configured `rag` vector schema; it does not modify the `public` business tables.
4. To refresh the tender-workflow CSV pack, run `Sujit/scripts/export_tender_sources.py`. It reads `tender_workflow/tender_source_export.sql` and produces CSV files in `Sujit/data2/tender_exports/`.
5. Start the application. The billing and RAG services execute their parameterised queries themselves; the reference files below document those exact queries.

## Files

| File | Used by | Purpose |
| --- | --- | --- |
| `001_rag_schema.sql` | RAG startup | Creates the PostgreSQL pgvector schema, document tables, and vector indexes. |
| `tender_workflow/eligible_vacant_plot_dropdown.sql` | Tender UI / DBeaver | Returns the eligible vacant-plot dropdown rows. |
| `tender_workflow/tender_source_export.sql` | `scripts/export_tender_sources.py` | Named, read-only export queries that create the tender auto-fill source CSV pack. |
| `billing/billing_runtime_reference.sql` | `billing_prediction_service.py` | Exact PostgreSQL lookup patterns for tenancy/customer mapping, bills, profile, structure, and tax rates. |
| `rag/rag_runtime_reference.sql` | `postgres_service.py` | Parameterised PostgreSQL pgvector insert and retrieval patterns. |
| `sqlite/001_rag_fallback_schema.sql` | `postgres_service.py` fallback | Local SQLite schema used only when pgvector is unavailable. |

## Safety and portability

- All `public`-schema billing and tender queries are read-only `SELECT` queries.
- Application parameters are intentionally shown as `%s` because the Python driver binds them safely. Do not replace them with string concatenation.
- `database_agent.py` has no fixed business SQL file: it generates read-only `SELECT` statements from user questions at runtime. It must remain read-only and is not a source for approved tender values.
- Tender values such as approved FSI, SoR/reserve rate, GST, escalation, tender method, approvals, and signatures are never invented by these queries. They must be provided from authorised records when the source data does not contain them.
