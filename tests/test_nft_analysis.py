import numpy as np
import pandas as pd
import pytest

from nft_analysis import (
    build_time_features,
    clean_dataframe,
    compute_engagement_correlations,
    compute_market_kpis,
    count_unique_assets,
    evaluate_models,
    infer_column,
    parse_dates,
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


def test_count_unique_assets_identifies_token_and_collection_columns():
    df = pd.DataFrame(
        {
            "token_id": ["#1", "#2", "#3", "#1"],
            "collection": ["Punk A", "Punk A", "Punk B", "Punk A"],
        }
    )
    count, col = count_unique_assets(df)
    assert count == 3
    assert col == "token_id"

    # Fallback to collection if no token_id exists
    df_no_token = pd.DataFrame({"collection": ["Col A", "Col B", "Col A"]})
    count2, col2 = count_unique_assets(df_no_token)
    assert count2 == 2
    assert col2 == "collection"


def test_compute_market_kpis_calculates_price_statistics_and_volume():
    df = pd.DataFrame(
        {
            "price_eth": [1.0, 2.0, 3.0, 4.0],
            "sales_count": [2, 1, 3, 2],
        }
    )
    kpis = compute_market_kpis(df, "price_eth", "sales_count")
    assert kpis["avg_price"] == pytest.approx(2.5)
    assert kpis["median_price"] == pytest.approx(2.5)
    assert kpis["min_price"] == pytest.approx(1.0)
    assert kpis["max_price"] == pytest.approx(4.0)
    assert kpis["volume_supported"] is True
    # 1*2 + 2*1 + 3*3 + 4*2 = 2 + 2 + 9 + 8 = 21
    assert kpis["total_volume"] == pytest.approx(21.0)


def test_compute_engagement_correlations_computes_pearson_r():
    df = pd.DataFrame(
        {
            "price": [1.0, 2.0, 3.0, 4.0, 5.0],
            "likes": [10.0, 20.0, 30.0, 40.0, 50.0],
        }
    )
    corr = compute_engagement_correlations(df, ["likes"], ["price"])
    assert len(corr) == 1
    assert corr.iloc[0]["Engagement Metric"] == "likes"
    assert corr.iloc[0]["Market Metric"] == "price"
    assert corr.iloc[0]["Pearson Correlation"] == pytest.approx(1.0)
    assert corr.iloc[0]["Observations"] == 5


def test_clean_dataframe_handles_empty_dataframe_and_newlines_in_headers():
    empty_df = pd.DataFrame()
    cleaned, stats = clean_dataframe(empty_df)
    assert cleaned.empty
    assert stats["rows_before_cleaning"] == 0

    df_newlines = pd.DataFrame({"sale_date\n": ["2024-01-01"], "\tprice\r": [2.5]})
    cleaned_nl, _ = clean_dataframe(df_newlines)
    assert list(cleaned_nl.columns) == ["sale_date", "price"]


def test_parse_numeric_handles_accounting_parentheses_percentages_and_tickers():
    series = pd.Series(["(25.50)", "15.0%", "ETH 3.75", "4.20 WETH", "$1,000.00"])
    parsed = parse_numeric(series)
    assert parsed.iloc[0] == pytest.approx(-25.50)
    assert parsed.iloc[1] == pytest.approx(15.0)
    assert parsed.iloc[2] == pytest.approx(3.75)
    assert parsed.iloc[3] == pytest.approx(4.20)
    assert parsed.iloc[4] == pytest.approx(1000.0)


def test_parse_dates_handles_epoch_timestamps():
    # Unix timestamp for 2024-01-01 00:00:00 UTC is 1704067200
    epoch_seconds = pd.Series([1704067200, 1704153600])
    parsed_s = parse_dates(epoch_seconds)
    assert parsed_s.dt.year.iloc[0] == 2024
    assert parsed_s.dt.month.iloc[0] == 1
    assert parsed_s.dt.day.iloc[0] == 1

    # Milliseconds
    epoch_ms = pd.Series([1704067200000, 1704153600000])
    parsed_ms = parse_dates(epoch_ms)
    assert parsed_ms.dt.year.iloc[0] == 2024


def test_infer_column_handles_expanded_terms():
    df = pd.DataFrame(
        {
            "tx_date": ["2024-01-01"],
            "floor_price": [1.2],
            "num_sales": [10],
            "upvotes": [150],
        }
    )
    assert infer_column(df, "date") == "tx_date"
    assert infer_column(df, "price") == "floor_price"
    assert infer_column(df, "sales") == "num_sales"
    assert infer_column(df, "social") == "upvotes"
