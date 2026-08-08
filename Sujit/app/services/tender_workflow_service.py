"""Source-backed Tender Publication workflow service.

This module deliberately keeps commercial and approval values as workflow inputs.
The data exports contain plot context, but they do not provide a complete approved
rate/policy schedule for a publishable tender.
"""

from __future__ import annotations

import csv
import json
import math
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class TenderWorkflowError(ValueError):
    """Raised for invalid workflow requests that the API can return to the UI."""


class TenderWorkflowService:
    def __init__(self) -> None:
        self.project_root = Path(__file__).resolve().parents[2]
        self.data_dir = self.project_root / "data"
        self.data2_dir = self.project_root / "data2"
        self.config_path = self.project_root / "config" / "tender_workflow.json"
        self.storage_path = self.data_dir / "tender_workflows.json"
        self._lock = threading.RLock()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _normalise(value: Any) -> str:
        return str(value or "").strip().casefold()

    @staticmethod
    def _clean_number(value: Any, field_name: str, *, positive: bool = False) -> float:
        if value is None or str(value).strip() == "":
            raise TenderWorkflowError(f"{field_name} is required.")
        try:
            number = float(str(value).replace(",", "").strip())
        except (TypeError, ValueError) as error:
            raise TenderWorkflowError(f"{field_name} must be a valid number.") from error
        if not math.isfinite(number):
            raise TenderWorkflowError(f"{field_name} must be finite.")
        if positive and number <= 0:
            raise TenderWorkflowError(f"{field_name} must be greater than zero.")
        if not positive and number < 0:
            raise TenderWorkflowError(f"{field_name} cannot be negative.")
        return number

    def _config(self) -> dict[str, Any]:
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise TenderWorkflowError("Tender workflow configuration is unavailable.") from error
        except json.JSONDecodeError as error:
            raise TenderWorkflowError("Tender workflow configuration is invalid JSON.") from error

    def _source_path(self, source_key: str) -> Path:
        source_name = self._config()["source_files"].get(source_key)
        if not source_name:
            raise TenderWorkflowError(f"Unknown tender source: {source_key}.")
        path = self.data2_dir / source_name
        if not path.is_file():
            raise TenderWorkflowError(f"Required tender source is unavailable: {source_name}.")
        return path

    def _checklists_by_key(self) -> dict[str, dict[str, Any]]:
        return {item["key"]: item for item in self._config().get("checklists", [])}

    def _actions_by_key(self) -> dict[str, dict[str, Any]]:
        return {item["key"]: item for item in self._config().get("workflow", {}).get("actions", [])}

    def _statuses_by_key(self) -> dict[str, str]:
        return {item["key"]: item["label"] for item in self._config().get("workflow", {}).get("statuses", [])}

    def _read_csv(self, source_key: str) -> list[dict[str, str]]:
        path = self._source_path(source_key)
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            with path.open("r", encoding="latin-1", newline="") as handle:
                return list(csv.DictReader(handle))

    def _load_records(self) -> list[dict[str, Any]]:
        if not self.storage_path.exists():
            return []
        try:
            content = json.loads(self.storage_path.read_text(encoding="utf-8"))
            return content if isinstance(content, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _save_records(self, records: list[dict[str, Any]]) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.storage_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.storage_path)

    def _eligible_vacant_rows(self) -> list[dict[str, str]]:
        statuses = {self._normalise(item) for item in self._config().get("eligible_plot_statuses", [])}
        return [row for row in self._read_csv("vacant_plot_master") if self._normalise(row.get("status")) in statuses]

    @staticmethod
    def _plot_label(row: dict[str, str]) -> str:
        values = [row.get("bill_code"), row.get("plot_no"), row.get("plot_name"), row.get("village")]
        return " · ".join(str(value).strip() for value in values if str(value or "").strip())

    def list_plots(self) -> list[dict[str, Any]]:
        plots: list[dict[str, Any]] = []
        for index, row in enumerate(self._eligible_vacant_rows()):
            plots.append(
                {
                    "id": str(index),
                    "label": self._plot_label(row) or f"Vacant plot {index + 1}",
                    "bill_code": row.get("bill_code", ""),
                    "area_sqm": row.get("area", ""),
                    "ready_recknor_zone": row.get("ready_recknor_zone", ""),
                    "source_status": row.get("status", ""),
                    "reference_rr_rate": row.get("rr_rate", ""),
                }
            )
        return plots

    def _vacant_plot(self, plot_id: str) -> dict[str, str]:
        try:
            index = int(str(plot_id))
        except (TypeError, ValueError) as error:
            raise TenderWorkflowError("Select an eligible vacant plot.") from error
        rows = self._eligible_vacant_rows()
        if index < 0 or index >= len(rows):
            raise TenderWorkflowError("The selected vacant plot is no longer eligible.")
        return rows[index]

    def _match_plot_master(self, vacant_row: dict[str, str]) -> dict[str, Any]:
        bill_code = self._normalise(vacant_row.get("bill_code"))
        if not bill_code:
            return {"status": "unmatched", "matches": [], "reason": "The vacant-plot record has no bill code."}
        candidate_columns = ("plot_code", "customer_code", "existing_plot_no", "mcgm_plot_no")
        matches: list[dict[str, str]] = []
        for row in self._read_csv("plot_master"):
            if any(self._normalise(row.get(column)) == bill_code for column in candidate_columns):
                matches.append(row)
        if len(matches) == 1:
            match = matches[0]
            return {
                "status": "matched",
                "matches": [
                    {
                        "plot_id": match.get("plot_id", ""),
                        "plot_code": match.get("plot_code", ""),
                        "plot_name": match.get("plot_name", ""),
                        "estate_name": match.get("estate_name", ""),
                    }
                ],
            }
        if len(matches) > 1:
            return {
                "status": "ambiguous",
                "matches": [
                    {
                        "plot_id": match.get("plot_id", ""),
                        "plot_code": match.get("plot_code", ""),
                        "plot_name": match.get("plot_name", ""),
                        "estate_name": match.get("estate_name", ""),
                    }
                    for match in matches[:10]
                ],
                "reason": "More than one plot-master record matches the bill code; review is required.",
            }
        return {"status": "unmatched", "matches": [], "reason": "No exact plot-master match was found for the bill code."}

    @staticmethod
    def _table_rows_from_markdown(path: Path) -> list[dict[str, str]]:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        rows: list[dict[str, str]] = []
        collecting = False
        for line in lines:
            text = line.strip()
            if text.startswith("| Sr. No.") and "Check" in text:
                collecting = True
                continue
            if not collecting:
                continue
            if not text.startswith("|"):
                if rows:
                    break
                continue
            if re.match(r"^\|[\s|:-]+\|$", text):
                continue
            cells = [cell.strip().replace("<br>", " ") for cell in text.strip("|").split("|")]
            if len(cells) < 2:
                continue
            number, checkpoint = cells[0], cells[1]
            if not number or not checkpoint:
                continue
            rows.append(
                {
                    "key": f"item_{len(rows) + 1}",
                    "number": number,
                    "label": checkpoint,
                    "source_answer": cells[2] if len(cells) > 2 else "",
                    "source_remarks": cells[3] if len(cells) > 3 else "",
                }
            )
        return rows

    def checklist(self, checklist_key: str) -> dict[str, Any]:
        checklist = self._checklists_by_key().get(checklist_key)
        if not checklist:
            raise TenderWorkflowError("Select a valid LAC checklist.")
        path = self._source_path(checklist["source_key"])
        return {"key": checklist_key, "label": checklist["label"], "source_file": path.name, "items": self._table_rows_from_markdown(path)}

    def config_payload(self) -> dict[str, Any]:
        config = self._config()
        return {
            "version": config.get("version"),
            "source_files": config.get("source_files", {}),
            "form_fields": config.get("form_fields", []),
            "checklists": [{"key": item["key"], "label": item["label"]} for item in config.get("checklists", [])],
            "statuses": self._statuses_by_key(),
            "workflow_notice": "Source data is used for plot context and checklist evidence. Approved commercial and policy values remain required workflow inputs.",
        }

    def plot_detail(self, plot_id: str) -> dict[str, Any]:
        row = self._vacant_plot(plot_id)
        mapping = self._match_plot_master(row)
        source_snapshot = {
            key: row.get(key, "")
            for key in ("bill_code", "plot_no", "plot_name", "village", "area", "ready_recknor_zone", "rr_rate", "status", "reservation", "remark")
        }
        return {
            "id": str(plot_id),
            "label": self._plot_label(row),
            "prefill_fields": {"area_sqm": row.get("area", "")},
            "source_snapshot": source_snapshot,
            "mapping": mapping,
            "rate_notice": "The source RR rate is retained as a reference only. Enter an approved monthly SoR rate from the applicable approved schedule; no rate is inferred from this CSV.",
        }

    def _field_definitions(self) -> dict[str, dict[str, Any]]:
        return {field["key"]: field for field in self._config().get("form_fields", [])}

    def _sanitize_fields(self, fields: dict[str, Any] | None) -> dict[str, Any]:
        definitions = self._field_definitions()
        clean: dict[str, Any] = {}
        for key, value in (fields or {}).items():
            if key not in definitions:
                continue
            if definitions[key].get("type") == "number":
                if value is None or str(value).strip() == "":
                    clean[key] = ""
                else:
                    clean[key] = self._clean_number(value, definitions[key]["label"])
            else:
                clean[key] = str(value or "").strip()
        return clean

    def calculate(self, fields: dict[str, Any]) -> dict[str, Any]:
        definitions = self._field_definitions()
        required_keys = ("area_sqm", "lease_years", "fsi", "approved_monthly_sor_rate", "annual_escalation_percent", "discount_rate_percent", "gst_percent")
        missing = [definitions[key]["label"] for key in required_keys if fields.get(key) in (None, "")]
        if missing:
            return {"ready": False, "missing_fields": missing, "steps": []}

        area = self._clean_number(fields["area_sqm"], definitions["area_sqm"]["label"], positive=True)
        lease_years = self._clean_number(fields["lease_years"], definitions["lease_years"]["label"], positive=True)
        if not lease_years.is_integer():
            raise TenderWorkflowError("Lease period must be a whole number of years.")
        fsi = self._clean_number(fields["fsi"], definitions["fsi"]["label"], positive=True)
        monthly_rate = self._clean_number(fields["approved_monthly_sor_rate"], definitions["approved_monthly_sor_rate"]["label"], positive=True)
        escalation = self._clean_number(fields["annual_escalation_percent"], definitions["annual_escalation_percent"]["label"])
        discount = self._clean_number(fields["discount_rate_percent"], definitions["discount_rate_percent"]["label"])
        gst = self._clean_number(fields["gst_percent"], definitions["gst_percent"]["label"])
        developed_area = area * fsi
        base_monthly_rent = developed_area * monthly_rate
        base_annual_rent = base_monthly_rent * 12
        npv_total = 0.0
        schedule: list[dict[str, float | int]] = []
        for year in range(1, int(lease_years) + 1):
            annual_rent = base_annual_rent * ((1 + escalation / 100) ** (year - 1))
            discount_factor = 1 / ((1 + discount / 100) ** (year - 1))
            present_value = annual_rent * discount_factor
            npv_total += present_value
            schedule.append({"year": year, "annual_rent": annual_rent, "discount_factor": discount_factor, "present_value": present_value})
        gst_amount = npv_total * gst / 100
        extras: dict[str, float] = {}
        for key in ("service_charge_per_sqm_year", "nominal_rent_per_sqm_year"):
            if fields.get(key) not in (None, ""):
                extras[key] = area * self._clean_number(fields[key], definitions[key]["label"])
        return {
            "ready": True,
            "currency": "INR",
            "developed_area_sqm": developed_area,
            "base_monthly_rent": base_monthly_rent,
            "base_annual_rent": base_annual_rent,
            "upfront_premium_before_gst": npv_total,
            "gst_amount": gst_amount,
            "upfront_premium_including_gst": npv_total + gst_amount,
            "annual_optional_charges": extras,
            "schedule": schedule,
            "steps": [
                "Developed area = plot area × approved FSI.",
                "Base annual rent = developed area × approved monthly SoR rate × 12.",
                "Each lease-year rent is escalated by the approved annual escalation percentage.",
                "Each year is discounted using the approved discount rate; the upfront premium is the sum of those present values.",
                "GST is calculated from the resulting upfront premium using the entered approved percentage.",
            ],
            "source_references": [self._config()["source_files"]["upfront_calculation_reference"], self._config()["source_files"]["npv_calculation_reference"]],
        }

    def _hydrate(self, record: dict[str, Any]) -> dict[str, Any]:
        output = json.loads(json.dumps(record))
        output["status_label"] = self._statuses_by_key().get(output.get("status"), output.get("status"))
        output["available_actions"] = [
            {"key": key, "label": action["label"]}
            for key, action in self._actions_by_key().items()
            if output.get("status") in action.get("from", [])
        ]
        return output

    def list_workflows(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._hydrate(record) for record in sorted(self._load_records(), key=lambda item: item.get("updated_at", ""), reverse=True)]

    def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        with self._lock:
            for record in self._load_records():
                if record.get("id") == workflow_id:
                    return self._hydrate(record)
        raise TenderWorkflowError("Tender workflow was not found.")

    def _checklist_answers(self, checklist: dict[str, Any], answers: dict[str, Any] | None) -> list[dict[str, str]]:
        supplied = answers or {}
        return [
            {
                **item,
                "answer": str(supplied.get(item["key"], item.get("source_answer", "")) or "").strip(),
            }
            for item in checklist["items"]
        ]

    def create_workflow(self, payload: dict[str, Any]) -> dict[str, Any]:
        plot_id = str(payload.get("plot_id", ""))
        checklist_key = str(payload.get("checklist_key", ""))
        detail = self.plot_detail(plot_id)
        checklist = self.checklist(checklist_key)
        fields = self._sanitize_fields(payload.get("fields"))
        if not fields.get("area_sqm") and detail["prefill_fields"].get("area_sqm"):
            fields["area_sqm"] = self._clean_number(detail["prefill_fields"]["area_sqm"], "Area")
        now = self._now()
        record = {
            "id": uuid.uuid4().hex,
            "status": self._config().get("workflow", {}).get("initial_status", "LAC_DRAFT"),
            "plot_id": plot_id,
            "plot_label": detail["label"],
            "source_snapshot": detail["source_snapshot"],
            "plot_mapping": detail["mapping"],
            "checklist": {"key": checklist["key"], "label": checklist["label"], "source_file": checklist["source_file"], "items": self._checklist_answers(checklist, payload.get("checklist_answers"))},
            "fields": fields,
            "calculation": self.calculate(fields),
            "created_at": now,
            "updated_at": now,
            "events": [{"at": now, "action": "created", "from": None, "to": self._config().get("workflow", {}).get("initial_status", "LAC_DRAFT"), "comment": "Workflow draft created."}],
        }
        with self._lock:
            records = self._load_records()
            records.append(record)
            self._save_records(records)
        return self._hydrate(record)

    def _merge_inputs(self, record: dict[str, Any], fields: dict[str, Any] | None, checklist_answers: dict[str, Any] | None) -> None:
        record["fields"].update(self._sanitize_fields(fields))
        answers = checklist_answers or {}
        for item in record["checklist"]["items"]:
            if item["key"] in answers:
                item["answer"] = str(answers[item["key"]] or "").strip()
        record["calculation"] = self.calculate(record["fields"])

    def _validate_action(self, record: dict[str, Any], action_key: str, action: dict[str, Any], comment: str) -> None:
        requirements = set(action.get("requires", []))
        if "comment" in requirements and not comment.strip():
            raise TenderWorkflowError("A return comment is required.")
        if "lac_complete" in requirements:
            missing_answers = [item["number"] for item in record["checklist"]["items"] if not item.get("answer", "").strip()]
            if missing_answers:
                raise TenderWorkflowError(f"Complete every LAC checklist response before submission (missing: {', '.join(missing_answers)}).")
            required_fields = [
                field["label"]
                for field in self._config().get("form_fields", [])
                if action_key in field.get("required_for", []) and not record["fields"].get(field["key"])
            ]
            if required_fields:
                raise TenderWorkflowError(f"Complete required LAC fields: {', '.join(required_fields)}.")
        if "proposal_fields" in requirements:
            missing = [
                field["label"]
                for field in self._config().get("form_fields", [])
                if action_key in field.get("required_for", []) and not record["fields"].get(field["key"])
            ]
            if missing:
                raise TenderWorkflowError(f"Complete required proposal fields: {', '.join(missing)}.")
        if "calculation" in requirements and not record["calculation"].get("ready"):
            raise TenderWorkflowError("Complete the approved financial inputs before finalizing the calculation.")

    def apply_action(self, workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        action_key = str(payload.get("action", ""))
        config = self._config()
        action = self._actions_by_key().get(action_key)
        if not action:
            raise TenderWorkflowError("Unknown workflow action.")
        comment = str(payload.get("comment", "") or "").strip()
        with self._lock:
            records = self._load_records()
            record = next((item for item in records if item.get("id") == workflow_id), None)
            if not record:
                raise TenderWorkflowError("Tender workflow was not found.")
            if record.get("status") not in action.get("from", []):
                raise TenderWorkflowError("This action is not available at the current workflow stage.")
            self._merge_inputs(record, payload.get("fields"), payload.get("checklist_answers"))
            self._validate_action(record, action_key, action, comment)
            before = record["status"]
            record["status"] = action["to"]
            record["updated_at"] = self._now()
            record["events"].append({"at": record["updated_at"], "action": action_key, "from": before, "to": record["status"], "comment": comment})
            self._save_records(records)
            return self._hydrate(record)

    @staticmethod
    def _money(value: Any) -> str:
        try:
            return f"INR {float(value):,.2f}"
        except (TypeError, ValueError):
            return "Not available"

    def document_markdown(self, workflow_id: str, kind: str) -> str:
        if kind not in {"lac", "board-note", "tender"}:
            raise TenderWorkflowError("Document type must be lac, board-note, or tender.")
        workflow = self.get_workflow(workflow_id)
        source_files = self._config()["source_files"]
        title = {"lac": "LAC Proposal Draft", "board-note": "Board Note Draft", "tender": "Tender Draft"}[kind]
        template_key = {"lac": "embarkation_checklist", "board-note": "board_note_template", "tender": "tender_template"}[kind]
        lines = [
            f"# {title}",
            "",
            "> Draft generated from the Tender Publication workflow record. It is not an approved or publishable document until the required authority approvals and template review are complete.",
            "",
            "## Workflow record",
            "",
            f"- **Workflow ID:** `{workflow['id']}`",
            f"- **Current stage:** {workflow['status_label']}",
            f"- **Selected plot:** {workflow['plot_label']}",
            f"- **Source template/reference:** `{source_files[template_key]}`",
            "",
            "## Source-backed plot context",
            "",
        ]
        for key, value in workflow["source_snapshot"].items():
            if value not in (None, ""):
                lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
        lines.extend(["", "## Entered proposal inputs", ""])
        for field in self._config().get("form_fields", []):
            value = workflow["fields"].get(field["key"], "")
            if value not in (None, ""):
                lines.append(f"- **{field['label']}:** {value}")
        if kind == "lac":
            lines.extend(["", "## LAC checklist responses", "", "| No. | Check point | Response |", "| --- | --- | --- |"])
            for item in workflow["checklist"]["items"]:
                label = item["label"].replace("|", "/")
                answer = item.get("answer", "").replace("|", "/")
                lines.append(f"| {item['number']} | {label} | {answer} |")
        calculation = workflow.get("calculation", {})
        if calculation.get("ready"):
            lines.extend(
                [
                    "",
                    "## Financial calculation draft",
                    "",
                    f"- **Developed area:** {float(calculation['developed_area_sqm']):,.2f} sq. m",
                    f"- **Base monthly rent:** {self._money(calculation['base_monthly_rent'])}",
                    f"- **Base annual rent:** {self._money(calculation['base_annual_rent'])}",
                    f"- **Upfront premium before GST:** {self._money(calculation['upfront_premium_before_gst'])}",
                    f"- **GST amount:** {self._money(calculation['gst_amount'])}",
                    f"- **Upfront premium including GST:** {self._money(calculation['upfront_premium_including_gst'])}",
                    "",
                    "Calculation uses the approved values entered in this workflow; source reference files are listed below and must be reviewed by the approving authority.",
                ]
            )
        else:
            lines.extend(["", "## Financial calculation draft", "", "Calculation is pending required approved inputs: " + ", ".join(calculation.get("missing_fields", [])) + "."])
        lines.extend(["", "## Source references", ""])
        for source in calculation.get("source_references", []) if isinstance(calculation, dict) else []:
            lines.append(f"- `{source}`")
        lines.extend(["", "## Workflow history", "", "| Time (UTC) | Action | From | To | Comment |", "| --- | --- | --- | --- | --- |"])
        for event in workflow.get("events", []):
            lines.append(f"| {event['at']} | {event['action']} | {event.get('from') or ''} | {event.get('to') or ''} | {event.get('comment', '').replace('|', '/')} |")
        return "\n".join(lines) + "\n"
