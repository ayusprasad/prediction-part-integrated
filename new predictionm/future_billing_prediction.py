"""Offline-safe future billing and rent prediction module.

This file is intentionally self-contained so it can be copied into an existing
RAG/SQL chatbot.  It has no required third-party dependencies.  PostgreSQL,
PGVector, and an LLM are optional adapters; when they are unavailable the
module uses deterministic local query extraction and compound growth.

Typical integration::

    from future_billing_prediction import predict_from_chat_query

    answer = predict_from_chat_query(
        "What will my rent be in 2029? Current amount is Rs 14000",
        data_source=my_postgres_and_pgvector_adapter,
        llm_extractor=my_llm_json_function,
    )
    if answer is not None:
        return answer
    return existing_rag_or_sql_pipeline(user_text)

The data_source adapter may implement either or both methods below.  Each
method should return a mapping or None.  The module is deliberately tolerant
of adapter failures so prediction never becomes a hard dependency on a live
database or vector store.

    get_baseline(request) -> {"amount": 14000, "historical_amounts": [..]}
    get_rules(request) -> {"annual_growth_rate": 0.06, "cgst_rate": 0.09, ...}
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
import json
import math
import re
from typing import Any, Callable, Mapping, Optional, Protocol


MONTH_NAMES = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

BILL_TYPE_ALIASES = {
    "rent": "rent",
    "lease": "rent",
    "licence fee": "rent",
    "license fee": "rent",
    "additional rent": "additional_rent",
    "electricity": "electricity",
    "power": "electricity",
    "water": "water",
    "water bill": "water",
    "tax": "tax",
    "property tax": "tax",
}

DEFAULT_GROWTH_RATES = {
    "rent": 0.06,
    "additional_rent": 0.06,
    "electricity": 0.07,
    "water": 0.05,
    "tax": 0.05,
}


def _clean_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    text = str(value).replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0))
    return number if math.isfinite(number) else None


def _clamp_rate(value: Any, default: float) -> float:
    parsed = _clean_number(value)
    if parsed is None:
        return default
    # Human-entered percentages such as 6 become 0.06; decimal rates remain.
    return parsed / 100 if abs(parsed) >= 1 else parsed


def _period_index(year: int, month: int) -> int:
    return year * 12 + month


class PredictionDataSource(Protocol):
    """Optional bridge to the host application's PostgreSQL/PGVector layer."""

    def get_baseline(self, request: "PredictionRequest") -> Optional[Mapping[str, Any]]:
        ...

    def get_rules(self, request: "PredictionRequest") -> Optional[Mapping[str, Any]]:
        ...


@dataclass
class PredictionRequest:
    target_year: int
    target_month: int = 12
    bill_type: str = "rent"
    current_baseline_amount: Optional[float] = None
    current_year: int = field(default_factory=lambda: date.today().year)
    current_month: int = field(default_factory=lambda: date.today().month)
    location: Optional[str] = None
    property_type: Optional[str] = None
    billing_period: str = "monthly"


@dataclass
class PredictionResult:
    request: PredictionRequest
    final_amount: float
    monthly_amount: float
    baseline_amount: float
    annual_growth_rate: float
    horizon_months: int
    taxes: dict[str, float]
    tax_total: float
    source: str
    fallback_applied: bool
    fallback_reasons: list[str]
    calculation_steps: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["request"] = asdict(self.request)
        return payload


class PredictionRouter:
    """Decide whether a chat prompt belongs to the future-prediction workflow."""

    PREDICTION_TERMS = re.compile(
        r"\b(predict|prediction|forecast|future|estimate|project|expected|will\s+my|next\s+year|next\s+month|by\s+20\d{2})\b",
        re.IGNORECASE,
    )
    BILLING_TERMS = re.compile(
        r"\b(rent|lease|licen[cs]e|electricity|power|water|tax|bill|charge|cess|rate)\b",
        re.IGNORECASE,
    )

    def is_prediction(self, prompt: str) -> bool:
        text = (prompt or "").strip()
        return bool(text and self.PREDICTION_TERMS.search(text) and self.BILLING_TERMS.search(text))

    def route(self, prompt: str) -> str:
        return "prediction" if self.is_prediction(prompt) else "existing_rag_or_sql"


class QueryExpander:
    """Extract prediction entities with an optional LLM, then local fallbacks."""

    def __init__(self, llm_extractor: Optional[Callable[[str], Any]] = None):
        self.llm_extractor = llm_extractor

    def expand(self, prompt: str) -> PredictionRequest:
        extracted: dict[str, Any] = {}
        if self.llm_extractor:
            try:
                raw = self.llm_extractor(prompt)
                extracted = self._as_mapping(raw)
            except Exception:
                # A failed LLM call is expected in offline mode.
                extracted = {}

        local = self._extract_locally(prompt)
        merged = {**local, **{key: value for key, value in extracted.items() if value not in (None, "")}}
        today = date.today()
        target_year = int(merged.get("target_year") or today.year + 1)
        target_month = int(merged.get("target_month") or 12)
        current_year = int(merged.get("current_year") or today.year)
        current_month = int(merged.get("current_month") or today.month)
        return PredictionRequest(
            target_year=target_year,
            target_month=max(1, min(12, target_month)),
            bill_type=str(merged.get("bill_type") or "rent"),
            current_baseline_amount=_clean_number(merged.get("current_baseline_amount")),
            current_year=current_year,
            current_month=max(1, min(12, current_month)),
            location=merged.get("location"),
            property_type=merged.get("property_type"),
            billing_period=str(merged.get("billing_period") or "monthly"),
        )

    @staticmethod
    def _as_mapping(raw: Any) -> dict[str, Any]:
        if isinstance(raw, Mapping):
            return dict(raw)
        if isinstance(raw, str):
            candidate = raw.strip()
            candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.IGNORECASE)
            parsed = json.loads(candidate)
            return dict(parsed) if isinstance(parsed, Mapping) else {}
        return {}

    @staticmethod
    def _extract_locally(prompt: str) -> dict[str, Any]:
        text = (prompt or "").strip()
        lowered = text.lower()
        result: dict[str, Any] = {}

        for alias, normalized in sorted(BILL_TYPE_ALIASES.items(), key=lambda item: -len(item[0])):
            if alias in lowered:
                result["bill_type"] = normalized
                break

        year_match = re.search(r"\b(20\d{2})\b", text)
        if year_match:
            result["target_year"] = int(year_match.group(1))
        elif "next year" in lowered:
            result["target_year"] = date.today().year + 1
        elif "this year" in lowered:
            result["target_year"] = date.today().year

        for name, month in MONTH_NAMES.items():
            if re.search(rf"\b{name}\b", lowered):
                result["target_month"] = month
                break
        month_number = re.search(r"\b(?:month|mo)\s*([1-9]|1[0-2])\b", lowered)
        if month_number:
            result["target_month"] = int(month_number.group(1))

        amount_patterns = [
            r"(?:current|present|baseline|existing|now)[^\d₹]{0,24}(₹|rs\.?\s*)?([\d,]+(?:\.\d+)?)",
            r"(?:amount|bill|rent)[^\d₹]{0,24}(₹|rs\.?\s*)?([\d,]+(?:\.\d+)?)",
        ]
        for pattern in amount_patterns:
            amount_match = re.search(pattern, lowered, flags=re.IGNORECASE)
            if amount_match:
                result["current_baseline_amount"] = _clean_number(amount_match.group(2))
                break

        period_match = re.search(r"\b(monthly|yearly|annual|half[- ]yearly|semi[- ]annual)\b", lowered)
        if period_match:
            period = period_match.group(1).replace("-", "_")
            result["billing_period"] = "yearly" if period in {"yearly", "annual"} else "half_yearly" if "half" in period or "semi" in period else "monthly"

        return result


class PredictionEngine:
    """Retrieve context when available and calculate an explainable forecast."""

    def __init__(
        self,
        data_source: Optional[PredictionDataSource] = None,
        default_baseline_amount: float = 10_000.0,
        default_growth_rates: Optional[Mapping[str, float]] = None,
    ):
        self.data_source = data_source
        self.default_baseline_amount = max(0.0, float(default_baseline_amount))
        self.default_growth_rates = {**DEFAULT_GROWTH_RATES, **(default_growth_rates or {})}

    def predict(self, request: PredictionRequest) -> PredictionResult:
        self._validate(request)
        fallback_reasons: list[str] = []
        baseline_context = self._retrieve("get_baseline", request, fallback_reasons)
        rules_context = self._retrieve("get_rules", request, fallback_reasons)

        baseline = request.current_baseline_amount
        source = "user baseline"
        if baseline is None:
            baseline = _clean_number(baseline_context.get("amount")) if baseline_context else None
            source = "PostgreSQL/PGVector baseline" if baseline is not None else "offline default baseline"
        if baseline is None:
            baseline = self.default_baseline_amount
            fallback_reasons.append("No current amount was provided or retrieved; the configured default baseline was used.")
        if baseline < 0:
            raise ValueError("The current baseline amount cannot be negative.")

        bill_type = request.bill_type if request.bill_type in self.default_growth_rates else "rent"
        default_rate = self.default_growth_rates[bill_type]
        growth_rate = _clamp_rate(rules_context.get("annual_growth_rate") if rules_context else None, default_rate)
        if not rules_context or rules_context.get("annual_growth_rate") is None:
            fallback_reasons.append(f"No applicable growth rule was retrieved; the offline {growth_rate:.1%} annual default was used.")

        historical = (baseline_context or {}).get("historical_amounts") or []
        if len(historical) >= 2 and not (rules_context or {}).get("annual_growth_rate"):
            inferred = self._infer_growth_rate(historical)
            if inferred is not None:
                growth_rate = inferred
                fallback_reasons.append("The annual growth rate was inferred from retrieved historical amounts.")

        horizon = _period_index(request.target_year, request.target_month) - _period_index(request.current_year, request.current_month)
        monthly_growth = (1.0 + growth_rate) ** (1.0 / 12.0) - 1.0
        monthly_amount = baseline * ((1.0 + monthly_growth) ** horizon)

        period_months = {"monthly": 1, "half_yearly": 6, "yearly": 12}.get(request.billing_period, 1)
        subtotal = monthly_amount * period_months
        cgst_rate = _clamp_rate((rules_context or {}).get("cgst_rate"), 0.09)
        sgst_rate = _clamp_rate((rules_context or {}).get("sgst_rate"), 0.09)
        taxes = {
            "CGST": subtotal * cgst_rate,
            "SGST": subtotal * sgst_rate,
        }
        for name, value in (rules_context or {}).get("additional_taxes", {}).items():
            taxes[str(name)] = subtotal * _clamp_rate(value, 0.0)
        tax_total = sum(taxes.values())
        final_amount = subtotal + tax_total

        calculation_steps = [
            f"Baseline amount = {baseline:,.2f} ({source}).",
            f"Horizon = {horizon} month(s), using {growth_rate:.2%} annual compound growth.",
            f"Monthly forecast = {baseline:,.2f} × (1 + {monthly_growth:.4%})^{horizon} = {monthly_amount:,.2f}.",
            f"Billing period subtotal = {monthly_amount:,.2f} × {period_months} = {subtotal:,.2f}.",
            f"Taxes = {tax_total:,.2f}; final predicted amount = {subtotal:,.2f} + {tax_total:,.2f} = {final_amount:,.2f}.",
        ]
        return PredictionResult(
            request=request,
            final_amount=final_amount,
            monthly_amount=monthly_amount,
            baseline_amount=baseline,
            annual_growth_rate=growth_rate,
            horizon_months=horizon,
            taxes=taxes,
            tax_total=tax_total,
            source=source,
            fallback_applied=bool(fallback_reasons),
            fallback_reasons=fallback_reasons,
            calculation_steps=calculation_steps,
            metadata={"retrieved_baseline": bool(baseline_context), "retrieved_rules": bool(rules_context)},
        )

    def _retrieve(self, method_name: str, request: PredictionRequest, reasons: list[str]) -> Mapping[str, Any]:
        if self.data_source is None:
            return {}
        method = getattr(self.data_source, method_name, None)
        if not callable(method):
            reasons.append(f"The data source does not implement {method_name}; offline fallback was used.")
            return {}
        try:
            result = method(request)
            return dict(result) if isinstance(result, Mapping) else {}
        except Exception as exc:
            reasons.append(f"{method_name} was unavailable ({type(exc).__name__}); offline fallback was used.")
            return {}

    @staticmethod
    def _infer_growth_rate(historical: list[Any]) -> Optional[float]:
        values = [_clean_number(item) for item in historical]
        values = [value for value in values if value is not None and value > 0]
        if len(values) < 2:
            return None
        rate = (values[-1] / values[0]) ** (12 / max(1, len(values) - 1)) - 1
        return rate if math.isfinite(rate) and -0.5 <= rate <= 1.0 else None

    @staticmethod
    def _validate(request: PredictionRequest) -> None:
        if not 1 <= request.current_month <= 12 or not 1 <= request.target_month <= 12:
            raise ValueError("Months must be between 1 and 12.")
        if request.target_year <= 0 or request.current_year <= 0:
            raise ValueError("Years must be positive integers.")
        if _period_index(request.target_year, request.target_month) <= _period_index(request.current_year, request.current_month):
            raise ValueError("The target period must be after the current period.")


class ExplainablePredictor:
    """Build a user-facing answer with the exact calculation trace."""

    def format(self, result: PredictionResult) -> str:
        request = result.request
        period = f"{request.target_year}-{request.target_month:02d}"
        lines = [
            f"Predicted {request.bill_type.replace('_', ' ')} for {period}: INR {result.final_amount:,.2f}",
            "",
            "Calculation breakdown:",
            *[f"{index}. {step}" for index, step in enumerate(result.calculation_steps, start=1)],
        ]
        if result.fallback_applied:
            lines.extend(["", "Fallback notes:", *[f"- {reason}" for reason in result.fallback_reasons]])
        return "\n".join(lines)


def predict_from_chat_query(
    prompt: str,
    *,
    data_source: Optional[PredictionDataSource] = None,
    llm_extractor: Optional[Callable[[str], Any]] = None,
    default_baseline_amount: float = 10_000.0,
) -> Optional[str]:
    """Return an answer for prediction prompts, otherwise return None.

    This makes the module drop-in for an existing chatbot router: call it before
    the standard SQL/PDF/RAG chain and continue with that chain when ``None`` is
    returned.
    """

    router = PredictionRouter()
    if not router.is_prediction(prompt):
        return None
    request = QueryExpander(llm_extractor).expand(prompt)
    result = PredictionEngine(data_source, default_baseline_amount=default_baseline_amount).predict(request)
    return ExplainablePredictor().format(result)


if __name__ == "__main__":
    print(predict_from_chat_query("What will my rent be in 2029? Current amount is Rs 14000"))
