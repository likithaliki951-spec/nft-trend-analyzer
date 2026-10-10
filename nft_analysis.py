"""Data cleaning, feature engineering, and leakage-safe model evaluation."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


DATE_TERMS = ("date", "time", "timestamp", "created_at", "sold_at", "block_time")
PRICE_TERMS = ("price", "amount", "sale_value", "floor")
SALES_TERMS = ("sales", "sale_count", "transactions", "trades", "volume")
SOCIAL_TERMS = (
    "like",
    "comment",
    "reply",
    "retweet",
    "share",
    "follower",
    "impression",
    "view",
    "engagement",
    "mention",
)
USEFUL_LAG_TERMS = (
    "social",
    "like",
    "comment",
    "reply",
    "retweet",
    "share",
    "follower",
    "impression",
    "view",
    "engagement",
    "mention",
    "sale",
    "volume",
    "trade",
    "transaction",
    "rarity",
    "rank",
    "floor",
)
IDENTIFIER_TERMS = ("_id", "tokenid", "contract", "address", "hash", "index")


def clean_dataframe(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Trim labels/strings, normalize blanks, and remove empty or duplicate rows."""
    original_rows = len(dataframe)
    cleaned = dataframe.copy()
    cleaned.columns = [str(column).strip() or f"unnamed_{i}" for i, column in enumerate(cleaned.columns)]

    # Duplicate header names make column selection ambiguous. Preserve each field
    # while assigning deterministic, human-readable suffixes.
    seen: dict[str, int] = {}
    unique_columns: list[str] = []
    for column in cleaned.columns:
        seen[column] = seen.get(column, 0) + 1
        unique_columns.append(column if seen[column] == 1 else f"{column}_{seen[column]}")
    cleaned.columns = unique_columns

    for column in cleaned.select_dtypes(include=["object", "string"]).columns:
        values = cleaned[column].map(lambda value: value.strip() if isinstance(value, str) else value)
        cleaned[column] = values.replace("", np.nan)

    cleaned = cleaned.dropna(axis=0, how="all")
    empty_rows_removed = original_rows - len(cleaned)
    before_duplicates = len(cleaned)
    cleaned = cleaned.drop_duplicates().reset_index(drop=True)
    duplicates_removed = before_duplicates - len(cleaned)
    return cleaned, {
        "rows_before_cleaning": original_rows,
        "empty_rows_removed": empty_rows_removed,
        "duplicate_rows_removed": duplicates_removed,
    }


def parse_numeric(values: pd.Series) -> pd.Series:
    """Convert common currency-formatted values to numbers without fabricating values."""
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_numeric(values, errors="coerce")
    text = values.astype("string").str.strip()
    text = text.str.replace(r"[$€£₹,]", "", regex=True)
    text = text.str.replace(r"\s*(?:WETH|ETH|BTC|SOL|USD|USDT)\s*$", "", case=False, regex=True)
    return pd.to_numeric(text, errors="coerce")


def parse_dates(values: pd.Series) -> pd.Series:
    """Parse date-like values as timezone-naive UTC timestamps."""
    parsed = pd.to_datetime(values, errors="coerce", utc=True)
    return parsed.dt.tz_convert(None)


def infer_column(dataframe: pd.DataFrame, kind: str) -> str | None:
    """Suggest a field using its name and, for dates/numbers, its actual values."""
    terms = {
        "date": DATE_TERMS,
        "price": PRICE_TERMS,
        "sales": SALES_TERMS,
        "social": SOCIAL_TERMS,
    }[kind]

    named_matches = []
    for column in dataframe.columns:
        normalized = str(column).lower().replace(" ", "_")
        if any(term in normalized for term in terms):
            named_matches.append(column)
    if named_matches:
        return named_matches[0]

    if kind == "date":
        best_column = None
        best_ratio = 0.8
        for column in dataframe.columns:
            parsed = parse_dates(dataframe[column])
            ratio = float(parsed.notna().mean()) if len(parsed) else 0.0
            if ratio > best_ratio:
                best_column, best_ratio = column, ratio
        return best_column

    return None


def discover_social_columns(dataframe: pd.DataFrame) -> list[str]:
    """Return social/engagement-like numeric fields that can be plotted."""
    columns = []
    for column in dataframe.columns:
        name = str(column).lower().replace(" ", "_")
        if any(term in name for term in SOCIAL_TERMS) and parse_numeric(dataframe[column]).notna().any():
            columns.append(column)
    return columns


def build_time_features(
    dataframe: pd.DataFrame, date_column: str, target_column: str
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Build one-step-ahead features using only known calendar fields and prior rows."""
    if date_column not in dataframe or target_column not in dataframe:
        raise ValueError("Select an available date field and price/target field.")

    dates = parse_dates(dataframe[date_column])
    target = parse_numeric(dataframe[target_column])
    valid = dates.notna() & target.notna() & np.isfinite(target)
    ordered = pd.DataFrame(
        {
            "_date": dates.loc[valid],
            "_target": target.loc[valid],
            "_original_order": np.flatnonzero(valid.to_numpy()),
        }
    ).sort_values(["_date", "_original_order"], kind="stable")
    if len(ordered) < 12:
        raise ValueError(
            "At least 12 rows with both a valid date and numeric target are required "
            "for a chronological train/test comparison."
        )

    original_indices = ordered["_original_order"].to_numpy()
    ordered = ordered.reset_index(drop=True)
    ordered_dates = ordered["_date"]
    ordered_target = ordered["_target"].astype(float)

    features = pd.DataFrame(index=ordered.index)
    features["time_index"] = np.arange(len(ordered), dtype=float)
    features["year"] = ordered_dates.dt.year.astype(float)
    features["month"] = ordered_dates.dt.month.astype(float)
    features["day_of_week"] = ordered_dates.dt.dayofweek.astype(float)
    features["day_of_year"] = ordered_dates.dt.dayofyear.astype(float)
    features["month_sin"] = np.sin(2 * np.pi * features["month"] / 12)
    features["month_cos"] = np.cos(2 * np.pi * features["month"] / 12)
    features["target_lag_1"] = ordered_target.shift(1)
    features["target_lag_2"] = ordered_target.shift(2)
    features["target_rolling_mean_3"] = ordered_target.shift(1).rolling(3, min_periods=2).mean()

    # Other market/social fields are included only as prior-observation values.
    # Same-row values can be unavailable at prediction time and would risk leakage.
    for column in dataframe.columns:
        if column in (date_column, target_column):
            continue
        name = str(column).lower().replace(" ", "_")
        if not any(term in name for term in USEFUL_LAG_TERMS):
            continue
        if any(term in name for term in IDENTIFIER_TERMS):
            continue
        numeric_values = parse_numeric(dataframe[column]).to_numpy(dtype=float, na_value=np.nan)
        prior_values = numeric_values[original_indices]
        if np.isfinite(prior_values).any():
            features[f"prior_{name}"] = pd.Series(prior_values).shift(1)

    # The first two observations cannot have the required price history.
    usable = features.index >= 2
    features = features.loc[usable].replace([np.inf, -np.inf], np.nan).reset_index(drop=True)
    y = ordered_target.loc[usable].reset_index(drop=True)
    evaluation_dates = ordered_dates.loc[usable].reset_index(drop=True)
    return features, y, evaluation_dates


def evaluate_models(
    dataframe: pd.DataFrame, date_column: str, target_column: str
) -> dict[str, Any]:
    """Fit two regressors with a chronological split; never shuffle time-series rows."""
    features, target, dates = build_time_features(dataframe, date_column, target_column)
    split_index = int(len(features) * 0.8)
    if split_index < 2 or len(features) - split_index < 2:
        raise ValueError(
            "There are too few usable observations for at least two training and two test rows."
        )

    x_train, x_test = features.iloc[:split_index], features.iloc[split_index:]
    y_train, y_test = target.iloc[:split_index], target.iloc[split_index:]
    test_dates = dates.iloc[split_index:]

    model_factories = {
        "Linear Regression": lambda: Pipeline(
            [("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler()), ("model", LinearRegression())]
        ),
        "Random Forest": lambda: Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("model", RandomForestRegressor(n_estimators=250, random_state=42, min_samples_leaf=2, n_jobs=-1)),
            ]
        ),
    }

    results: dict[str, Any] = {
        "metrics": {},
        "predictions": {},
        "actual": y_test.reset_index(drop=True),
        "dates": test_dates.reset_index(drop=True),
        "features": list(features.columns),
        "training_rows": len(x_train),
        "test_rows": len(x_test),
        "split_date": test_dates.iloc[0],
    }
    for model_name, factory in model_factories.items():
        model = factory()
        model.fit(x_train, y_train)
        predictions = np.asarray(model.predict(x_test), dtype=float)
        results["predictions"][model_name] = predictions
        results["metrics"][model_name] = {
            "MAE": float(mean_absolute_error(y_test, predictions)),
            "RMSE": float(np.sqrt(mean_squared_error(y_test, predictions))),
            "R²": float(r2_score(y_test, predictions)) if len(y_test) >= 2 else float("nan"),
        }
    return results


def make_synthetic_demo_data(rows: int = 120) -> pd.DataFrame:
    """Generate labeled educational demo rows; these are not real NFT market data."""
    rng = np.random.default_rng(2026)
    dates = pd.date_range("2024-01-01", periods=rows, freq="D")
    trend = np.linspace(0.8, 1.9, rows)
    seasonal = 0.16 * np.sin(np.arange(rows) * 2 * np.pi / 30)
    prices = np.maximum(0.05, trend + seasonal + rng.normal(0, 0.11, rows))
    sales = np.maximum(1, np.rint(22 + 7 * np.sin(np.arange(rows) / 9) + rng.normal(0, 4, rows))).astype(int)
    likes = np.maximum(0, np.rint(110 + 24 * np.sin(np.arange(rows) / 8) + rng.normal(0, 18, rows))).astype(int)
    comments = np.maximum(0, np.rint(18 + 5 * np.sin(np.arange(rows) / 7) + rng.normal(0, 4, rows))).astype(int)
    return pd.DataFrame(
        {
            "sale_date": dates,
            "price_eth": prices.round(4),
            "sales_count": sales,
            "social_likes": likes,
            "social_comments": comments,
            "collection": np.where(np.arange(rows) % 2 == 0, "Demo Collection A", "Demo Collection B"),
        }
    )
