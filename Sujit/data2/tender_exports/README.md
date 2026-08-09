# Tender workflow database export pack

This folder is populated by `scripts/export_tender_sources.py` from the read-only
queries in `sql/tender_workflow/tender_source_export.sql`.

Run from the project directory:

```powershell
.\.venv\Scripts\python.exe .\scripts\export_tender_sources.py
```

The application uses `tender_plot_master.csv` for the eligible-vacant-plot
dropdown and plot-context prefill. The other CSV files are evidence/reference
exports for LAC and tender review.

The public database currently does not establish every approval needed for an
official tender. In particular, do not treat historic tenancy values, FSI,
rates, or approvals in these exports as approvals for a new tender. Enter or
import only the values from the approved case record.
