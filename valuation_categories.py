"""NFT valuation categorization, boundary validation, and classification modeling."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from nft_analysis import build_time_features, parse_numeric


# Standard valuation bands in USD
DEFAULT_VALUATION_BANDS: list[tuple[str, float, float]] = [
    ("$0–$10", 0.0, 10.0),
    ("$10–$100", 10.0, 100.0),
    ("$100–$1,000", 100.0, 1000.0),
    ("$1,000–$10,000", 1000.0, 10000.0),
    ("$10,000–$100,000", 10000.0, 100000.0),
    ("$100,000+", 100000.0, float("inf")),
]
UNSOLD_LABEL = "Unsold / No Observed Sale"


def validate_valuation_bands(bands: list[tuple[str, float, float]]) -> bool:
    """Validate that price bands are sorted, non-overlapping, and cover contiguous ranges."""
    if not bands:
        raise ValueError("Valuation bands cannot be empty.")

    for i, (name, low, high) in enumerate(bands):
        if low < 0 or high < 0:
            raise ValueError(f"Band '{name}' has negative bounds ({low}, {high}).")
        if low >= high:
            raise ValueError(f"Band '{name}' lower bound {low} must be strictly less than upper bound {high}.")
        if i > 0:
            prev_high = bands[i - 1][2]
            if not np.isclose(low, prev_high) and low != prev_high:
                raise ValueError(
                    f"Gap or overlap detected between '{bands[i - 1][0]}' (ends {prev_high}) "
                    f"and '{name}' (starts {low})."
                )
    return True


def categorize_prices(
    prices: pd.Series,
    is_sold: pd.Series | None = None,
    currency: str = "USD",
    eth_usd_rate: float | None = None,
    bands: list[tuple[str, float, float]] | None = None,
) -> pd.Series:
    """Assign observed prices into validated valuation categories without confounding unsold/zero/missing values.

    Parameters:
    - prices: Numeric series of observed NFT prices.
    - is_sold: Optional boolean series indicating whether an asset actually completed a sale.
    - currency: 'USD' or 'ETH'. If 'ETH', eth_usd_rate is applied.
    - eth_usd_rate: Exchange rate used only when converting ETH prices to USD.
    - bands: List of (name, lower_bound, upper_bound) tuples.
    """
    active_bands = bands or DEFAULT_VALUATION_BANDS
    validate_valuation_bands(active_bands)

    parsed_prices = parse_numeric(prices)
    if currency.upper() == "ETH":
        if eth_usd_rate is None or eth_usd_rate <= 0:
            raise ValueError("A positive eth_usd_rate is required when converting ETH-denominated prices to USD.")
        usd_prices = parsed_prices * eth_usd_rate
    else:
        usd_prices = parsed_prices

    categories = pd.Series(index=prices.index, dtype="object")

    # If is_sold is explicitly provided, mark unsold assets
    if is_sold is not None:
        unsold_mask = ~is_sold.astype(bool)
        categories.loc[unsold_mask] = UNSOLD_LABEL

    # Categorize valid prices
    for name, low, high in active_bands:
        if np.isneginf(high) or np.isposinf(high):
            mask = (usd_prices >= low) & categories.isna()
        else:
            mask = (usd_prices >= low) & (usd_prices < high) & categories.isna()
        categories.loc[mask] = name

    # Remaining missing prices (not previously marked unsold) become UNSOLD_LABEL
    categories = categories.fillna(UNSOLD_LABEL)
    return categories


def compute_category_distribution(categories: pd.Series) -> pd.DataFrame:
    """Return category counts, percentages, and class imbalance metrics."""
    counts = categories.value_counts(dropna=False).rename("Count").reset_index()
    counts.columns = ["Valuation Category", "Count"]
    total = len(categories)
    counts["Percentage"] = ((counts["Count"] / total) * 100).round(2) if total > 0 else 0.0
    return counts


def evaluate_valuation_classifiers(
    dataframe: pd.DataFrame,
    date_column: str,
    target_column: str,
    currency: str = "USD",
    eth_usd_rate: float | None = None,
) -> dict[str, Any]:
    """Train Random Forest and Support Vector Machine classifiers on valuation categories using strict chronological 80/20 split."""
    # 1. Feature engineering (leakage-safe time-ordered features)
    features, target_numeric, dates = build_time_features(dataframe, date_column, target_column)

    # 2. Assign categorical targets
    target_categories = categorize_prices(
        target_numeric,
        currency=currency,
        eth_usd_rate=eth_usd_rate if currency.upper() == "ETH" else None,
    )

    # Need at least two distinct classes to evaluate classification
    unique_classes = sorted(list(target_categories.unique()))
    if len(unique_classes) < 2:
        raise ValueError(
            f"Classification requires at least 2 distinct valuation categories in the dataset. "
            f"Found only 1 category: {unique_classes}."
        )

    # 3. Chronological 80/20 train/test split
    split_index = int(len(features) * 0.8)
    if split_index < 4 or len(features) - split_index < 2:
        raise ValueError("Too few usable observations for chronological train/test classification split.")

    x_train, x_test = features.iloc[:split_index], features.iloc[split_index:]
    y_train, y_test = target_categories.iloc[:split_index], target_categories.iloc[split_index:]
    test_dates = dates.iloc[split_index:]

    # Class distribution
    train_dist = y_train.value_counts().to_dict()
    test_dist = y_test.value_counts().to_dict()

    # Define model factories
    classifier_factories = {
        "Random Forest Classifier": lambda: Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("model", RandomForestClassifier(n_estimators=200, random_state=42, class_weight="balanced", n_jobs=-1)),
            ]
        ),
        "Support Vector Classifier (SVM)": lambda: Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
                ("model", CalibratedClassifierCV(SVC(kernel="rbf", class_weight="balanced", random_state=42), ensemble=False)),
            ]
        ),
    }

    results: dict[str, Any] = {
        "metrics": {},
        "predictions": {},
        "probabilities": {},
        "confusion_matrices": {},
        "actual": y_test.reset_index(drop=True),
        "dates": test_dates.reset_index(drop=True),
        "classes": unique_classes,
        "features": list(features.columns),
        "training_rows": len(x_train),
        "test_rows": len(x_test),
        "split_date": test_dates.iloc[0],
        "train_distribution": train_dist,
        "test_distribution": test_dist,
        "per_class_reports": {},
        "trained_pipelines": {},
    }

    for model_name, factory in classifier_factories.items():
        pipeline = factory()
        pipeline.fit(x_train, y_train)
        preds = pipeline.predict(x_test)
        results["predictions"][model_name] = preds
        results["trained_pipelines"][model_name] = pipeline

        # Probabilities if available
        if hasattr(pipeline.named_steps["model"], "predict_proba"):
            probs = pipeline.predict_proba(x_test)
            results["probabilities"][model_name] = probs

        # Metrics
        acc = float(accuracy_score(y_test, preds))
        bal_acc = float(balanced_accuracy_score(y_test, preds))
        macro_p = float(precision_score(y_test, preds, average="macro", zero_division=0))
        macro_r = float(recall_score(y_test, preds, average="macro", zero_division=0))
        macro_f1 = float(f1_score(y_test, preds, average="macro", zero_division=0))
        weighted_f1 = float(f1_score(y_test, preds, average="weighted", zero_division=0))

        results["metrics"][model_name] = {
            "Accuracy": acc,
            "Balanced Accuracy": bal_acc,
            "Macro Precision": macro_p,
            "Macro Recall": macro_r,
            "Macro F1": macro_f1,
            "Weighted F1": weighted_f1,
        }

        # Confusion Matrix
        cm = confusion_matrix(y_test, preds, labels=unique_classes)
        results["confusion_matrices"][model_name] = cm

        # Per-class classification report
        rep = classification_report(y_test, preds, labels=unique_classes, output_dict=True, zero_division=0)
        results["per_class_reports"][model_name] = rep

    return results


def predict_single_valuation(
    pipeline: Pipeline,
    feature_values: dict[str, float],
    feature_names: list[str],
) -> dict[str, Any]:
    """Perform single-asset valuation category prediction with class probabilities and limitations warning."""
    input_vector = pd.DataFrame([[feature_values.get(f, 0.0) for f in feature_names]], columns=feature_names)
    predicted_class = str(pipeline.predict(input_vector)[0])

    probs_dict = {}
    if hasattr(pipeline.named_steps["model"], "predict_proba"):
        probs = pipeline.predict_proba(input_vector)[0]
        classes = pipeline.named_steps["model"].classes_
        probs_dict = {str(c): float(p) for c, p in zip(classes, probs)}

    return {
        "predicted_category": predicted_class,
        "class_probabilities": probs_dict,
        "disclaimer": (
            "Model estimate only: Classification probability reflects resemblance to historical training patterns, "
            "not a guaranteed transaction price or liquidity commitment."
        ),
    }
