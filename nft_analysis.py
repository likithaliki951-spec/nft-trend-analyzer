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


DATE_TERMS = (
    "date",
    "time",
    "timestamp",
    "created_at",
    "sold_at",
    "block_time",
    "datetime",
    "tx_time",
    "tx_date",
    "day",
    "period",
    "transacted_at",
)
PRICE_TERMS = (
    "price",
    "amount",
    "sale_value",
    "floor",
    "floor_price",
    "last_sale",
    "eth_price",
    "usd_price",
    "cost",
    "value",
)
SALES_TERMS = (
    "sales",
    "sale_count",
    "transactions",
    "trades",
    "volume",
    "num_sales",
    "tx_count",
    "trade_count",
    "quantity",
    "tokens_sold",
)
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
    "upvote",
    "tweet",
    "post",
    "favorite",
    "subscriber",
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
ASSET_IDENTIFIER_TERMS = (
    "token_id",
    "tokenid",
    "asset_id",
    "item_id",
    "nft_id",
    "token",
    "item",
    "asset",
    "collection",
    "name",
    "title",
    "contract",
)


def clean_dataframe(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Trim labels/strings, normalize blanks, and remove empty or duplicate rows."""
    if dataframe.empty or len(dataframe.columns) == 0:
        return dataframe.copy(), {
            "rows_before_cleaning": len(dataframe),
            "empty_rows_removed": 0,
            "duplicate_rows_removed": 0,
        }

    original_rows = len(dataframe)
    cleaned = dataframe.copy()
    cleaned.columns = [
        str(column).strip().replace("\r", "").replace("\n", "").replace("\t", "") or f"unnamed_{i}"
        for i, column in enumerate(cleaned.columns)
    ]

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
    """Convert currency-formatted strings, scientific notation, percentages, and tokens to numbers."""
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_numeric(values, errors="coerce")
    text = values.astype("string").str.strip()
    # Strip currency symbols and thousands commas
    text = text.str.replace(r"[$€£₹,]", "", regex=True)
    # Strip leading or trailing crypto/fiat ticker tokens
    text = text.str.replace(r"^\s*(?:WETH|ETH|BTC|SOL|USD|USDT)\s*", "", case=False, regex=True)
    text = text.str.replace(r"\s*(?:WETH|ETH|BTC|SOL|USD|USDT)\s*$", "", case=False, regex=True)
    # Strip trailing percentage signs
    text = text.str.replace(r"%\s*$", "", regex=True)
    # Convert accounting parentheses for negative numbers, e.g. "(12.5)" -> "-12.5"
    paren_mask = text.str.startswith("(") & text.str.endswith(")")
    if paren_mask.any():
        text = text.where(~paren_mask, "-" + text.str[1:-1].str.strip())
    return pd.to_numeric(text, errors="coerce")


def parse_dates(values: pd.Series) -> pd.Series:
    """Parse date-like values as timezone-naive UTC timestamps, supporting ISO strings and Unix epochs."""
    # Check if series is numeric and looks like Unix timestamps (seconds or milliseconds)
    if pd.api.types.is_numeric_dtype(values):
        valid_num = values.dropna()
        if not valid_num.empty:
            median_val = float(valid_num.median())
            if 1e9 <= median_val <= 2.5e9:  # Epoch seconds (approx 2001 - 2049)
                return pd.to_datetime(values, unit="s", errors="coerce", utc=True).dt.tz_convert(None)
            elif 1e12 <= median_val <= 2.5e12:  # Epoch milliseconds
                return pd.to_datetime(values, unit="ms", errors="coerce", utc=True).dt.tz_convert(None)
        return pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
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
        normalized = str(column).lower().replace(" ", "_").replace("-", "_")
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
    results["feature_importances"] = {}
    results["linear_coefficients"] = {}
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
        regressor = model.named_steps["model"]
        if hasattr(regressor, "feature_importances_"):
            results["feature_importances"] = {
                feat: float(imp)
                for feat, imp in zip(features.columns, regressor.feature_importances_)
            }
        elif hasattr(regressor, "coef_"):
            results["linear_coefficients"] = {
                feat: float(coef)
                for feat, coef in zip(features.columns, regressor.coef_)
            }

    results["residuals"] = {
        m: (y_test.to_numpy() - preds)
        for m, preds in results["predictions"].items()
    }
    results["train_dates"] = dates.iloc[:split_index].reset_index(drop=True)
    return results


def count_unique_assets(dataframe: pd.DataFrame) -> tuple[int | None, str | None]:
    """Identify the primary asset/NFT or collection column and return (unique_count, column_name)."""
    for term in ASSET_IDENTIFIER_TERMS:
        for column in dataframe.columns:
            normalized = str(column).lower().replace(" ", "_")
            if (
                term == normalized
                or normalized.startswith(f"{term}_")
                or normalized.endswith(f"_{term}")
                or term in normalized
            ):
                valid_count = int(dataframe[column].dropna().nunique())
                if valid_count > 0:
                    return valid_count, str(column)
    return None, None


def compute_market_kpis(
    dataframe: pd.DataFrame, price_column: str | None, sales_column: str | None
) -> dict[str, Any]:
    """Compute verified market KPIs, trading volume support check, and data-quality diagnostics."""
    kpis: dict[str, Any] = {
        "valid_records": len(dataframe),
        "avg_price": None,
        "median_price": None,
        "min_price": None,
        "max_price": None,
        "volume_supported": False,
        "total_volume": None,
        "volume_method": None,
        "quality_warnings": [],
    }

    if price_column and price_column in dataframe:
        prices = parse_numeric(dataframe[price_column])
        valid_prices = prices.dropna()
        if not valid_prices.empty:
            kpis["avg_price"] = float(valid_prices.mean())
            kpis["median_price"] = float(valid_prices.median())
            kpis["min_price"] = float(valid_prices.min())
            kpis["max_price"] = float(valid_prices.max())

            missing_pct = float(prices.isna().mean() * 100)
            if missing_pct > 10.0:
                kpis["quality_warnings"].append(
                    f"High missingness in '{price_column}': {missing_pct:.1f}% of rows have missing or unparseable price values."
                )
            neg_count = int((valid_prices < 0).sum())
            if neg_count > 0:
                kpis["quality_warnings"].append(
                    f"Found {neg_count} negative value(s) in '{price_column}'. NFT prices should typically be non-negative."
                )

    if sales_column and sales_column in dataframe:
        norm_sales = str(sales_column).lower().replace(" ", "_")
        sales_numeric = parse_numeric(dataframe[sales_column])
        valid_sales = sales_numeric.dropna()
        if not valid_sales.empty:
            if "volume" in norm_sales:
                kpis["volume_supported"] = True
                kpis["total_volume"] = float(valid_sales.sum())
                kpis["volume_method"] = f"Direct sum of '{sales_column}'"
            elif price_column and price_column in dataframe:
                prices = parse_numeric(dataframe[price_column])
                valid_pairs = prices.notna() & sales_numeric.notna() & np.isfinite(prices) & np.isfinite(sales_numeric)
                if valid_pairs.any():
                    kpis["volume_supported"] = True
                    kpis["total_volume"] = float((prices.loc[valid_pairs] * sales_numeric.loc[valid_pairs]).sum())
                    kpis["volume_method"] = f"Estimated as Price ('{price_column}') × Sales ('{sales_column}')"

    return kpis


def compute_engagement_correlations(
    dataframe: pd.DataFrame, social_columns: list[str], target_columns: list[str]
) -> pd.DataFrame:
    """Compute Pearson correlation between engagement metrics and price/sales metrics."""
    rows: list[dict[str, Any]] = []
    for social in social_columns:
        if social not in dataframe:
            continue
        s_vals = parse_numeric(dataframe[social])
        for target in target_columns:
            if not target or target not in dataframe:
                continue
            t_vals = parse_numeric(dataframe[target])
            valid = s_vals.notna() & t_vals.notna() & np.isfinite(s_vals) & np.isfinite(t_vals)
            count = int(valid.sum())
            if count >= 3:
                s_valid = s_vals.loc[valid].to_numpy(dtype=float)
                t_valid = t_vals.loc[valid].to_numpy(dtype=float)
                if np.std(s_valid) > 1e-9 and np.std(t_valid) > 1e-9:
                    r = float(np.corrcoef(s_valid, t_valid)[0, 1])
                    rows.append(
                        {
                            "Engagement Metric": social,
                            "Market Metric": target,
                            "Pearson Correlation": round(r, 4),
                            "Observations": count,
                        }
                    )
    return pd.DataFrame(rows)


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
