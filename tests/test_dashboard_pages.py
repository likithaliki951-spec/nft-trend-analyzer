from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from auth import AUTH_SESSION_KEY, create_session_token
from nft_analysis import make_synthetic_demo_data

MOCK_CG = {"status": "success", "rate_usd": 2800.0, "source": "Mock Live", "timestamp": "2026-10-31T00:00:00Z"}
MOCK_OS = {"status": "success", "floor_price_eth": 15.0, "total_supply": 10000, "retrieval_time": "2026-10-31T00:00:00Z"}


def test_all_seven_dashboard_pages_render():
    with patch("api_clients.get_current_eth_usd_price", return_value=MOCK_CG), \
         patch("api_clients.get_opensea_collection_stats", return_value=MOCK_OS):
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=45)
        app.session_state[AUTH_SESSION_KEY] = create_session_token("analyst@nfttrends.io", "Senior Analyst")
        app.session_state["dataset"] = make_synthetic_demo_data()
        app.session_state["dataset_signature"] = "synthetic-dashboard-test"
        app.session_state["dataset_source"] = "Synthetic educational demo"
        app.session_state["cleaning_stats"] = {
            "duplicate_rows_removed": 0,
            "empty_rows_removed": 0,
        }
        app.session_state["date_col"] = "sale_date"
        app.session_state["price_col"] = "price_eth"
        app.session_state["sales_col"] = "sales_count"
        app.run()

        pages = {
            "NFT Market Overview": "NFT Market Overview",
            "Time-Series Analysis": "Time-Series Analysis",
            "Social-Media Engagement": "Social-Media Engagement Analysis",
            "Price Prediction": "Price Prediction",
            "Model Evaluation": "Model Evaluation",
            "Valuation Categories": "NFT Valuation Categories",
            "Live Market Intelligence": "Live Market Intelligence & Currency Hub",
        }
        for page, heading in pages.items():
            nav_radio = next(r for r in app.radio if r.label == "Dashboard pages")
            nav_radio.set_value(page).run()
            assert not app.exception, f"{page} raised a Streamlit exception: {app.exception}"
            assert any(element.value == heading for element in app.header), (
                f"{page} did not render its expected page heading: {heading}"
            )


def test_dashboard_with_pca_and_join_diagnostics():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=45)
    app.session_state[AUTH_SESSION_KEY] = create_session_token("analyst@nfttrends.io", "Senior Analyst")
    app.session_state["dataset"] = make_synthetic_demo_data()
    app.session_state["dataset_signature"] = "synthetic-dashboard-test"
    app.session_state["dataset_source"] = "Synthetic educational demo"
    app.session_state["date_col"] = "sale_date"
    app.session_state["price_col"] = "price_eth"
    app.session_state["sales_col"] = "sales_count"
    app.session_state["join_diagnostics"] = {
        "join_key": "collection",
        "join_type": "inner",
        "market_rows": 100,
        "social_rows": 100,
        "joined_rows": 95,
        "matched_records": 95,
        "unmatched_market_records": 5,
        "unmatched_social_records": 5,
        "warnings": [],
    }
    app.run()
    assert not app.exception

    # 1. NFT Market Overview with join diagnostics
    nav_radio = next(r for r in app.radio if r.label == "Dashboard pages")
    nav_radio.set_value("NFT Market Overview").run()
    assert not app.exception

    # 2. Valuation Categories with 3 classifiers
    nav_radio.set_value("Valuation Categories").run()
    assert not app.exception

    # 3. Price Prediction with PCA enabled
    nav_radio.set_value("Price Prediction").run()
    assert not app.exception
    pca_checkbox = next((c for c in app.checkbox if "PCA" in getattr(c, "label", "")), None)
    if pca_checkbox:
        pca_checkbox.check().run()
        assert not app.exception


def test_dashboard_work_history_and_admin_views():
    """Verify that Work History and Admin Console navigation render properly without errors."""
    with patch("api_clients.get_current_eth_usd_price", return_value=MOCK_CG), \
         patch("api_clients.get_opensea_collection_stats", return_value=MOCK_OS):
        app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=45)
        app.session_state[AUTH_SESSION_KEY] = create_session_token("admin@nfttrends.io", "Administrator", role="admin")
        app.run()
        assert not app.exception

        # Switch to Work History
        section_radio = next(r for r in app.radio if r.label == "Navigation")
        for opt in section_radio.options:
            if "My Work" in opt:
                section_radio.set_value(opt).run()
                break
        assert not app.exception
        assert any("My Work" in str(h.value) for h in app.header)

        # Switch to Admin Console
        section_radio = next(r for r in app.radio if r.label == "Navigation")
        for opt in section_radio.options:
            if "Admin" in opt:
                section_radio.set_value(opt).run()
                break
        assert not app.exception
        assert any("Administrator" in str(h.value) for h in app.header)
