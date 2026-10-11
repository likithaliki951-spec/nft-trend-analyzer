"""Tests for extended valuation categories, SVR/GRU machine learning models, and API clients."""

import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from api_clients import (
    clear_api_cache,
    convert_eth_to_usd,
    get_current_eth_usd_price,
    get_opensea_collection_stats,
)
from ml_models import (
    GRUHybridTimeSeriesRegressor,
    NumpyGRUCell,
    check_gru_data_sufficiency,
    evaluate_extended_models,
)
from valuation_categories import (
    UNSOLD_LABEL,
    categorize_prices,
    compute_category_distribution,
    evaluate_valuation_classifiers,
    predict_single_valuation,
    validate_valuation_bands,
)


# ==============================================================================
# Valuation Categories Tests
# ==============================================================================


def test_validate_valuation_bands_validates_contiguous_non_overlapping():
    valid_bands = [
        ("Tier 1", 0.0, 50.0),
        ("Tier 2", 50.0, 500.0),
        ("Tier 3", 500.0, float("inf")),
    ]
    assert validate_valuation_bands(valid_bands) is True

    # Gap between 50 and 60
    with pytest.raises(ValueError, match="Gap or overlap detected"):
        validate_valuation_bands([("Tier 1", 0.0, 50.0), ("Tier 2", 60.0, 100.0)])

    # Negative bounds
    with pytest.raises(ValueError, match="negative"):
        validate_valuation_bands([("Tier Neg", -10.0, 50.0)])


def test_categorize_prices_respects_unsold_missing_and_zero():
    prices = pd.Series([0.0, 5.0, 50.0, np.nan, 250000.0])
    is_sold = pd.Series([True, True, True, False, True])

    cats = categorize_prices(prices, is_sold=is_sold, currency="USD")
    assert cats.iloc[0] == "$0–$10"
    assert cats.iloc[1] == "$0–$10"
    assert cats.iloc[2] == "$10–$100"
    assert cats.iloc[3] == UNSOLD_LABEL
    assert cats.iloc[4] == "$100,000+"


def test_categorize_prices_converts_eth_to_usd_with_rate():
    eth_prices = pd.Series([0.01, 0.5, 2.0])  # at $2,000/ETH: $20, $1,000, $4,000
    cats = categorize_prices(eth_prices, currency="ETH", eth_usd_rate=2000.0)
    assert cats.iloc[0] == "$10–$100"
    assert cats.iloc[1] == "$1,000–$10,000"
    assert cats.iloc[2] == "$1,000–$10,000"

    with pytest.raises(ValueError, match="positive eth_usd_rate"):
        categorize_prices(eth_prices, currency="ETH", eth_usd_rate=None)


def test_compute_category_distribution_counts_percentages():
    cats = pd.Series(["$0–$10", "$0–$10", "$10–$100", UNSOLD_LABEL])
    dist = compute_category_distribution(cats)
    assert len(dist) == 3
    assert set(dist.columns) == {"Valuation Category", "Count", "Percentage"}
    assert dist.loc[dist["Valuation Category"] == "$0–$10", "Count"].iloc[0] == 2
    assert dist.loc[dist["Valuation Category"] == "$0–$10", "Percentage"].iloc[0] == pytest.approx(50.0)


def test_evaluate_valuation_classifiers_fits_rf_and_svm():
    dates = pd.date_range("2024-01-01", periods=50, freq="D")
    # Generate prices spanning multiple categories
    prices = 5.0 + np.arange(50) * 25.0  # prices range from $5 to $1230
    df = pd.DataFrame({"date": dates, "price": prices})

    results = evaluate_valuation_classifiers(df, "date", "price", currency="USD")
    assert set(results["metrics"]) == {"Random Forest Classifier", "Support Vector Classifier (SVM)"}
    assert results["training_rows"] > results["test_rows"] >= 2
    for model_name, m in results["metrics"].items():
        assert 0.0 <= m["Accuracy"] <= 1.0
        assert 0.0 <= m["Macro F1"] <= 1.0
        assert results["confusion_matrices"][model_name].shape[0] == len(results["classes"])

    # Test single-asset prediction
    rf_pipe = results["trained_pipelines"]["Random Forest Classifier"]
    features_list = results["features"]
    sample_feat = {f: 1.0 for f in features_list}
    single_res = predict_single_valuation(rf_pipe, sample_feat, features_list)
    assert "predicted_category" in single_res
    assert "disclaimer" in single_res


# ==============================================================================
# Advanced ML: SVR and GRU Hybrid Model Tests
# ==============================================================================


def test_check_gru_data_sufficiency():
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    target = pd.Series(np.arange(10, dtype=float))
    ok, msg = check_gru_data_sufficiency(dates, target, min_sequence_rows=20)
    assert ok is False
    assert "Insufficient sequential records" in msg

    dates_long = pd.date_range("2024-01-01", periods=30, freq="D")
    target_long = pd.Series(np.arange(30, dtype=float))
    ok_long, msg_long = check_gru_data_sufficiency(dates_long, target_long, min_sequence_rows=20)
    assert ok_long is True


def test_numpy_gru_cell_forward():
    cell = NumpyGRUCell(input_dim=1, hidden_dim=4, seed=42)
    seq = np.array([[0.5], [1.0], [1.5]])
    h_T = cell.forward_sequence(seq)
    assert h_T.shape == (4,)
    assert np.all(np.isfinite(h_T))


def test_gru_hybrid_regressor_fit_and_predict():
    rng = np.random.default_rng(42)
    y_train = np.linspace(1.0, 10.0, 20) + rng.normal(0, 0.1, 20)
    x_tab = np.ones((20, 3))

    model = GRUHybridTimeSeriesRegressor(window_size=3, hidden_dim=4, seed=42)
    model.fit(y_train, x_tab)
    assert model.fitted_ is True

    # Predict test indices
    test_idx = np.array([16, 17, 18, 19])
    preds = model.predict(y_train, x_tab, test_idx)
    assert len(preds) == 4
    assert np.all(np.isfinite(preds))


def test_evaluate_extended_models_includes_svr_and_gru():
    dates = pd.date_range("2024-01-01", periods=40, freq="D")
    df = pd.DataFrame(
        {
            "date": dates,
            "price": 10.0 + np.sin(np.arange(40) / 4) * 3.0 + np.arange(40) * 0.1,
        }
    )
    res = evaluate_extended_models(df, "date", "price")
    assert "Linear Regression" in res["metrics"]
    assert "Random Forest" in res["metrics"]
    assert "Support Vector Regressor (SVR)" in res["metrics"]
    assert "GRU Hybrid Model" in res["metrics"]

    # All metrics valid
    for model_name, m in res["metrics"].items():
        assert m["MAE"] >= 0.0
        assert m["RMSE"] >= 0.0


# ==============================================================================
# API Clients Tests
# ==============================================================================


def test_opensea_handles_missing_api_key_gracefully():
    with patch.dict("os.environ", {}, clear=True):
        res = get_opensea_collection_stats("boredapeyachtclub")
        assert res["status"] == "no_credentials"
        assert "guide" in res


def test_opensea_handles_success_response():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "name": "Bored Ape Yacht Club",
        "description": "BAYC NFT collection",
        "floor_price": 18.5,
        "total_supply": 10000,
    }

    with patch.dict("os.environ", {"OPENSEA_API_KEY": "test_key_123"}):
        with patch("requests.get", return_value=mock_response):
            res = get_opensea_collection_stats("boredapeyachtclub")
            assert res["status"] == "success"
            assert res["name"] == "Bored Ape Yacht Club"
            assert res["floor_price"] == 18.5


def test_coingecko_eth_price_mock_and_caching():
    clear_api_cache()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ethereum": {"usd": 2650.0}}

    with patch("requests.get", return_value=mock_response):
        res = get_current_eth_usd_price()
        assert res["status"] == "success"
        assert res["rate_usd"] == 2650.0


def test_convert_eth_to_usd_handles_fallback():
    # When APIs are offline, returns benchmark fallback with clear estimation flag
    with patch("api_clients.get_historical_eth_usd_price", return_value={"status": "not_found"}):
        with patch("api_clients.get_current_eth_usd_price", return_value={"status": "network_error"}):
            conv = convert_eth_to_usd(2.0)
            assert conv["usd_amount"] == 5200.0
            assert conv["is_estimate"] is True
