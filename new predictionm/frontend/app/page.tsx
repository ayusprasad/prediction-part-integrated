"use client";

import { useEffect, useState } from "react";
import type { ChangeEvent } from "react";

type XgbTree = {
  base_weights: number[];
  default_left: number[];
  left_children: number[];
  right_children: number[];
  split_conditions: number[];
  split_indices: number[];
};

type XgbModel = {
  learner: {
    learner_model_param: { base_score: string };
    gradient_booster: { model: { trees: XgbTree[] } };
  };
};

type Manifest = {
  feature_columns: string[];
  metrics: {
    mae: number;
    rmse: number;
    r2_raw: number;
    r2_log: number;
    smape_percent: number;
    n: number;
    training_pairs: number;
    total_pairs: number;
    model: string;
  };
};

type FormState = {
  year: number;
  month: number;
  amount: number;
  cgst: number;
  sgst: number;
  billingCharge: number;
  areaBillPer: "monthly" | "half_yearly" | "yearly";
  area: number;
  targetYear: number;
  targetMonth: number;
  billType: "rent" | "additional_rent" | "electricity" | "water" | "tax";
  lineCategory: "rent" | "additional_rent";
  structureType: "other" | "mbpt";
  waterTaxIncluded: boolean;
  rates: {
    general: number;
    sewerage: number;
    water: number;
    street: number;
    mecess: number;
    tree_cess: number;
    wbt: number;
    sbt: number;
    egcess: number;
  };
};

type Step = { label: string; formula: string; value: number };

type Prediction = {
  finalPrice: number;
  baseAmount: number;
  modelRaw: number;
  modelLogR2: number;
  modelRawR2: number;
  formulaSchedule: string;
  nrvConstant: number;
  formulaSteps: Step[];
  taxItems: Array<{ label: string; formula: string; value: number }>;
  totalFormulaTax: number;
  forecastPath: Array<{ year: number; month: number; raw: number; amount: number }>;
  source: "xgboost" | "offline-fallback";
  billType: FormState["billType"];
  fallbackReason: string;
};

const DEFAULT_FORM: FormState = {
  year: 2025,
  month: 8,
  amount: 14000,
  cgst: 1260,
  sgst: 1260,
  billingCharge: 250,
  areaBillPer: "monthly",
  area: 1000,
  targetYear: 2026,
  targetMonth: 4,
  billType: "rent",
  lineCategory: "rent",
  structureType: "mbpt",
  waterTaxIncluded: true,
  rates: {
    general: 15,
    sewerage: 8,
    water: 6,
    street: 2,
    mecess: 2,
    tree_cess: 1,
    wbt: 3,
    sbt: 2,
    egcess: 1,
  },
};

const RATE_LABELS: Record<keyof FormState["rates"], string> = {
  general: "General property",
  sewerage: "Sewerage",
  water: "Water",
  street: "Street",
  mecess: "MECESS",
  tree_cess: "Tree cess",
  wbt: "WBT",
  sbt: "SBT",
  egcess: "EGCESS",
};

const PERIOD_MONTHS = { monthly: 1, half_yearly: 6, yearly: 12 } as const;
const PRE_TAX_MONTHS = new Set([4, 10]);
const POST_TAX_MONTHS = new Set([3, 9]);

function periodIndex(year: number, month: number) {
  return year * 12 + month;
}

function nextMonth(year: number, month: number) {
  return month === 12 ? { year: year + 1, month: 1 } : { year, month: month + 1 };
}

function numberValue(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function currency(value: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number.isFinite(value) ? value : 0);
}

function plainNumber(value: number) {
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(
    Number.isFinite(value) ? value : 0,
  );
}

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function normalizeRate(value: number) {
  // The UI is percentage-based, so an entered value of 1 means 1%, not 100%.
  return Math.abs(value) >= 1 ? value / 100 : value;
}

type ExpandedQuery = {
  isPrediction: boolean;
  targetYear?: number;
  targetMonth?: number;
  billType?: FormState["billType"];
  currentBaselineAmount?: number;
  location?: string;
  propertyType?: string;
};

function routePredictionQuery(query: string) {
  const hasFutureSignal = /\b(predict|forecast|future|estimate|project|expected|will\s+my|next\s+year|next\s+month|by\s+20\d{2})\b/i.test(query);
  const hasBillingSignal = /\b(rent|lease|electricity|power|water|tax|bill|charge|cess|rate)\b/i.test(query);
  return Boolean(query.trim() && hasFutureSignal && hasBillingSignal);
}

function expandPredictionQuery(query: string): ExpandedQuery {
  const lowered = query.toLowerCase();
  const result: ExpandedQuery = { isPrediction: routePredictionQuery(query) };
  const year = query.match(/\b(20\d{2})\b/);
  const monthNames = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"];
  const monthNameIndex = monthNames.findIndex((name) => new RegExp(`\\b${name}\\b`, "i").test(query));
  const monthNumber = lowered.match(/\b(?:month|mo)\s*([1-9]|1[0-2])\b/);
  const amount = query.match(/(?:current|present|baseline|existing|now)[^\d₹]{0,24}(?:₹|rs\.?\s*)?([\d,]+(?:\.\d+)?)/i)
    ?? query.match(/(?:amount|bill)\s*(?:is|of|:)?\s*(?:₹|rs\.?\s*)?([\d,]+(?:\.\d+)?)/i);

  if (year) result.targetYear = Number(year[1]);
  else if (/\bnext\s+year\b/i.test(query)) result.targetYear = new Date().getFullYear() + 1;
  if (monthNameIndex >= 0) result.targetMonth = monthNameIndex + 1;
  else if (monthNumber) result.targetMonth = Number(monthNumber[1]);
  if (amount) result.currentBaselineAmount = Number(amount[1].replace(/,/g, ""));
  if (/\b(additional\s+rent)\b/i.test(query)) result.billType = "additional_rent";
  else if (/\b(electricity|power)\b/i.test(query)) result.billType = "electricity";
  else if (/\bwater\b/i.test(query)) result.billType = "water";
  else if (/\b(property\s+tax|tax)\b/i.test(query)) result.billType = "tax";
  else if (/\b(rent|lease|licen[cs]e)\b/i.test(query)) result.billType = "rent";
  if (/\b(monthly|month)\b/i.test(query)) result.targetMonth = result.targetMonth ?? 12;
  return result;
}

function predictXgbRaw(model: XgbModel, featureVector: number[]) {
  const baseScore = Number(model.learner.learner_model_param.base_score.replace(/[[\]]/g, ""));
  const trees = model.learner.gradient_booster.model.trees;
  let prediction = baseScore;

  for (const tree of trees) {
    let node = 0;
    while (tree.left_children[node] !== -1) {
      const featureIndex = tree.split_indices[node];
      const featureValue = featureVector[featureIndex];
      if (!Number.isFinite(featureValue)) {
        node = tree.default_left[node] ? tree.left_children[node] : tree.right_children[node];
      } else if (featureValue < tree.split_conditions[node]) {
        node = tree.left_children[node];
      } else {
        node = tree.right_children[node];
      }
    }
    prediction += tree.base_weights[node];
  }
  return prediction;
}

function makeFeatureVector(
  manifest: Manifest,
  form: FormState,
  presentAmount: number,
  presentCgst: number,
  presentSgst: number,
  presentYear: number,
  presentMonth: number,
  targetYear: number,
  targetMonth: number,
) {
  const values: Record<string, number> = {
    present_amount: presentAmount,
    present_cgst: presentCgst,
    present_sgst: presentSgst,
    present_area: Math.max(0, form.area),
    present_year: presentYear,
    present_month: presentMonth,
    target_year: targetYear,
    target_month: targetMonth,
    horizon_months: periodIndex(targetYear, targetMonth) - periodIndex(presentYear, presentMonth),
    present_amount_per_area: form.area > 0 ? presentAmount / form.area : 0,
    present_log_amount: Math.log1p(Math.max(0, presentAmount)),
    billing_frequency_monthly: form.areaBillPer === "monthly" ? 1 : 0,
    billing_frequency_yearly: form.areaBillPer === "yearly" ? 1 : 0,
    line_category_additional_rent: form.lineCategory === "additional_rent" ? 1 : 0,
    line_category_rent: form.lineCategory === "rent" ? 1 : 0,
  };
  return manifest.feature_columns.map((column) => values[column] ?? 0);
}

function fallbackAnnualGrowthRate(billType: FormState["billType"]) {
  return ({ rent: 0.06, additional_rent: 0.06, electricity: 0.07, water: 0.05, tax: 0.05 })[billType];
}

function forecastOfflineAmount(form: FormState) {
  const path: Prediction["forecastPath"] = [];
  const targetIndex = periodIndex(form.targetYear, form.targetMonth);
  let currentYear = form.year;
  let currentMonth = form.month;
  let currentAmount = Math.max(0, form.amount);
  const monthlyGrowth = Math.pow(1 + fallbackAnnualGrowthRate(form.billType), 1 / 12) - 1;
  while (periodIndex(currentYear, currentMonth) < targetIndex) {
    const next = nextMonth(currentYear, currentMonth);
    currentAmount *= 1 + monthlyGrowth;
    path.push({ year: next.year, month: next.month, raw: Math.log1p(currentAmount), amount: currentAmount });
    currentYear = next.year;
    currentMonth = next.month;
  }
  return { amount: currentAmount, raw: Math.log1p(currentAmount), path };
}

function forecastBaseAmount(model: XgbModel | null, manifest: Manifest | null, form: FormState) {
  if (!model || !manifest || !["rent", "additional_rent"].includes(form.billType)) {
    return forecastOfflineAmount(form);
  }
  const path: Prediction["forecastPath"] = [];
  const targetIndex = periodIndex(form.targetYear, form.targetMonth);
  let currentYear = form.year;
  let currentMonth = form.month;
  let currentAmount = Math.max(0, form.amount);
  let currentCgst = Math.max(0, form.cgst);
  let currentSgst = Math.max(0, form.sgst);
  const cgstRate = form.amount > 0 ? Math.max(0, form.cgst / form.amount) : 0;
  const sgstRate = form.amount > 0 ? Math.max(0, form.sgst / form.amount) : 0;

  while (periodIndex(currentYear, currentMonth) < targetIndex) {
    const next = nextMonth(currentYear, currentMonth);
    const vector = makeFeatureVector(
      manifest,
      form,
      currentAmount,
      currentCgst,
      currentSgst,
      currentYear,
      currentMonth,
      next.year,
      next.month,
    );
    const raw = predictXgbRaw(model, vector);
    const nextAmount = Math.max(0, Math.expm1(raw));
    path.push({ year: next.year, month: next.month, raw, amount: nextAmount });
    currentAmount = nextAmount;
    currentCgst = nextAmount * cgstRate;
    currentSgst = nextAmount * sgstRate;
    currentYear = next.year;
    currentMonth = next.month;
  }

  return { amount: currentAmount, raw: path.at(-1)?.raw ?? Math.log1p(currentAmount), path };
}

function calculatePrediction(model: XgbModel | null, manifest: Manifest | null, form: FormState): Prediction {
  if (periodIndex(form.targetYear, form.targetMonth) <= periodIndex(form.year, form.month)) {
    throw new Error("Target month must be after the present bill month.");
  }
  const forecast = forecastBaseAmount(model, manifest, form);
  const monthlyBase = forecast.amount;
  const propertyFormulaEnabled = form.billType === "rent" || form.billType === "additional_rent";
  const nrvConstant = propertyFormulaEnabled ? (form.structureType === "mbpt" ? 0.837 : 0.792) : 0;
  const annualAmount = monthlyBase * 12;
  const lettingValue = annualAmount + annualAmount / 3;
  const grvp = lettingValue - (lettingValue * 0.9 * 0.9);
  const nrvp = grvp - grvp / 10;
  const grvs = grvp - annualAmount;
  const nrvs = grvs - grvs / 10;
  const presentPeriodMonths = PERIOD_MONTHS[form.areaBillPer];
  const areaCharge =
    Math.max(0, form.billingCharge) *
    (Math.max(0, form.area) / Math.max(form.area, 0.000001)) *
    (presentPeriodMonths / presentPeriodMonths);
  const cgstRate = form.amount > 0 ? Math.max(0, form.cgst / form.amount) : 0;
  const sgstRate = form.amount > 0 ? Math.max(0, form.sgst / form.amount) : 0;
  const taxableBase = monthlyBase + areaCharge;
  const predictedCgst = taxableBase * cgstRate;
  const predictedSgst = taxableBase * sgstRate;
  const rates = Object.fromEntries(
    Object.entries(form.rates).map(([key, value]) => [key, normalizeRate(value)]),
  ) as FormState["rates"];

  const dual = (rate: number) => (annualAmount / 2) * nrvConstant * rate + (nrvs / 2) * rate;
  const taxItems: Prediction["taxItems"] = [];
  let formulaSchedule = "No scheduled formula tax";
  if (propertyFormulaEnabled && PRE_TAX_MONTHS.has(form.targetMonth)) {
    formulaSchedule = "Pre taxes · April / October";
    const propertyTax =
      form.structureType === "mbpt"
        ? (nrvs * rates.general) / 2 + (nrvp * rates.sewerage) / 2 +
          (form.waterTaxIncluded ? (nrvp * rates.water) / 2 : 0)
        : 0;
    taxItems.push({
      label: "Property tax",
      formula: "(NRVS × general)/2 + (NRVP × sewerage)/2 + (NRVP × water)/2",
      value: propertyTax,
    });
    taxItems.push({ label: "Water benefit tax", formula: "((AM/2) × Const × WBT%) + (NRVS/2 × WBT%)", value: dual(rates.wbt) });
    taxItems.push({ label: "Sewerage benefit tax", formula: "((AM/2) × Const × SBT%) + (NRVS/2 × SBT%)", value: dual(rates.sbt) });
    taxItems.push({ label: "Employee guarantee cess", formula: "((AM/2) × Const × EGCESS%) + (NRVS/2 × EGCESS%)", value: dual(rates.egcess) });
    taxItems.push({ label: "Street tax", formula: "(NRVP × street rate) / 2", value: (nrvp * rates.street) / 2 });
  } else if (propertyFormulaEnabled && POST_TAX_MONTHS.has(form.targetMonth)) {
    formulaSchedule = "Post taxes · March / September";
    taxItems.push({ label: "Maharashtra education cess", formula: "((AM/2) × Const × MECESS%) + (NRVS/2 × MECESS%)", value: dual(rates.mecess) });
    taxItems.push({ label: "Tree cess", formula: "((AM/2) × Const × TREE%) + (NRVS/2 × TREE%)", value: dual(rates.tree_cess) });
  }
  const totalFormulaTax = taxItems.reduce((sum, item) => sum + item.value, 0);
  const finalPrice = taxableBase + predictedCgst + predictedSgst + totalFormulaTax;
  const source = model && manifest && propertyFormulaEnabled ? "xgboost" : "offline-fallback";
  const formulaSteps: Step[] = propertyFormulaEnabled
    ? [
        { label: "Forecast base amount", formula: source === "xgboost" ? "XGBoost prediction = expm1(model log prediction)" : `Offline compound growth using ${percent(fallbackAnnualGrowthRate(form.billType))} annual growth`, value: monthlyBase },
        { label: "Annual amount (AM)", formula: "AM = predicted monthly base × 12", value: annualAmount },
        { label: "Letting value (LV)", formula: "LV = AM + (AM / 3)", value: lettingValue },
        { label: "Gross rateable value — property (GRVP)", formula: "GRVP = LV − ((LV × 9/10) × 9/10)", value: grvp },
        { label: "Net rateable value — property (NRVP)", formula: "NRVP = GRVP − (GRVP / 10)", value: nrvp },
        { label: "Gross rateable value — structure (GRVS)", formula: "GRVS = GRVP − AM", value: grvs },
        { label: "Net rateable value — structure (NRVS)", formula: "NRVS = GRVS − (GRVS / 10)", value: nrvs },
        { label: "Area-linked billing charge", formula: "billing charge × area ratio × period ratio", value: areaCharge },
        { label: "Predicted CGST", formula: "(present CGST / present amount) × taxable base", value: predictedCgst },
        { label: "Predicted SGST", formula: "(present SGST / present amount) × taxable base", value: predictedSgst },
        { label: "Scheduled formula taxes", formula: formulaSchedule, value: totalFormulaTax },
        { label: "Final predicted bill", formula: "base + area charge + CGST + SGST + formula taxes", value: finalPrice },
      ]
    : [
        { label: "Forecast base amount", formula: `Offline compound growth using ${percent(fallbackAnnualGrowthRate(form.billType))} annual growth`, value: monthlyBase },
        { label: "Billing period base", formula: "Forecasted amount for the selected billing period", value: monthlyBase },
        { label: "Area-linked billing charge", formula: "billing charge × area ratio × period ratio", value: areaCharge },
        { label: "Predicted CGST", formula: "(present CGST / present amount) × taxable base", value: predictedCgst },
        { label: "Predicted SGST", formula: "(present SGST / present amount) × taxable base", value: predictedSgst },
        { label: "Scheduled formula taxes", formula: formulaSchedule, value: totalFormulaTax },
        { label: "Final predicted bill", formula: "base + area charge + CGST + SGST + formula taxes", value: finalPrice },
      ];

  return {
    finalPrice,
    baseAmount: monthlyBase,
    modelRaw: forecast.raw,
    modelLogR2: manifest?.metrics.r2_log ?? 0,
    modelRawR2: manifest?.metrics.r2_raw ?? 0,
    formulaSchedule,
    nrvConstant,
    totalFormulaTax,
    taxItems,
    forecastPath: forecast.path,
    formulaSteps,
    source,
    billType: form.billType,
    fallbackReason: source === "offline-fallback"
      ? !model || !manifest
        ? "The local model artifact was unavailable, so compound growth was used."
        : "This bill type is outside the rent model's training scope, so compound growth was used."
      : "",
  };
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
}

function Metric({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "neutral" | "accent" }) {
  return (
    <div className={`metric metric-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function Home() {
  const [model, setModel] = useState<XgbModel | null>(null);
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [modelError, setModelError] = useState("");
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [error, setError] = useState("");
  const [showRates, setShowRates] = useState(false);
  const [query, setQuery] = useState("");
  const [querySummary, setQuerySummary] = useState("");

  useEffect(() => {
    Promise.all([
      fetch("/billing_xgb_model.json").then((response) => {
        if (!response.ok) throw new Error("Model artifact could not be loaded.");
        return response.json() as Promise<XgbModel>;
      }),
      fetch("/billing_model_manifest.json").then((response) => {
        if (!response.ok) throw new Error("Model manifest could not be loaded.");
        return response.json() as Promise<Manifest>;
      }),
    ])
      .then(([loadedModel, loadedManifest]) => {
        setModel(loadedModel);
        setManifest(loadedManifest);
      })
      .catch((reason: Error) => setModelError(reason.message));
  }, []);

  const modelReady = Boolean(model && manifest);
  const predictionReady = true;
  function updateNumber(key: keyof FormState, event: ChangeEvent<HTMLInputElement>) {
    setForm((current) => ({ ...current, [key]: numberValue(event.target.value) }));
  }

  function applyExpandedQuery(expanded: ExpandedQuery) {
    setForm((current) => ({
      ...current,
      ...(expanded.targetYear ? { targetYear: expanded.targetYear } : {}),
      ...(expanded.targetMonth ? { targetMonth: expanded.targetMonth } : {}),
      ...(expanded.currentBaselineAmount !== undefined ? { amount: expanded.currentBaselineAmount } : {}),
      ...(expanded.billType ? {
        billType: expanded.billType,
        lineCategory: expanded.billType === "additional_rent" ? "additional_rent" : "rent",
      } : {}),
    }));
    setQuerySummary([
      expanded.billType ? `bill type: ${expanded.billType.replace("_", " ")}` : "bill type: existing selection",
      expanded.targetYear ? `target year: ${expanded.targetYear}` : "target year: existing selection",
      expanded.targetMonth ? `target month: ${expanded.targetMonth}` : "target month: existing selection",
      expanded.currentBaselineAmount !== undefined ? `baseline: ${currency(expanded.currentBaselineAmount)}` : "baseline: existing selection",
    ].join(" · "));
  }

  function handleUseQuery() {
    setError("");
    const expanded = expandPredictionQuery(query);
    if (!expanded.isPrediction) {
      setQuerySummary("");
      setError("This is not routed as a future billing prediction. Existing RAG/PDF/SQL handling can process it.");
      return;
    }
    applyExpandedQuery(expanded);
  }

  function runPrediction() {
    setError("");
    let calculationForm = form;
    if (query.trim()) {
      const expanded = expandPredictionQuery(query);
      if (!expanded.isPrediction) {
        setError("This is not routed as a future billing prediction. Existing RAG/PDF/SQL handling can process it.");
        return;
      }
      calculationForm = {
        ...form,
        ...(expanded.targetYear ? { targetYear: expanded.targetYear } : {}),
        ...(expanded.targetMonth ? { targetMonth: expanded.targetMonth } : {}),
        ...(expanded.currentBaselineAmount !== undefined ? { amount: expanded.currentBaselineAmount } : {}),
        ...(expanded.billType ? {
          billType: expanded.billType,
          lineCategory: expanded.billType === "additional_rent" ? "additional_rent" : "rent",
        } : {}),
      };
      applyExpandedQuery(expanded);
    }
    try {
      setPrediction(calculatePrediction(model, manifest, calculationForm));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not calculate this prediction.");
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark">BF</div>
          <div>
            <p className="eyebrow">BILLING FORECAST LAB</p>
            <p className="brand-subtitle">Model + formula audit</p>
          </div>
        </div>
        <div className="status-pill">
          <span className={`status-dot ${predictionReady ? "status-ready" : ""}`} />
          {modelReady ? "Local XGBoost ready" : "Offline fallback ready"}
        </div>
      </header>

      <section className="hero-grid">
        <div className="hero-copy">
          <p className="eyebrow accent-text">FORECAST BEFORE THE INVOICE</p>
          <h1>See the price. Trace every rupee.</h1>
          <p className="hero-lede">
            A browser-ready billing forecast powered by the historical dataset, then grounded in the supplied tax formulas line by line.
          </p>
          <div className="hero-metrics">
            <Metric label="Log-space R²" value={manifest ? percent(manifest.metrics.r2_log) : "—"} tone="accent" />
            <Metric label="Raw-currency R²" value={manifest ? percent(manifest.metrics.r2_raw) : "—"} />
            <Metric label="Validation rows" value={manifest ? plainNumber(manifest.metrics.n) : "—"} />
          </div>
          <div className="method-note">
            <span className="note-index">01</span>
            <div>
              <strong>How to read the score</strong>
              <p>
                The 88.9% score is R² on the positive log billing target, which is appropriate for this heavily skewed price distribution. Raw rupee R² is shown beside it without hiding the difference.
              </p>
            </div>
          </div>
        </div>

        <section className="input-card" aria-labelledby="inputs-title">
          <div className="card-heading">
            <div>
              <p className="eyebrow">INPUTS</p>
              <h2 id="inputs-title">Present bill → target bill</h2>
            </div>
            <button className="ghost-button" type="button" onClick={() => setForm(DEFAULT_FORM)}>Reset</button>
          </div>
          <div className="query-box">
            <div className="query-box-heading"><div><p className="eyebrow">CHAT ROUTER</p><strong>Ask the prediction module</strong></div><span className="query-route-badge">LOCAL NLP</span></div>
            <div className="query-row"><input aria-label="Future billing prediction question" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") handleUseQuery(); }} placeholder="What will my rent be in 2029? Current amount ₹14,000" /><button className="ghost-button query-button" type="button" onClick={handleUseQuery}>Use query</button></div>
            <p className="query-hint">Offline entity extraction finds the bill type, target date, and baseline amount. No LLM, PostgreSQL, or internet connection is required.</p>
            {querySummary ? <p className="query-summary">Routed to prediction · {querySummary}</p> : null}
          </div>
          <div className="section-label">Present bill details</div>
          <div className="field-grid two-col">
            <Field label="Present year"><input type="number" value={form.year} onChange={(event) => updateNumber("year", event)} /></Field>
            <Field label="Present month"><input type="number" min="1" max="12" value={form.month} onChange={(event) => updateNumber("month", event)} /></Field>
            <Field label="Base amount" hint="₹ / current billing base"><input type="number" min="0" value={form.amount} onChange={(event) => updateNumber("amount", event)} /></Field>
            <Field label="Billing charge" hint="current-period area-linked amount"><input type="number" min="0" value={form.billingCharge} onChange={(event) => updateNumber("billingCharge", event)} /></Field>
            <Field label="CGST"><input type="number" min="0" value={form.cgst} onChange={(event) => updateNumber("cgst", event)} /></Field>
            <Field label="SGST"><input type="number" min="0" value={form.sgst} onChange={(event) => updateNumber("sgst", event)} /></Field>
            <Field label="Area"><input type="number" min="0" value={form.area} onChange={(event) => updateNumber("area", event)} /></Field>
            <Field label="Area billed"><select value={form.areaBillPer} onChange={(event) => setForm((current) => ({ ...current, areaBillPer: event.target.value as FormState["areaBillPer"] }))}><option value="monthly">Monthly</option><option value="half_yearly">Half-yearly</option><option value="yearly">Yearly</option></select></Field>
          </div>

          <div className="section-label target-label">Target prediction</div>
          <div className="field-grid two-col">
            <Field label="Target year"><input type="number" value={form.targetYear} onChange={(event) => updateNumber("targetYear", event)} /></Field>
            <Field label="Target month"><input type="number" min="1" max="12" value={form.targetMonth} onChange={(event) => updateNumber("targetMonth", event)} /></Field>
            <Field label="Bill type"><select value={form.billType} onChange={(event) => setForm((current) => ({ ...current, billType: event.target.value as FormState["billType"] }))}><option value="rent">Rent</option><option value="additional_rent">Additional rent</option><option value="electricity">Electricity</option><option value="water">Water</option><option value="tax">Tax</option></select></Field>
            <Field label="Base line"><select value={form.lineCategory} onChange={(event) => setForm((current) => ({ ...current, lineCategory: event.target.value as FormState["lineCategory"] }))}><option value="rent">Rent</option><option value="additional_rent">Additional rent</option></select></Field>
            <Field label="Structure"><select value={form.structureType} onChange={(event) => setForm((current) => ({ ...current, structureType: event.target.value as FormState["structureType"] }))}><option value="other">Other structure · 0.792</option><option value="mbpt">MbPT structure · 0.837</option></select></Field>
          </div>
          <label className="checkbox-row"><input type="checkbox" checked={form.waterTaxIncluded} onChange={(event) => setForm((current) => ({ ...current, waterTaxIncluded: event.target.checked }))} /><span>Include water component in Property Tax</span></label>

          <button className="run-button" type="button" onClick={runPrediction} disabled={!predictionReady}>Run prediction <span>→</span></button>
          {error ? <div className="error-box">{error}</div> : null}
          {modelError ? <div className="offline-note">{modelError} Offline compound growth remains available.</div> : null}

          <button className="rate-toggle" type="button" onClick={() => setShowRates((current) => !current)}>{showRates ? "Hide" : "Edit"} formula rates <span>{showRates ? "−" : "+"}</span></button>
          {showRates ? <div className="rate-grid">{(Object.keys(form.rates) as Array<keyof FormState["rates"]>).map((key) => <label className="rate-field" key={key}><span>{RATE_LABELS[key]}</span><div><input type="number" step="0.01" value={form.rates[key]} onChange={(event) => setForm((current) => ({ ...current, rates: { ...current.rates, [key]: numberValue(event.target.value) } }))} /><small>%</small></div></label>)}</div> : <p className="rate-note">Rates start with the worked example from the supplied formula sheet. Replace them with your master-record rates for production billing.</p>}
        </section>
      </section>

      <section className="results-section" aria-live="polite">
        <div className="results-heading"><div><p className="eyebrow">PREDICTION OUTPUT</p><h2>{prediction ? "Audited target bill" : "Your calculation will appear here"}</h2></div>{prediction ? <span className="schedule-badge">{prediction.formulaSchedule}</span> : null}</div>
        {prediction ? <div className="results-grid">
           <div className="total-card"><div className="total-kicker">Final predicted billing price</div><div className="total-value">{currency(prediction.finalPrice)}</div><div className="total-caption">{prediction.source === "xgboost" ? "Local XGBoost + formula layer" : `Offline compound-growth fallback · ${prediction.fallbackReason}`}</div><div className="score-row"><span>Bill type <strong>{prediction.billType.replace("_", " ")}</strong></span><span>{prediction.source === "xgboost" ? "Model log-R²" : "Fallback rate"} <strong>{prediction.source === "xgboost" ? percent(prediction.modelLogR2) : percent(fallbackAnnualGrowthRate(prediction.billType))}</strong></span></div></div>
          <div className="breakdown-card"><div className="breakdown-head"><h3>What drives the result</h3><span>₹</span></div><div className="breakdown-row"><span>Predicted monthly base</span><strong>{currency(prediction.baseAmount)}</strong></div><div className="breakdown-row"><span>Area-linked charge</span><strong>{currency(prediction.formulaSteps.find((step) => step.label === "Area-linked billing charge")?.value ?? 0)}</strong></div><div className="breakdown-row"><span>CGST + SGST</span><strong>{currency((prediction.formulaSteps.find((step) => step.label === "Predicted CGST")?.value ?? 0) + (prediction.formulaSteps.find((step) => step.label === "Predicted SGST")?.value ?? 0))}</strong></div><div className="breakdown-row"><span>Formula taxes</span><strong className={prediction.totalFormulaTax < 0 ? "negative-value" : ""}>{currency(prediction.totalFormulaTax)}</strong></div><div className="breakdown-total"><span>Final</span><strong>{currency(prediction.finalPrice)}</strong></div></div>
        </div> : <div className="empty-result"><div className="empty-orbit">→</div><p>Enter the present bill and target month, then run the model. The next panel will show the ML forecast, all six rateable values, and the exact scheduled tax formulas.</p></div>}
      </section>

      {prediction ? <>
        <section className="audit-section"><div className="section-intro"><p className="eyebrow">CALCULATION TRACE</p><h2>Prediction, unpacked</h2><p>Every stage is visible. The model predicts the base amount; the rest is deterministic arithmetic from the formula sheet.</p></div><div className="audit-table"><div className="audit-table-head"><span>Step</span><span>Formula / logic</span><span>Value</span></div>{prediction.formulaSteps.map((step, index) => <div className={`audit-row ${index === prediction.formulaSteps.length - 1 ? "audit-final" : ""}`} key={step.label}><span className="step-number">{String(index + 1).padStart(2, "0")}</span><span><strong>{step.label}</strong><small>{step.formula}</small></span><strong>{currency(step.value)}</strong></div>)}</div></section>
        <section className="lower-grid"><div className="forecast-card"><div className="card-heading"><div><p className="eyebrow">MODEL PATH</p><h3>Month-by-month forecast</h3></div><span className="mini-tag">log1p → expm1</span></div><div className="mini-table"><div className="mini-table-head"><span>Target period</span><span>Model output</span><span>Base amount</span></div>{prediction.forecastPath.slice(-8).map((point) => <div className="mini-table-row" key={`${point.year}-${point.month}`}><span>{point.year}-{String(point.month).padStart(2, "0")}</span><span>{point.raw.toFixed(4)}</span><strong>{currency(point.amount)}</strong></div>)}</div></div><div className="tax-card"><div className="card-heading"><div><p className="eyebrow">FORMULA LAYER</p><h3>{prediction.formulaSchedule}</h3></div><span className="mini-tag">Const {prediction.nrvConstant}</span></div>{prediction.taxItems.length ? prediction.taxItems.map((item) => <div className="tax-row" key={item.label}><div><strong>{item.label}</strong><small>{item.formula}</small></div><strong className={item.value < 0 ? "negative-value" : ""}>{currency(item.value)}</strong></div>) : <div className="no-tax">This target month is not one of the formula-sheet billing months, so scheduled formula taxes are zero.</div>}<div className="tax-total"><span>Total formula taxes</span><strong className={prediction.totalFormulaTax < 0 ? "negative-value" : ""}>{currency(prediction.totalFormulaTax)}</strong></div></div></section>
      </> : null}

      <footer className="footer-note"><span>Sources</span><span>Billing CSV · Tax_Formulas_Expanded.md · XGBoost model artifact</span><span>Deterministic formula layer</span></footer>
    </main>
  );
}
