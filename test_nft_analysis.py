import numpy as np
import pandas as pd
import pytest

from nft_analysis import (
    build_time_features,
    clean_dataframe,
    evaluate_models,
    infer_column,
    parse_numeric,
)


def test_clean_dataframe_trims_headers_and_drops_empty_and_duplicate_rows():
    source = pd.DataFrame(
        {
            " sale_date ": [" 2024-01-01 ", " 2024-01-01 ", "   "],
            " price_eth ": [" 1.25 ", " 1.25 ", " "],
        }
    )

    cleaned, stats = clean_dataframe(source)

    assert list(cleaned.columns) == ["sale_date", "price_eth"]
    assert len(cleaned) == 1
    assert stats["duplicate_rows_removed"] == 1
    assert stats["empty_rows_removed"] == 1


def test_parse_numeric_handles_currency_commas_and_eth_suffix():
    values = pd.Series(["$1,250.50 ETH", "0.75", "not available"])

    parsed = parse_numeric(values)

    assert parsed.iloc[0] == pytest.approx(1250.5)
    assert parsed.iloc[1] == pytest.approx(0.75)
    assert pd.isna(parsed.iloc[2])


def test_infer_column_suggests_date_and_price_from_headers():
    dataframe = pd.DataFrame({"sold_at": ["2025-01-01"], "floor_price": [1.0]})

    assert infer_column(dataframe, "date") == "sold_at"
    assert infer_column(dataframe, "price") == "floor_price"


def test_features_are_ordered_and_use_only_prior_target_values():
    dataframe = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=20, freq="D")[::-1],
            "price": np.arange(20, dtype=float)[::-1],
            "social_likes": np.arange(100, 120, dtype=float)[::-1],
        }
    )

    features, target, dates = build_time_features(dataframe, "date", "price")

    assert dates.is_monotonic_increasing
    assert target.iloc[0] == pytest.approx(2.0)
    assert features.loc[0, "target_lag_1"] == pytest.approx(1.0)
    assert features.loc[0, "target_lag_2"] == pytest.approx(0.0)
    assert features.loc[0, "prior_social_likes"] == pytest.approx(101.0)
    assert "price" not in features.columns


def test_evaluate_models_returns_both_scores_on_later_test_period():
    dates = pd.date_range("2024-01-01", periods=50, freq="D")
    dataframe = pd.DataFrame(
        {
            "date": dates,
            "price": 1 + np.arange(50) * 0.02 + np.sin(np.arange(50) / 5) * 0.1,
            "sales_count": 10 + np.arange(50) % 7,
        }
    )

    results = evaluate_models(dataframe, "date", "price")

    assert set(results["metrics"]) == {"Linear Regression", "Random Forest"}
    assert results["training_rows"] > results["test_rows"] >= 2
    assert results["split_date"] > dates[0]
    assert len(results["actual"]) == results["test_rows"]
    for model_metrics in results["metrics"].values():
        assert set(model_metrics) == {"MAE", "RMSE", "R²"}
        assert model_metrics["MAE"] >= 0
        assert model_metrics["RMSE"] >= 0
        assert np.isfinite(model_metrics["R²"])


def test_model_evaluation_explains_insufficient_data():
    dataframe = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=8, freq="D"),
            "price": np.arange(8, dtype=float),
        }
    )

    with pytest.raises(ValueError, match="At least 12 rows"):
        evaluate_models(dataframe, "date", "price")
