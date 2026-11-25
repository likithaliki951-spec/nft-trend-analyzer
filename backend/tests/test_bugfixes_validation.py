"""Comprehensive validation test for the 3 bug fixes:
1. Analytical charts data pipeline & key mappings.
2. Gradient Boosting & Ridge Regression ML prediction lines.
3. OpenSea Collection Intelligence stats per-collection updating.
"""

import os
import sys
import numpy as np
import pytest

# Ensure backend app is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.analysis_service import AnalysisService
from app.services.ml_service import MLService
from app.services.marketplace_service import MarketplaceService, COLLECTION_BENCHMARKS


def test_issue_1_analytical_charts_data_pipeline():
    """Verify time series aggregation, rolling averages, volume fields, and collection breakdown."""
    demo_df = AnalysisService.get_demo_dataset(150)
    assert not demo_df.empty, "Demo dataset must not be empty"

    ts_data = AnalysisService.get_time_series_data(demo_df)
    assert len(ts_data) > 0, "Time-series data must contain aggregated daily rows"

    for pt in ts_data:
        assert "date" in pt
        assert "price" in pt
        assert "price_avg" in pt
        assert "price_ma7" in pt
        assert "price_7d_ma" in pt
        assert "sales_count" in pt
        assert "total_sales" in pt
        assert "total_volume" in pt
        assert pt["price"] > 0
        assert pt["price_ma7"] > 0
        assert pt["sales_count"] >= 0

    # Verify 7-day moving average calculation:
    # First point MA equals point 1; subsequent points smooth towards mean
    prices = [p["price"] for p in ts_data]
    ma7s = [p["price_ma7"] for p in ts_data]
    assert ma7s[0] == pytest.approx(prices[0], rel=1e-3)
    if len(prices) >= 7:
        expected_7th_ma = float(np.mean(prices[:7]))
        assert ma7s[6] == pytest.approx(expected_7th_ma, rel=1e-3)

    # Verify Market KPIs Collection Breakdown
    kpis = AnalysisService.get_market_kpis(demo_df)
    assert "collection_breakdown" in kpis
    cb = kpis["collection_breakdown"]
    assert len(cb) > 0
    for item in cb:
        assert "collection" in item
        assert "total_volume" in item
        assert isinstance(item["collection"], str)
        assert item["total_volume"] > 0


def test_issue_2_ml_gradient_boosting_and_ridge_regression():
    """Verify that Random Forest, Gradient Boosting, and Ridge Regression all fit, predict, and appear."""
    demo_df = AnalysisService.get_demo_dataset(120)
    ml_res = MLService.train_price_models(demo_df, use_pca=True, target_pca_components=60, test_size=0.2)

    assert "models" in ml_res
    model_names = [m["model_name"] for m in ml_res["models"]]
    assert "Random Forest" in model_names
    assert "Gradient Boosting" in model_names
    assert "Ridge Regression" in model_names

    # Check metrics for each model
    for m in ml_res["models"]:
        assert m["rmse"] >= 0.0
        assert m["mae"] >= 0.0
        assert np.isfinite(m["rmse"])

    # Check out-of-sample test predictions
    test_preds = ml_res["actual_vs_predicted_sample"]
    assert len(test_preds) > 0, "Out-of-sample test predictions must not be empty"

    required_keys = ["index", "actual", "Random Forest", "Gradient Boosting", "Ridge Regression"]
    for i, pt in enumerate(test_preds):
        for k in required_keys:
            assert k in pt, f"Missing key {k} in test sample {i}"
            assert pt[k] is not None, f"Key {k} is None in sample {i}"
            assert np.isfinite(pt[k]), f"Key {k} is non-finite/NaN in sample {i}"

    # Verify that predictions from all models are distinct and not all identical copies
    rf_preds = [pt["Random Forest"] for pt in test_preds]
    gb_preds = [pt["Gradient Boosting"] for pt in test_preds]
    ridge_preds = [pt["Ridge Regression"] for pt in test_preds]
    actuals = [pt["actual"] for pt in test_preds]

    assert len(rf_preds) == len(gb_preds) == len(ridge_preds) == len(actuals)
    # The models use different loss functions/algorithms, so their predictions should not be 100% identical
    assert not np.allclose(rf_preds, ridge_preds), "RF and Ridge predictions must be distinct"
    assert not np.allclose(gb_preds, ridge_preds), "GB and Ridge predictions must be distinct"


def test_issue_3_opensea_collection_stats_updating():
    """Verify that selecting different collections produces distinct, collection-specific statistics."""
    collections = [
        "boredapeyachtclub",
        "cryptopunks",
        "mutant-ape-yacht-club",
        "azuki",
        "pudgypenguins",
        "doodles-official",
    ]

    all_stats = {}
    for slug in collections:
        stats = MarketplaceService.get_collection_stats(slug)
        all_stats[slug] = stats

        assert stats["slug"] == slug
        assert stats["name"] is not None and len(stats["name"]) > 0
        assert stats["contract"].startswith("0x")
        assert stats["floor_price_eth"] > 0
        assert stats["total_supply"] > 0
        assert stats["total_volume_eth"] > 0
        assert stats["implied_market_cap_eth"] > 0
        assert stats["implied_market_cap_usd"] > 0
        assert "source" in stats

    # Verify that each collection has distinct floor prices
    floors = {slug: s["floor_price_eth"] for slug, s in all_stats.items()}
    assert floors["boredapeyachtclub"] != floors["cryptopunks"]
    assert floors["cryptopunks"] != floors["mutant-ape-yacht-club"]
    assert floors["azuki"] != floors["pudgypenguins"]
    assert floors["pudgypenguins"] != floors["doodles-official"]

    # Verify supplies
    assert all_stats["pudgypenguins"]["total_supply"] == 8888
    assert all_stats["mutant-ape-yacht-club"]["total_supply"] == 19500
    assert all_stats["boredapeyachtclub"]["total_supply"] == 10000

    # Verify contracts
    contracts = [s["contract"] for s in all_stats.values()]
    assert len(set(contracts)) == len(collections), "Every collection must have a unique contract address"

    # Verify USD math consistency
    eth_rate = MarketplaceService.get_eth_price()["rate_usd"]
    for slug, s in all_stats.items():
        expected_eth_cap = round(s["floor_price_eth"] * s["total_supply"], 2)
        assert s["implied_market_cap_eth"] == pytest.approx(expected_eth_cap, rel=1e-2)
        expected_usd_cap = round(expected_eth_cap * eth_rate, 2)
        assert s["implied_market_cap_usd"] == pytest.approx(expected_usd_cap, rel=1e-2)
