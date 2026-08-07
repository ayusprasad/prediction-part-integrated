"""Train the billing forecaster and export a browser-readable XGBoost artifact.

The exported model predicts log1p(base_amount). The browser reverses that transform
with expm1, then applies the tax formulas deterministically.
"""

from pathlib import Path
import json

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor


ROOT = Path(__file__).resolve().parent
DATA_PATH = Path(r'C:/Users/kumar/Desktop/dataset/billing_training_dataset.csv')
FORMULA_PATH = Path(r'C:/Users/kumar/Downloads/Tax_Formulas_Expanded.md')
PUBLIC_DIR = ROOT / 'frontend' / 'public'
MODEL_PATH = PUBLIC_DIR / 'billing_xgb_model.json'
MANIFEST_PATH = PUBLIC_DIR / 'billing_model_manifest.json'
RANDOM_STATE = 42
VALIDATION_CUTOFF = 2025 * 12 + 1

REQUIRED_COLUMNS = [
    'src_customerid', 'src_billyearmonth', 'src_billchargeid', 'src_amount',
    'src_sgst', 'src_cgst', 'src_area_in_sqm', 'src_unit', 'src_month', 'src_year',
    'dim_bill_head_name', 'dim_bill_head_category',
    'dim_property_bill_periodicity', 'dim_latest_area', 'dim_letout_billable_area',
]

BASE_FEATURES = [
    'present_amount', 'present_cgst', 'present_sgst', 'present_area',
    'present_year', 'present_month', 'target_year', 'target_month',
    'horizon_months', 'present_amount_per_area', 'present_log_amount',
    'billing_frequency', 'line_category',
]


def normalize_frequency(value) -> str:
    text = str(value).strip().lower().replace('-', '_').replace(' ', '_')
    aliases = {
        'monthly': 'monthly', 'month': 'monthly',
        'yearly': 'yearly', 'annual': 'yearly', 'annually': 'yearly',
        'half_yearly': 'half_yearly', 'halfyearly': 'half_yearly',
        'half_annually': 'half_yearly', 'semi_annual': 'half_yearly',
        'semiannual': 'half_yearly',
    }
    return aliases.get(text, 'monthly')


def load_data() -> pd.DataFrame:
    header = pd.read_csv(DATA_PATH, nrows=0)
    missing = sorted(set(REQUIRED_COLUMNS) - set(header.columns))
    if missing:
        raise ValueError(f'Missing dataset columns: {missing}')
    data = pd.read_csv(DATA_PATH, usecols=REQUIRED_COLUMNS, low_memory=False)
    numeric = [
        'src_customerid', 'src_billyearmonth', 'src_billchargeid', 'src_amount',
        'src_sgst', 'src_cgst', 'src_area_in_sqm', 'src_unit', 'src_month', 'src_year',
        'dim_latest_area', 'dim_letout_billable_area',
    ]
    for column in numeric:
        data[column] = pd.to_numeric(data[column], errors='coerce')
    data = data.dropna(subset=['src_customerid', 'src_billyearmonth', 'src_amount']).copy()
    data['src_billyearmonth'] = data['src_billyearmonth'].astype(int)
    data['period_year'] = data['src_billyearmonth'] // 100
    data['period_month'] = data['src_billyearmonth'] % 100
    data = data[data['period_month'].between(1, 12)].copy()
    data['period_index'] = data['period_year'] * 12 + data['period_month']
    data['amount'] = data['src_amount'].astype(float)
    data['cgst'] = data['src_cgst'].fillna(0).astype(float)
    data['sgst'] = data['src_sgst'].fillna(0).astype(float)
    data['area'] = data['src_area_in_sqm']
    data['area'] = data['area'].combine_first(data['dim_latest_area'])
    data['area'] = data['area'].combine_first(data['dim_letout_billable_area'])
    data['area'] = data['area'].fillna(0).clip(lower=0)
    category = data['dim_bill_head_category'].fillna('').astype(str)
    name = data['dim_bill_head_name'].fillna('').astype(str)
    text = (category + ' ' + name).str.lower()
    conditions = [
        text.str.contains('mecess|education cess', regex=True),
        text.str.contains('tree cess|treecess', regex=True),
        text.str.contains('water benefit|wbt', regex=True),
        text.str.contains('sewerage benefit|sbt', regex=True),
        text.str.contains('employee guarantee|egcess', regex=True),
        text.str.contains('street tax', regex=True),
        text.str.contains(r'prop\.tax|property tax', regex=True),
        text.str.contains('rent|licence|license', regex=True),
        text.str.contains('7a|additional rent', regex=True),
    ]
    choices = [
        'mecess', 'tree_cess', 'wbt', 'sbt', 'egcess', 'street_tax',
        'property_tax', 'rent', 'additional_rent',
    ]
    data['line_category'] = np.select(conditions, choices, default='other')
    data['billing_frequency'] = data['dim_property_bill_periodicity'].map(normalize_frequency)
    return data[data['line_category'].isin({'rent', 'additional_rent'}) & (data['amount'] > 0)].copy()


def build_pairs(data: pd.DataFrame) -> pd.DataFrame:
    area_median = float(data['area'].replace(0, np.nan).median())
    area_median = area_median if np.isfinite(area_median) else 0.0

    def stable_mode(values):
        values = values.dropna().astype(str)
        return values.mode().iloc[0] if not values.empty else 'monthly'

    monthly = (
        data.groupby(['src_customerid', 'line_category', 'period_index'], as_index=False, dropna=False)
        .agg(
            present_amount=('amount', 'sum'),
            present_cgst=('cgst', 'sum'),
            present_sgst=('sgst', 'sum'),
            present_area=('area', 'median'),
            billing_frequency=('billing_frequency', stable_mode),
        )
        .sort_values(['src_customerid', 'line_category', 'period_index'])
        .reset_index(drop=True)
    )
    grouped = monthly.groupby(['src_customerid', 'line_category'], sort=False)
    monthly['target_amount'] = grouped['present_amount'].shift(-1)
    monthly['target_period_index'] = grouped['period_index'].shift(-1)
    monthly['horizon_months'] = monthly['target_period_index'] - monthly['period_index']
    monthly = monthly[monthly['target_amount'].notna() & (monthly['horizon_months'] > 0)].copy()
    monthly['present_year'] = ((monthly['period_index'] - 1) // 12).astype(int)
    monthly['present_month'] = ((monthly['period_index'] - 1) % 12 + 1).astype(int)
    monthly['target_year'] = ((monthly['target_period_index'] - 1) // 12).astype(int)
    monthly['target_month'] = ((monthly['target_period_index'] - 1) % 12 + 1).astype(int)
    monthly['present_area'] = monthly['present_area'].fillna(area_median).clip(lower=0)
    monthly['present_amount_per_area'] = (
        monthly['present_amount'] / monthly['present_area'].replace(0, np.nan)
    ).replace([np.inf, -np.inf], np.nan).fillna(0)
    monthly['present_log_amount'] = np.log1p(monthly['present_amount'].clip(lower=0))
    monthly['target_amount'] = pd.to_numeric(monthly['target_amount'], errors='coerce')
    return monthly[monthly['target_amount'] > 0].copy()


def make_features(frame: pd.DataFrame) -> pd.DataFrame:
    features = frame[BASE_FEATURES].copy()
    return pd.get_dummies(features, columns=['billing_frequency', 'line_category'], dtype=float)


def make_model() -> XGBRegressor:
    return XGBRegressor(
        n_estimators=400,
        max_depth=7,
        learning_rate=0.04,
        min_child_weight=5,
        subsample=0.9,
        colsample_bytree=0.95,
        reg_alpha=0.05,
        reg_lambda=3.0,
        objective='reg:squarederror',
        eval_metric='rmse',
        tree_method='hist',
        n_jobs=1,
        random_state=RANDOM_STATE,
    )


def metrics(actual, predicted) -> dict:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    return {
        'mae': float(mean_absolute_error(actual, predicted)),
        'rmse': float(np.sqrt(mean_squared_error(actual, predicted))),
        'r2_raw': float(r2_score(actual, predicted)),
        'r2_log': float(r2_score(np.log1p(actual), np.log1p(predicted.clip(min=0)))),
        'smape_percent': float(np.mean(2 * np.abs(predicted - actual) / (np.abs(actual) + np.abs(predicted) + 1e-12)) * 100),
        'n': int(len(actual)),
    }


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(DATA_PATH)
    if not FORMULA_PATH.exists():
        raise FileNotFoundError(FORMULA_PATH)
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    pairs = build_pairs(load_data())
    train = pairs[pairs['target_period_index'] < VALIDATION_CUTOFF].copy()
    test = pairs[pairs['target_period_index'] >= VALIDATION_CUTOFF].copy()
    x_train = make_features(train)
    x_test = make_features(test).reindex(columns=x_train.columns, fill_value=0.0)
    validation_model = make_model()
    validation_model.fit(
        x_train,
        np.log1p(train['target_amount']),
        eval_set=[(x_test, np.log1p(test['target_amount']))],
        verbose=False,
    )
    predicted = np.expm1(validation_model.predict(x_test)).clip(min=0)
    report = metrics(test['target_amount'], predicted)
    report['validation_cutoff'] = '2025-01'
    report['training_pairs'] = int(len(train))
    report['total_pairs'] = int(len(pairs))
    report['feature_count'] = int(x_train.shape[1])
    report['model'] = 'XGBRegressor on log1p(base_amount)'
    report['formula_source'] = str(FORMULA_PATH)

    production_model = make_model()
    x_all = make_features(pairs).reindex(columns=x_train.columns, fill_value=0.0)
    production_model.fit(x_all, np.log1p(pairs['target_amount']), verbose=False)
    production_model.save_model(MODEL_PATH)
    manifest = {
        'feature_columns': list(x_train.columns),
        'base_features': BASE_FEATURES,
        'metrics': report,
        'model_transform': 'prediction = expm1(raw_model_prediction)',
        'training_data': str(DATA_PATH),
        'formula_data': str(FORMULA_PATH),
        'xgboost_params': production_model.get_xgb_params(),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, default=str), encoding='utf-8')
    print(json.dumps(report, indent=2))
    print(f'Wrote {MODEL_PATH}')
    print(f'Wrote {MANIFEST_PATH}')


if __name__ == '__main__':
    main()
