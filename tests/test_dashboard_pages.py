from pathlib import Path

from streamlit.testing.v1 import AppTest

from nft_analysis import make_synthetic_demo_data


def test_all_five_dashboard_pages_render():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=45)
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
    }
    for page, heading in pages.items():
        app.radio[0].set_value(page).run()
        assert not app.exception, f"{page} raised a Streamlit exception"
        assert any(element.value == heading for element in app.header), (
            f"{page} did not render its expected page heading"
        )
