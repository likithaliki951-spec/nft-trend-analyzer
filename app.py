"""Interactive research dashboard for analysis of trending NFT time-series datasets and machine learning."""

from __future__ import annotations

import datetime
import hashlib
import html
import io
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from api_clients import (
    convert_eth_to_usd,
    get_current_eth_usd_price,
    get_historical_eth_usd_price,
    get_opensea_collection_stats,
)
from auth import (
    get_current_user,
    render_user_badge_and_logout,
    require_authentication,
)
from ml_models import evaluate_extended_models
from nft_analysis import (
    clean_dataframe,
    compute_engagement_correlations,
    compute_market_kpis,
    count_unique_assets,
    discover_social_columns,
    infer_column,
    make_synthetic_demo_data,
    parse_dates,
    parse_numeric,
)
from valuation_categories import (
    DEFAULT_VALUATION_BANDS,
    UNSOLD_LABEL,
    categorize_prices,
    compute_category_distribution,
    evaluate_valuation_classifiers,
    predict_single_valuation,
)


PROJECT_TITLE = "Analysis of Trending NFTs Using Time-Series Data and Machine Learning"
PAGE_NAMES = (
    "NFT Market Overview",
    "Time-Series Analysis",
    "Social-Media Engagement",
    "Price Prediction",
    "Model Evaluation",
    "Valuation Categories",
    "Live Market Intelligence",
)
NO_FIELD = "Not selected"

# Plotly dark palette: Violet, Electric Blue, Emerald, Amber, Rose, Indigo
CHART_COLOR_PALETTE = [
    "#8b5cf6",  # Violet
    "#38bdf8",  # Electric Blue
    "#10b981",  # Emerald
    "#f59e0b",  # Amber
    "#f43f5e",  # Rose
    "#6366f1",  # Indigo
    "#a855f7",  # Purple
]

st.set_page_config(
    page_title=PROJECT_TITLE,
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_custom_theme() -> None:
    """Inject restrained, accessible dark-theme styling with violet and electric-blue accents."""
    custom_css = """
    <style>
    /* Overall typography & container smoothing */
    .stApp {
        background-color: #0b0f19;
        color: #f1f5f9;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    /* Restrained KPI card styling */
    .kpi-card {
        background: linear-gradient(135deg, rgba(19, 27, 46, 0.85) 0%, rgba(15, 23, 42, 0.95) 100%);
        border: 1px solid rgba(139, 92, 246, 0.22);
        border-radius: 10px;
        padding: 16px 18px;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
        margin-bottom: 12px;
        transition: border-color 0.2s ease, transform 0.2s ease;
    }
    .kpi-card:hover {
        border-color: rgba(56, 189, 248, 0.4);
    }
    .kpi-title {
        font-size: 0.76rem;
        font-weight: 600;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #f8fafc;
        letter-spacing: -0.02em;
        line-height: 1.2;
    }
    .kpi-subtext {
        font-size: 0.76rem;
        color: #64748b;
        margin-top: 5px;
    }

    /* Status badges & pills */
    .status-pill-demo {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        font-size: 0.75rem;
        font-weight: 600;
        color: #f59e0b;
        background: rgba(245, 158, 11, 0.12);
        border: 1px solid rgba(245, 158, 11, 0.35);
        border-radius: 9999px;
    }
    .status-pill-active {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        font-size: 0.75rem;
        font-weight: 600;
        color: #38bdf8;
        background: rgba(56, 189, 248, 0.12);
        border: 1px solid rgba(56, 189, 248, 0.35);
        border-radius: 9999px;
    }

    /* Research callout cards */
    .research-callout {
        background: rgba(19, 27, 46, 0.75);
        border-left: 3px solid #8b5cf6;
        border-radius: 0 8px 8px 0;
        padding: 12px 16px;
        margin: 12px 0 16px 0;
        font-size: 0.88rem;
        color: #cbd5e1;
        line-height: 1.5;
    }
    .research-callout-warning {
        background: rgba(30, 24, 16, 0.8);
        border-left: 3px solid #f59e0b;
        border-radius: 0 8px 8px 0;
        padding: 12px 16px;
        margin: 12px 0 16px 0;
        font-size: 0.88rem;
        color: #fde68a;
        line-height: 1.5;
    }

    /* Modern empty-state hero container */
    .empty-state-card {
        background: linear-gradient(135deg, rgba(19, 27, 46, 0.9) 0%, rgba(11, 15, 25, 0.95) 100%);
        border: 1px solid rgba(139, 92, 246, 0.25);
        border-radius: 12px;
        padding: 28px;
        margin: 16px 0 24px 0;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
    }
    .empty-state-title {
        font-size: 1.4rem;
        font-weight: 700;
        color: #f8fafc;
        margin-bottom: 8px;
    }
    .empty-state-desc {
        font-size: 0.92rem;
        color: #94a3b8;
        line-height: 1.6;
        margin-bottom: 20px;
    }
    .empty-feature-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 14px;
        margin-top: 16px;
    }
    .empty-feature-item {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 8px;
        padding: 12px 14px;
    }
    .empty-feature-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #e2e8f0;
        margin-bottom: 4px;
    }
    .empty-feature-text {
        font-size: 0.78rem;
        color: #64748b;
        line-height: 1.4;
    }

    /* Sidebar cleanup */
    section[data-testid="stSidebar"] {
        background-color: #0f1626;
        border-right: 1px solid rgba(255, 255, 255, 0.06);
    }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)


def render_kpi(label: str, value: str, subtext: str = "") -> None:
    """Render a restrained, styled KPI card."""
    card_html = f"""
    <div class="kpi-card">
        <div class="kpi-title">{html.escape(label)}</div>
        <div class="kpi-value">{html.escape(value)}</div>
        {f'<div class="kpi-subtext">{html.escape(subtext)}</div>' if subtext else ''}
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def apply_chart_theme(
    fig: go.Figure,
    title: str | None = None,
    xaxis_title: str | None = None,
    yaxis_title: str | None = None,
    height: int = 420,
) -> go.Figure:
    """Apply a unified dark-mode Plotly theme with charcoal/navy backdrop and violet/blue accents."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="#111827",
        font=dict(
            family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
            color="#cbd5e1",
            size=12,
        ),
        title=dict(
            text=f"<b>{title}</b>" if title else None,
            font=dict(color="#f8fafc", size=15),
            x=0.01,
            xanchor="left",
        ) if title else None,
        xaxis=dict(
            title=dict(text=xaxis_title, font=dict(color="#94a3b8", size=12)) if xaxis_title else None,
            gridcolor="rgba(148, 163, 184, 0.08)",
            linecolor="rgba(148, 163, 184, 0.2)",
            tickfont=dict(color="#94a3b8", size=11),
            zeroline=False,
        ),
        yaxis=dict(
            title=dict(text=yaxis_title, font=dict(color="#94a3b8", size=12)) if yaxis_title else None,
            gridcolor="rgba(148, 163, 184, 0.08)",
            linecolor="rgba(148, 163, 184, 0.2)",
            tickfont=dict(color="#94a3b8", size=11),
            zeroline=False,
        ),
        hoverlabel=dict(
            bgcolor="#1e293b",
            bordercolor="rgba(139, 92, 246, 0.5)",
            font=dict(color="#f8fafc", size=12),
        ),
        hovermode="x unified",
        colorway=CHART_COLOR_PALETTE,
        margin=dict(l=50, r=25, t=55 if title else 25, b=45),
        height=height,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#cbd5e1", size=11),
            bgcolor="rgba(0, 0, 0, 0)",
        ),
    )
    return fig


def set_dataset(dataframe: pd.DataFrame, signature: str, source_label: str) -> None:
    cleaned, cleaning_stats = clean_dataframe(dataframe)
    st.session_state["dataset"] = cleaned
    st.session_state["dataset_signature"] = signature
    st.session_state["dataset_source"] = source_label
    st.session_state["cleaning_stats"] = cleaning_stats
    st.session_state["date_col"] = infer_column(cleaned, "date") or NO_FIELD
    st.session_state["price_col"] = infer_column(cleaned, "price") or NO_FIELD
    st.session_state["sales_col"] = infer_column(cleaned, "sales") or NO_FIELD


def field_options(columns: list[str]) -> list[str]:
    return [NO_FIELD, *columns]


def selected_field(key: str) -> str | None:
    value = st.session_state.get(key, NO_FIELD)
    return value if value != NO_FIELD else None


def period_start(dates: pd.Series, frequency: str) -> pd.Series:
    parsed = parse_dates(dates)
    if frequency == "Weekly":
        return parsed.dt.to_period("W").dt.start_time
    if frequency == "Monthly":
        return parsed.dt.to_period("M").dt.start_time
    return parsed.dt.floor("D")


def time_series_data(
    dataframe: pd.DataFrame,
    date_column: str | None,
    value_column: str | None,
    frequency: str,
    aggregation: str,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> pd.DataFrame:
    if not date_column or not value_column:
        return pd.DataFrame()
    dates = parse_dates(dataframe[date_column])
    values = parse_numeric(dataframe[value_column])
    valid = dates.notna() & values.notna() & np.isfinite(values)
    if not valid.any():
        return pd.DataFrame()

    subset_dates = dates.loc[valid]
    subset_values = values.loc[valid].astype(float)

    if start_date:
        mask = subset_dates.dt.date >= start_date
        subset_dates = subset_dates.loc[mask]
        subset_values = subset_values.loc[mask]
    if end_date:
        mask = subset_dates.dt.date <= end_date
        subset_dates = subset_dates.loc[mask]
        subset_values = subset_values.loc[mask]

    if subset_dates.empty:
        return pd.DataFrame()

    chart_data = pd.DataFrame(
        {
            "Period": period_start(subset_dates, frequency).to_numpy(),
            "Value": subset_values.to_numpy(),
        }
    )
    operation = "sum" if aggregation == "sum" else "mean"
    return (
        chart_data.groupby("Period", as_index=False)["Value"]
        .agg(operation)
        .sort_values("Period")
    )


def show_price_chart(
    dataframe: pd.DataFrame,
    date_column: str | None,
    price_column: str | None,
    frequency: str,
    rolling_window: int = 7,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> bool:
    if not date_column:
        st.info("Choose a date/time column to plot prices over time.")
        return False
    if not price_column:
        st.info("Choose a price column in the sidebar to show a price trend.")
        return False
    chart_data = time_series_data(
        dataframe, date_column, price_column, frequency, "mean", start_date, end_date
    )
    if chart_data.empty:
        st.warning("The selected price field has no usable numeric values within the chosen date range.")
        return False

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=chart_data["Period"],
            y=chart_data["Value"],
            mode="lines+markers",
            name="Period average",
            line=dict(color="#38bdf8", width=2),
            marker=dict(size=4),
        )
    )
    if rolling_window > 1 and len(chart_data) >= 2:
        chart_data["Rolling average"] = chart_data["Value"].rolling(rolling_window, min_periods=1).mean()
        fig.add_trace(
            go.Scatter(
                x=chart_data["Period"],
                y=chart_data["Rolling average"],
                mode="lines",
                name=f"{rolling_window}-period rolling average",
                line=dict(color="#8b5cf6", width=2.5, dash="solid"),
            )
        )
    apply_chart_theme(
        fig,
        title=f"NFT Price Trend ({frequency.lower()} average)",
        xaxis_title="Date",
        yaxis_title=f"Average {price_column}",
    )
    st.plotly_chart(fig, width="stretch")
    return True


def show_activity_chart(
    dataframe: pd.DataFrame,
    date_column: str | None,
    sales_column: str | None,
    frequency: str,
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> bool:
    if not date_column:
        st.info("Choose a date/time column to show market activity over time.")
        return False

    if sales_column:
        chart_data = time_series_data(
            dataframe, date_column, sales_column, frequency, "sum", start_date, end_date
        )
        title = f"Recorded {sales_column} by {frequency.lower()} period"
        y_label = f"Recorded {sales_column}"
        note = "This chart sums the selected sales/activity field; it does not add external marketplace data."
    else:
        dates = parse_dates(dataframe[date_column])
        valid_dates = dates.dropna()
        if start_date:
            valid_dates = valid_dates.loc[valid_dates.dt.date >= start_date]
        if end_date:
            valid_dates = valid_dates.loc[valid_dates.dt.date <= end_date]
        if valid_dates.empty:
            st.warning("The selected date/time field contains no valid dates within the chosen range.")
            return False
        chart_data = (
            pd.DataFrame({"Period": period_start(valid_dates, frequency)})
            .groupby("Period")
            .size()
            .rename("Value")
            .reset_index()
            .sort_values("Period")
        )
        title = f"Dataset record activity by {frequency.lower()} period"
        y_label = "Rows in uploaded dataset"
        note = "No sales-count field is selected, so this is a count of uploaded records, not verified sales."
    if chart_data.empty:
        st.warning("The selected activity field has no usable numeric values within the chosen date range.")
        return False
    st.caption(note)
    fig = px.bar(chart_data, x="Period", y="Value")
    fig.update_traces(marker_color="#8b5cf6", marker_line_color="#a78bfa", marker_line_width=1)
    apply_chart_theme(fig, title=title, xaxis_title="Date", yaxis_title=y_label)
    st.plotly_chart(fig, width="stretch")
    return True


def inspect_table(dataframe: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Column": [str(column) for column in dataframe.columns],
            "Detected type": [str(dataframe[column].dtype) for column in dataframe.columns],
            "Missing values": [int(dataframe[column].isna().sum()) for column in dataframe.columns],
            "Missing (%)": [
                round(float(dataframe[column].isna().mean() * 100), 1) for column in dataframe.columns
            ],
            "Example values": [
                ", ".join(dataframe[column].dropna().astype(str).head(3).tolist()) or "—"
                for column in dataframe.columns
            ],
        }
    )


def show_model_results(results: dict[str, Any]) -> None:
    metrics = results["metrics"]
    metric_table = pd.DataFrame(metrics).T.rename_axis("Model").reset_index()

    # Append training times if tracked
    if results.get("training_times"):
        metric_table["Training Time (s)"] = metric_table["Model"].map(results["training_times"])

    st.dataframe(
        metric_table.style.format({"MAE": "{:.4f}", "RMSE": "{:.4f}", "R²": "{:.4f}", "Training Time (s)": "{:.4f}"}),
        width="stretch",
        hide_index=True,
    )
    st.caption(
        f"Chronological split: {results['training_rows']:,} training rows followed by "
        f"{results['test_rows']:,} test rows, beginning {results['split_date']:%Y-%m-%d}. "
        "No shuffled split was used. Predictions are rolling one-step-ahead forecasts using only prior history."
    )
    st.caption(f"Features used: {', '.join(results['features'])}")


def actual_predicted_chart(results: dict[str, Any]) -> None:
    actual = results["actual"].to_numpy(dtype=float)
    all_values = [actual]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=results["dates"],
            y=actual,
            mode="lines+markers",
            name="Actual",
            line=dict(color="#f8fafc", width=2.5),
            marker=dict(size=5),
        )
    )
    colors = {
        "Linear Regression": "#38bdf8",
        "Random Forest": "#8b5cf6",
        "Support Vector Regressor (SVR)": "#10b981",
        "GRU Hybrid Model": "#f59e0b",
    }
    for name, predictions in results["predictions"].items():
        all_values.append(np.asarray(predictions))
        fig.add_trace(
            go.Scatter(
                x=results["dates"],
                y=predictions,
                mode="lines+markers",
                name=f"{name} prediction",
                line=dict(
                    color=colors.get(name, "#10b981"),
                    width=2,
                    dash="dash" if "Linear" in name else "solid",
                ),
                marker=dict(size=4),
            )
        )
    apply_chart_theme(
        fig,
        title="Actual vs. Predicted Prices (Chronological Test Set)",
        xaxis_title="Date",
        yaxis_title="Price / target value",
    )
    st.plotly_chart(fig, width="stretch")

    scatter = go.Figure()
    for name, predictions in results["predictions"].items():
        scatter.add_trace(
            go.Scatter(
                x=actual,
                y=predictions,
                mode="markers",
                name=name,
                marker=dict(color=colors.get(name, "#38bdf8"), size=7, opacity=0.85),
            )
        )
    low = float(np.nanmin(np.concatenate(all_values)))
    high = float(np.nanmax(np.concatenate(all_values)))
    scatter.add_trace(
        go.Scatter(
            x=[low, high],
            y=[low, high],
            mode="lines",
            name="Perfect prediction (y = x)",
            line=dict(color="#94a3b8", dash="dash", width=1.5),
        )
    )
    apply_chart_theme(
        scatter,
        title="Actual vs. Predicted Correlation Scatter",
        xaxis_title="Actual Value",
        yaxis_title="Predicted Value",
    )
    scatter.update_layout(hovermode="closest")
    st.plotly_chart(scatter, width="stretch")


def train_for_selection(
    dataframe: pd.DataFrame, date_column: str | None, target_column: str | None
) -> dict[str, Any] | None:
    if not date_column:
        st.warning("A valid date/time column is required for chronological model evaluation.")
        return None
    if not target_column:
        st.warning("Select a numeric price/target field to train models.")
        return None
    try:
        return evaluate_extended_models(dataframe, date_column, target_column)
    except ValueError as error:
        st.info(str(error))
    except Exception as error:  # Keep malformed user uploads from crashing the dashboard.
        st.error(f"Model training could not complete: {error}")
    return None


def read_uploaded_csv(file_bytes: bytes) -> pd.DataFrame:
    """Read CSV bytes with robust multi-encoding and delimiter fallback."""
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        for sep in (",", ";", "\t"):
            try:
                df = pd.read_csv(io.BytesIO(file_bytes), encoding=encoding, sep=sep)
                if len(df.columns) > 1 or len(file_bytes) < 80:
                    return df
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
    return pd.read_csv(io.BytesIO(file_bytes))


# Inject custom styling
inject_custom_theme()

# Enforce authentication on every rerun (halts with st.stop() if not logged in)
authenticated_user = require_authentication()

st.title(PROJECT_TITLE)
st.caption(
    "A research-oriented dashboard for exploring NFT market time series, social engagement, "
    "and leakage-safe machine-learning price estimates. Analyses use only the dataset provided."
)

with st.sidebar:
    render_user_badge_and_logout(authenticated_user)
    st.divider()
    st.markdown("### 🧭 Navigation & Data")
    uploaded_file = st.file_uploader(
        "Upload a CSV dataset",
        type=["csv"],
        help="Column names and sample values are inspected after upload. Your file is held strictly in this session.",
        max_upload_size=200,
    )
    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        signature = hashlib.sha256(file_bytes).hexdigest()
        if st.session_state.get("dataset_signature") != signature:
            try:
                raw_dataframe = read_uploaded_csv(file_bytes)
                if raw_dataframe.empty and len(raw_dataframe.columns) == 0:
                    raise ValueError("The CSV has no header or data columns.")
                set_dataset(raw_dataframe, signature, f"Uploaded: {uploaded_file.name}")
            except Exception as error:
                st.session_state["dataset"] = None
                st.session_state["dataset_signature"] = signature
                st.error(f"Could not read this CSV: {error}")
    if st.button("⚡ Load generated synthetic demo", width="stretch"):
        set_dataset(make_synthetic_demo_data(), "synthetic-demo-v1", "Synthetic educational demo")
    st.caption("The demo is generated for illustration; it is not actual NFT, OpenSea, or social-media data.")

    dataframe = st.session_state.get("dataset")
    if isinstance(dataframe, pd.DataFrame) and not dataframe.empty:
        columns = [str(column) for column in dataframe.columns]
        st.divider()
        st.markdown("### ⚙️ Map Dataset Fields")
        st.selectbox("Date / time", field_options(columns), key="date_col")
        st.selectbox("Price / target", field_options(columns), key="price_col")
        st.selectbox("Sales / activity", field_options(columns), key="sales_col")
        st.divider()
        nav_page = st.radio("Dashboard pages", PAGE_NAMES, label_visibility="visible")
        source_label = st.session_state.get("dataset_source", "Dataset")
        if "Synthetic" in source_label:
            st.markdown(f'<div class="status-pill-demo">● {html.escape(source_label)}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="status-pill-active">● {html.escape(source_label)}</div>', unsafe_allow_html=True)
    else:
        st.divider()
        nav_page = st.radio("Dashboard pages", PAGE_NAMES, label_visibility="visible")
        st.caption("Upload a CSV or choose the generated synthetic demo to begin.")

dataframe = st.session_state.get("dataset")
if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
    st.markdown(
        """
        <div class="empty-state-card">
            <div class="empty-state-title">Welcome to the NFT Trend Analyzer</div>
            <div class="empty-state-desc">
                An interactive time-series analytics and machine-learning benchmarking dashboard. 
                Upload your transaction dataset in the sidebar or initialize the synthetic demo to begin exploring.
            </div>
            <div class="empty-feature-grid">
                <div class="empty-feature-item">
                    <div class="empty-feature-title">📈 Market Overview</div>
                    <div class="empty-feature-text">Dataset diagnostics, volume tracking, price metrics, and data-quality inspection.</div>
                </div>
                <div class="empty-feature-item">
                    <div class="empty-feature-title">⏱️ Time-Series Analysis</div>
                    <div class="empty-feature-text">Interactive price trends with rolling averages and multi-interval aggregations.</div>
                </div>
                <div class="empty-feature-item">
                    <div class="empty-feature-title">💬 Social Engagement</div>
                    <div class="empty-feature-text">Detection of social signals, cross-metric comparisons, and correlation analysis.</div>
                </div>
                <div class="empty-feature-item">
                    <div class="empty-feature-title">🤖 Predictive Modeling</div>
                    <div class="empty-feature-text">Multi-model benchmark: Linear Regression, Random Forest, SVR, and GRU Hybrid.</div>
                </div>
                <div class="empty-feature-item">
                    <div class="empty-feature-title">🏷️ Valuation Categories</div>
                    <div class="empty-feature-text">Classify assets into structured price bands via Random Forest and SVM classifiers.</div>
                </div>
                <div class="empty-feature-item">
                    <div class="empty-feature-title">🌐 Live Intelligence</div>
                    <div class="empty-feature-text">Live spot rates and historical price context via CoinGecko and OpenSea API v2.</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.subheader("Common fields that enable each analysis")
    st.dataframe(
        pd.DataFrame(
            [
                {"Analysis": "Price trends and prediction", "Useful fields": "A date/time field and a numeric NFT price"},
                {"Analysis": "Market activity", "Useful fields": "A date/time field and a sales, trade, or volume field"},
                {"Analysis": "Social engagement", "Useful fields": "Numeric likes, comments, views, shares, or engagement"},
                {"Analysis": "Model evaluation", "Useful fields": "At least 12 dated numeric target observations"},
                {"Analysis": "Valuation categories", "Useful fields": "Numeric price field and optional transaction flag"},
                {"Analysis": "Live marketplace hub", "Useful fields": "OpenSea collection slug and optional API credentials"},
            ]
        ),
        width="stretch",
        hide_index=True,
    )
    st.stop()

date_column = selected_field("date_col")
price_column = selected_field("price_col")
sales_column = selected_field("sales_col")
frequency = st.sidebar.selectbox("Chart interval", ("Daily", "Weekly", "Monthly"), index=1)

if st.session_state.get("dataset_source") == "Synthetic educational demo":
    st.markdown(
        '<div class="research-callout-warning">⚠️ <b>Synthetic Demo Active:</b> The values displayed are synthetically generated for demonstration and do not reflect actual live market trades or live social metrics.</div>',
        unsafe_allow_html=True,
    )

# ==============================================================================
# Page 1: NFT Market Overview
# ==============================================================================
if nav_page == "NFT Market Overview":
    st.header("NFT Market Overview")
    stats = st.session_state.get("cleaning_stats", {})
    market_kpis = compute_market_kpis(dataframe, price_column, sales_column)
    asset_count, asset_col = count_unique_assets(dataframe)

    # Primary KPI metrics row
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    with kpi_col1:
        render_kpi("Dataset rows", f"{len(dataframe):,}", "Active clean records")
    with kpi_col2:
        if asset_count is not None and asset_col is not None:
            render_kpi("Identifiable Assets", f"{asset_count:,}", f"Unique across '{asset_col}'")
        else:
            render_kpi("Identifiable Assets", "N/A", "No asset/item column found")
    with kpi_col3:
        if market_kpis["avg_price"] is not None:
            render_kpi("Average Price", f"{market_kpis['avg_price']:.4f}", f"Field: {price_column}")
        else:
            render_kpi("Average Price", "N/A", "Select valid price field")
    with kpi_col4:
        if market_kpis["median_price"] is not None:
            render_kpi("Median Price", f"{market_kpis['median_price']:.4f}", f"Field: {price_column}")
        else:
            render_kpi("Median Price", "N/A", "Select valid price field")

    # Secondary KPI row: Volume, Pruned duplicates & blanks
    vol_col1, vol_col2, vol_col3 = st.columns(3)
    with vol_col1:
        if market_kpis["volume_supported"] and market_kpis["total_volume"] is not None:
            render_kpi(
                "Trading Volume",
                f"{market_kpis['total_volume']:,.2f}",
                market_kpis["volume_method"] or "Calculated volume",
            )
        else:
            render_kpi("Trading Volume", "Unsupported", "Dataset lacks volume / paired sales")
    with vol_col2:
        render_kpi("Duplicate Rows Pruned", f"{stats.get('duplicate_rows_removed', 0):,}", "Exact duplicate rows")
    with vol_col3:
        render_kpi("Empty Rows Removed", f"{stats.get('empty_rows_removed', 0):,}", "Blank rows dropped")

    # Data Quality Warnings
    if market_kpis["quality_warnings"]:
        for warning in market_kpis["quality_warnings"]:
            st.warning(f"Data Quality Notice: {warning}")

    st.subheader("Dataset inspection")
    st.caption("Headers were trimmed, blank cells normalized to missing values, empty rows removed, and exact duplicates dropped.")
    st.dataframe(inspect_table(dataframe), width="stretch", hide_index=True)

    st.subheader("Market snapshots")
    chart_left, chart_right = st.columns(2)
    with chart_left:
        show_price_chart(dataframe, date_column, price_column, frequency)
    with chart_right:
        show_activity_chart(dataframe, date_column, sales_column, frequency)

# ==============================================================================
# Page 2: Time-Series Analysis
# ==============================================================================
elif nav_page == "Time-Series Analysis":
    st.header("Time-Series Analysis")
    st.write(
        "Analyze historical NFT metric movements across configurable time aggregation intervals, "
        "apply rolling averages to smooth short-term variance, and isolate specific date windows."
    )

    numeric_columns = [col for col in dataframe.columns if parse_numeric(dataframe[col]).notna().any()]

    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns(3)
    with ctrl_col1:
        ts_metric = st.selectbox(
            "Select metric to analyze",
            numeric_columns,
            index=numeric_columns.index(price_column) if price_column in numeric_columns else 0,
        )
    with ctrl_col2:
        rolling_choice = st.selectbox(
            "Rolling average window",
            ("None", "7 periods", "14 periods", "30 periods"),
            index=1,
        )
        window_map = {"None": 1, "7 periods": 7, "14 periods": 14, "30 periods": 30}
        rolling_window = window_map[rolling_choice]
    with ctrl_col3:
        ts_interval = st.selectbox("Interval aggregation", ("Daily", "Weekly", "Monthly"), index=0)

    start_date = None
    end_date = None
    if date_column and date_column in dataframe:
        parsed_dates = parse_dates(dataframe[date_column]).dropna()
        if not parsed_dates.empty:
            min_d = parsed_dates.min().date()
            max_d = parsed_dates.max().date()
            if min_d < max_d:
                date_filter = st.slider(
                    "Date Range Filter",
                    min_value=min_d,
                    max_value=max_d,
                    value=(min_d, max_d),
                    format="YYYY-MM-DD",
                )
                start_date, end_date = date_filter
            else:
                st.caption(f"Single date available: {min_d}")

    show_price_chart(
        dataframe,
        date_column,
        ts_metric,
        ts_interval,
        rolling_window=rolling_window,
        start_date=start_date,
        end_date=end_date,
    )

    st.subheader("Recorded market activity")
    show_activity_chart(
        dataframe,
        date_column,
        sales_column,
        ts_interval,
        start_date=start_date,
        end_date=end_date,
    )

# ==============================================================================
# Page 3: Social-Media Engagement
# ==============================================================================
elif nav_page == "Social-Media Engagement":
    st.header("Social-Media Engagement Analysis")
    st.markdown(
        """
        <div class="research-callout">
            <b>🔬 Scientific & Methodological Caveat:</b> 
            Correlation does not establish causation. Observed statistical relationships between social activity 
            (likes, comments, views) and NFT prices may reflect mutual exposure to wider crypto market sentiment, 
            algorithmic amplification, or reverse causality (higher sales triggering viral posts). 
            Interpret correlations as observational co-occurrences.
        </div>
        """,
        unsafe_allow_html=True,
    )

    social_columns = discover_social_columns(dataframe)
    if not social_columns:
        st.info(
            "No numeric social-engagement fields were detected in this dataset. "
            "Columns matching keywords such as likes, comments, replies, retweets, shares, views, "
            "followers, impressions, or engagement enable this analysis."
        )
    else:
        selected_social = st.multiselect(
            "Engagement fields to analyze",
            social_columns,
            default=social_columns[: min(5, len(social_columns))],
        )
        if not selected_social:
            st.info("Select at least one detected engagement metric.")
        else:
            long_data = []
            for column in selected_social:
                values = parse_numeric(dataframe[column])
                if date_column:
                    dates = parse_dates(dataframe[date_column])
                    valid = dates.notna() & values.notna() & np.isfinite(values)
                    if valid.any():
                        long_data.append(
                            pd.DataFrame(
                                {
                                    "Period": period_start(dates.loc[valid], frequency).to_numpy(),
                                    "Metric": str(column),
                                    "Value": values.loc[valid].astype(float).to_numpy(),
                                }
                            )
                        )
                else:
                    numeric_values = values.dropna()
                    if len(numeric_values):
                        long_data.append(
                            pd.DataFrame(
                                {
                                    "Period": [str(column)],
                                    "Metric": [str(column)],
                                    "Value": [numeric_values.sum()],
                                }
                            )
                        )
            if long_data:
                engagement = pd.concat(long_data, ignore_index=True)
                if date_column:
                    engagement = engagement.groupby(["Period", "Metric"], as_index=False)["Value"].sum()
                    fig = px.line(
                        engagement,
                        x="Period",
                        y="Value",
                        color="Metric",
                        markers=True,
                    )
                    apply_chart_theme(
                        fig,
                        title=f"Recorded Social Metrics by {frequency.lower()} period",
                        xaxis_title="Date",
                        yaxis_title="Recorded metric total",
                    )
                else:
                    totals = engagement.groupby("Metric", as_index=False)["Value"].sum()
                    fig = px.bar(totals, x="Metric", y="Value")
                    apply_chart_theme(
                        fig,
                        title="Social Metric Totals in Uploaded Dataset",
                        xaxis_title="Metric",
                        yaxis_title="Sum of uploaded values",
                    )
                st.plotly_chart(fig, width="stretch")

            st.subheader("Cross-metric comparison: Engagement vs. Market Price / Sales")
            target_candidates = [col for col in [price_column, sales_column] if col and col in dataframe]
            if not target_candidates:
                st.info("Select a valid price or sales column in the sidebar to enable cross-metric comparison.")
            else:
                scatter_col1, scatter_col2 = st.columns(2)
                with scatter_col1:
                    chosen_social = st.selectbox("Engagement X-Axis", selected_social, key="scatter_social")
                with scatter_col2:
                    chosen_target = st.selectbox("Market Metric Y-Axis", target_candidates, key="scatter_target")

                s_raw = parse_numeric(dataframe[chosen_social])
                t_raw = parse_numeric(dataframe[chosen_target])
                valid_scatter = s_raw.notna() & t_raw.notna() & np.isfinite(s_raw) & np.isfinite(t_raw)
                if valid_scatter.sum() >= 3:
                    scatter_df = pd.DataFrame(
                        {
                            chosen_social: s_raw.loc[valid_scatter].astype(float),
                            chosen_target: t_raw.loc[valid_scatter].astype(float),
                        }
                    )
                    sc_fig = px.scatter(
                        scatter_df,
                        x=chosen_social,
                        y=chosen_target,
                    )
                    sc_fig.update_traces(marker=dict(color="#38bdf8", size=7, opacity=0.85))
                    x_sc = scatter_df[chosen_social].to_numpy(dtype=float)
                    y_sc = scatter_df[chosen_target].to_numpy(dtype=float)
                    if len(x_sc) >= 2 and float(np.std(x_sc)) > 1e-9:
                        slope, intercept = np.polyfit(x_sc, y_sc, 1)
                        x_line = np.linspace(float(np.min(x_sc)), float(np.max(x_sc)), 50)
                        y_line = slope * x_line + intercept
                        sc_fig.add_trace(
                            go.Scatter(
                                x=x_line,
                                y=y_line,
                                mode="lines",
                                name=f"Linear Trend (slope: {slope:.3f})",
                                line=dict(color="#8b5cf6", width=2),
                            )
                        )
                    apply_chart_theme(
                        sc_fig,
                        title=f"{chosen_social} vs. {chosen_target} Correlation Scatter",
                        xaxis_title=chosen_social,
                        yaxis_title=chosen_target,
                    )
                    sc_fig.update_layout(hovermode="closest")
                    st.plotly_chart(sc_fig, width="stretch")
                else:
                    st.warning("Insufficient overlapping records between chosen engagement and market metrics.")

            st.subheader("Statistical Correlation Matrix (Pearson r)")
            corr_df = compute_engagement_correlations(dataframe, selected_social, target_candidates)
            if not corr_df.empty:
                st.dataframe(
                    corr_df.style.format({"Pearson Correlation": "{:.4f}", "Observations": "{:,}"}),
                    width="stretch",
                    hide_index=True,
                )
                st.caption(
                    "Pearson correlation ranges from -1.0 (inverse relationship) to +1.0 (direct relationship). "
                    "Values near 0 denote absence of linear correlation."
                )
            else:
                st.info("Insufficient paired data points to compute correlation matrix.")

# ==============================================================================
# Page 4: Price Prediction
# ==============================================================================
elif nav_page == "Price Prediction":
    st.header("Price Prediction")
    st.markdown(
        """
        <div class="research-callout">
            <b>⚖️ Price Estimate Disclaimer:</b> 
            Predictions produced by this dashboard are exploratory machine-learning estimates based strictly 
            on historical training patterns within the uploaded file. They do not represent guaranteed future prices, 
            valuation promises, or investment advice.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write(
        "Models predict the target variable one observation ahead using chronological feature history. "
        "Features include calendar indices and lagged values strictly prior to the prediction timestamp "
        "to prevent target leakage. Evaluates Linear Regression, Random Forest, Support Vector Regression (SVR), "
        "and a GRU Hybrid recurrent sequence model where data depth permits."
    )

    numeric_columns = [col for col in dataframe.columns if parse_numeric(dataframe[col]).notna().any()]
    pred_target = st.selectbox(
        "Target price/metric column",
        numeric_columns,
        index=numeric_columns.index(price_column) if price_column in numeric_columns else 0,
        help="Select which column represents the price/target to forecast.",
    )

    results = train_for_selection(dataframe, date_column, pred_target)
    if results:
        # Display GRU Sequence Status Callout
        gru_info = results.get("gru_status", {})
        if gru_info.get("available"):
            st.markdown(
                '<div class="status-pill-active">● GRU Hybrid Model Active (Chronological multi-step sequence encoder)</div>',
                unsafe_allow_html=True,
            )
        else:
            reason = gru_info.get("reason", "Sequence depth requirement not met.")
            st.caption(f"ℹ️ GRU Sequence Model: {reason}")

        show_model_results(results)
        actual_predicted_chart(results)

        # Feature Importance Analysis for Random Forest
        rf_pipe = None
        from nft_analysis import evaluate_models
        # Feature importances from standard evaluate_models if available
        base_res = evaluate_models(dataframe, date_column, pred_target)
        if base_res.get("feature_importances"):
            st.subheader("Random Forest Feature Importance")
            feat_df = (
                pd.DataFrame(list(base_res["feature_importances"].items()), columns=["Feature", "Importance"])
                .sort_values("Importance", ascending=True)
            )
            feat_fig = px.bar(feat_df, x="Importance", y="Feature", orientation="h")
            feat_fig.update_traces(marker_color="#8b5cf6")
            apply_chart_theme(
                feat_fig,
                title="Relative Feature Importances (Random Forest)",
                xaxis_title="Importance Weight",
                yaxis_title="Feature",
                height=320,
            )
            st.plotly_chart(feat_fig, width="stretch")

# ==============================================================================
# Page 5: Model Evaluation
# ==============================================================================
elif nav_page == "Model Evaluation":
    st.header("Model Evaluation")
    st.write(
        "All regression models are benchmarked using a strict chronological 80/20 train/test evaluation. "
        "Earlier observations train the algorithms, and the most recent 20% of chronological records "
        "are held out as an unseen test benchmark."
    )

    numeric_columns = [col for col in dataframe.columns if parse_numeric(dataframe[col]).notna().any()]
    eval_target = st.selectbox(
        "Evaluation target metric",
        numeric_columns,
        index=numeric_columns.index(price_column) if price_column in numeric_columns else 0,
        key="eval_target_select",
    )

    results = train_for_selection(dataframe, date_column, eval_target)
    if results:
        st.subheader("Multi-Model Regression Comparison")
        metrics_dict = results["metrics"]
        metric_rows = []
        for model_name, m_vals in metrics_dict.items():
            for m_name, m_val in m_vals.items():
                metric_rows.append({"Model": model_name, "Metric": m_name, "Score": m_val})
        metrics_df = pd.DataFrame(metric_rows)

        col_bar, col_table = st.columns([3, 2])
        with col_bar:
            comp_fig = px.bar(
                metrics_df[metrics_df["Metric"].isin(["MAE", "RMSE"])],
                x="Metric",
                y="Score",
                color="Model",
                barmode="group",
                title="Regression Error Comparison (Lower is Better)",
            )
            apply_chart_theme(comp_fig, height=330)
            st.plotly_chart(comp_fig, width="stretch")
        with col_table:
            st.write("**Evaluation Metrics & Compute Time**")
            show_model_results(results)

        with st.expander("📖 Metric Interpretation & Technical Definitions"):
            st.markdown(
                """
                - **MAE (Mean Absolute Error):** Average absolute magnitude of errors in target units. Less sensitive to outliers.
                - **RMSE (Root Mean Squared Error):** Square root of mean squared errors. Heavily penalizes large prediction errors.
                - **R² (Coefficient of Determination):** Proportion of variance explained relative to a horizontal line predicting the test set mean. Can be negative if the model predicts worse than the simple historical average.
                - **Support Vector Regressor (SVR):** RBF kernel regression with epsilon-insensitive loss margin.
                - **GRU Hybrid Model:** Recurrent sequence encoder paired with tabular features for multi-step temporal context.
                """
            )

        st.subheader("Held-out test predictions")
        actual_predicted_chart(results)

        if results.get("residuals"):
            st.subheader("Residual Analysis (Actual − Predicted)")
            res_fig = go.Figure()
            colors_map = {
                "Linear Regression": "#38bdf8",
                "Random Forest": "#8b5cf6",
                "Support Vector Regressor (SVR)": "#10b981",
                "GRU Hybrid Model": "#f59e0b",
            }
            for m_name, res_vals in results["residuals"].items():
                res_fig.add_trace(
                    go.Scatter(
                        x=results["dates"],
                        y=res_vals,
                        mode="lines+markers",
                        name=f"{m_name}",
                        line=dict(color=colors_map.get(m_name, "#cbd5e1")),
                        marker=dict(size=4),
                    )
                )
            res_fig.add_hline(y=0, line_dash="dash", line_color="#94a3b8")
            apply_chart_theme(
                res_fig,
                title="Residual Errors Across Held-Out Test Window",
                xaxis_title="Date",
                yaxis_title="Residual Error",
                height=320,
            )
            st.plotly_chart(res_fig, width="stretch")

        comparison = pd.DataFrame(
            {
                "Date": results["dates"],
                "Actual": results["actual"],
                **{f"{name} predicted": values for name, values in results["predictions"].items()},
            }
        )
        st.dataframe(comparison, width="stretch", hide_index=True)

# ==============================================================================
# Page 6: NFT Valuation Categories (NEW)
# ==============================================================================
elif nav_page == "Valuation Categories":
    st.header("NFT Valuation Categories")
    st.markdown(
        """
        <div class="research-callout">
            <b>🏷️ Valuation Category Framework:</b> 
            Classifies assets into structured, contiguous price bands without conflating unsold assets with zero-price sales. 
            Evaluates <b>Random Forest Classifier</b> and <b>Support Vector Machine (SVM)</b> classifiers on an 
            80/20 chronological split to benchmark category estimation.
        </div>
        """,
        unsafe_allow_html=True,
    )

    numeric_columns = [col for col in dataframe.columns if parse_numeric(dataframe[col]).notna().any()]
    val_target = st.selectbox(
        "Valuation Price Column",
        numeric_columns,
        index=numeric_columns.index(price_column) if price_column in numeric_columns else 0,
        help="Select column containing NFT prices to categorize.",
    )

    col_curr1, col_curr2 = st.columns(2)
    with col_curr1:
        currency_mode = st.radio("Base Pricing Unit", ["USD", "ETH"], horizontal=True)
    with col_curr2:
        eth_rate = 2600.0
        if currency_mode == "ETH":
            st.caption("Live CoinGecko rate query:")
            cg_res = get_current_eth_usd_price()
            if cg_res.get("status") == "success" and cg_res.get("rate_usd"):
                eth_rate = float(cg_res["rate_usd"])
                st.write(f"Spot ETH/USD: **${eth_rate:,.2f}** ({cg_res.get('source')})")
            else:
                eth_rate = st.number_input("Custom ETH/USD rate", min_value=1.0, value=2600.0, step=50.0)

    # 1. Category Distribution
    st.subheader("Observed Valuation Category Distribution")
    raw_prices = parse_numeric(dataframe[val_target])
    assigned_cats = categorize_prices(
        raw_prices,
        currency=currency_mode,
        eth_usd_rate=eth_rate if currency_mode == "ETH" else None,
    )
    dist_df = compute_category_distribution(assigned_cats)

    col_dist_chart, col_dist_table = st.columns([3, 2])
    with col_dist_chart:
        dist_fig = px.bar(
            dist_df,
            x="Valuation Category",
            y="Count",
            color="Valuation Category",
            title="Frequency Across Valuation Brackets",
        )
        apply_chart_theme(dist_fig, height=320)
        st.plotly_chart(dist_fig, width="stretch")
    with col_dist_table:
        st.write("**Category Breakdown Table**")
        st.dataframe(dist_df, width="stretch", hide_index=True)

    # 2. Classifier Benchmarking
    st.subheader("Supervised Valuation Category Classification")
    st.write(
        "Trains Random Forest and Support Vector Machine (SVM) classifiers to predict price category "
        "one observation ahead using calendar features and lagged history."
    )

    try:
        clf_results = evaluate_valuation_classifiers(
            dataframe,
            date_column,
            val_target,
            currency=currency_mode,
            eth_usd_rate=eth_rate if currency_mode == "ETH" else None,
        )

        clf_metrics_df = pd.DataFrame(clf_results["metrics"]).T.reset_index().rename(columns={"index": "Model"})
        st.dataframe(
            clf_metrics_df.style.format(
                {
                    "Accuracy": "{:.4f}",
                    "Balanced Accuracy": "{:.4f}",
                    "Macro Precision": "{:.4f}",
                    "Macro Recall": "{:.4f}",
                    "Macro F1": "{:.4f}",
                    "Weighted F1": "{:.4f}",
                }
            ),
            width="stretch",
            hide_index=True,
        )

        # Confusion Matrix Display
        st.subheader("Confusion Matrix Benchmark")
        cm_col1, cm_col2 = st.columns(2)
        classes_labels = clf_results["classes"]
        with cm_col1:
            cm_rf = clf_results["confusion_matrices"]["Random Forest Classifier"]
            fig_rf = px.imshow(
                cm_rf,
                labels=dict(x="Predicted Category", y="Actual Category", color="Records"),
                x=classes_labels,
                y=classes_labels,
                text_auto=True,
                color_continuous_scale="Purples",
                title="Random Forest Confusion Matrix",
            )
            apply_chart_theme(fig_rf, height=360)
            st.plotly_chart(fig_rf, width="stretch")
        with cm_col2:
            cm_svm = clf_results["confusion_matrices"]["Support Vector Classifier (SVM)"]
            fig_svm = px.imshow(
                cm_svm,
                labels=dict(x="Predicted Category", y="Actual Category", color="Records"),
                x=classes_labels,
                y=classes_labels,
                text_auto=True,
                color_continuous_scale="Blues",
                title="Support Vector Machine (SVM) Confusion Matrix",
            )
            apply_chart_theme(fig_svm, height=360)
            st.plotly_chart(fig_svm, width="stretch")

        # 3. Interactive Valuation Estimator
        st.subheader("Interactive Valuation Category Estimator")
        st.write("Simulate asset valuation tier prediction for specific historical lag and calendar inputs:")
        features_list = clf_results["features"]
        rf_pipe = clf_results["trained_pipelines"]["Random Forest Classifier"]

        input_cols = st.columns(min(4, len(features_list)))
        sample_inputs = {}
        for idx, feat_name in enumerate(features_list[:4]):
            col_target = input_cols[idx % len(input_cols)]
            with col_target:
                sample_inputs[feat_name] = st.number_input(
                    f"Feature: {feat_name}",
                    value=float(dataframe[val_target].dropna().median()) if "lag" in feat_name else 1.0,
                    step=0.5,
                )

        if st.button("Predict Valuation Category", width="stretch"):
            val_pred = predict_single_valuation(rf_pipe, sample_inputs, features_list)
            st.success(f"Estimated Valuation Tier: **{val_pred['predicted_category']}**")
            if val_pred.get("class_probabilities"):
                prob_df = pd.DataFrame(
                    list(val_pred["class_probabilities"].items()), columns=["Category", "Estimated Probability"]
                )
                prob_fig = px.bar(prob_df, x="Category", y="Estimated Probability", color="Category")
                apply_chart_theme(prob_fig, title="Estimated Category Class Probabilities", height=280)
                st.plotly_chart(prob_fig, width="stretch")
            st.caption(f"⚠️ {val_pred['disclaimer']}")

    except ValueError as err:
        st.info(f"Valuation classification notice: {err}")
    except Exception as err:
        st.error(f"Valuation classification error: {err}")

# ==============================================================================
# Page 7: Live Market Intelligence (NEW)
# ==============================================================================
elif nav_page == "Live Market Intelligence":
    st.header("Live Market Intelligence & Currency Hub")
    st.markdown(
        """
        <div class="research-callout">
            <b>🌐 External Market Context:</b> 
            Connects to official public endpoints for <b>CoinGecko</b> (ETH/USD spot and historical exchange rates) 
            and <b>OpenSea API v2</b> (collection floor prices and supply metadata). Operates with in-memory caching, 
            timeout guards, and transparent offline fallback when credentials are absent.
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_cg, tab_os = st.tabs(["🪙 CoinGecko Currency Hub", "🌊 OpenSea Marketplace Explorer"])

    with tab_cg:
        st.subheader("CoinGecko Live & Historical Exchange Rates")
        cg_kpi1, cg_kpi2, cg_kpi3 = st.columns(3)

        cg_current = get_current_eth_usd_price()
        with cg_kpi1:
            if cg_current.get("status") == "success" and cg_current.get("rate_usd"):
                render_kpi("ETH / USD Spot Rate", f"${cg_current['rate_usd']:,.2f}", cg_current.get("source", "Live"))
            else:
                render_kpi("ETH / USD Spot Rate", "Unavailable", cg_current.get("message", "Offline / Rate limited"))
        with cg_kpi2:
            render_kpi("Query Timestamp", cg_current.get("timestamp", "—")[:19], "UTC")
        with cg_kpi3:
            render_kpi("Cached Status", "Active" if cg_current.get("is_cached") else "Live Query", "TTL: 5 Minutes")

        st.divider()
        st.write("**Interactive Currency Converter (ETH $\\rightarrow$ USD)**")
        conv_c1, conv_c2, conv_c3 = st.columns(3)
        with conv_c1:
            input_eth = st.number_input("Amount in ETH", min_value=0.001, value=1.0, step=0.1)
        with conv_c2:
            use_hist = st.checkbox("Match to Historical Date")
            hist_date = None
            if use_hist:
                hist_date = st.date_input("Historical Conversion Date", value=datetime.date.today())
        with conv_c3:
            conv_res = convert_eth_to_usd(input_eth, historical_date=hist_date)
            st.metric("Converted USD Value", f"${conv_res['usd_amount']:,.2f}", conv_res.get("rate_type"))

    with tab_os:
        st.subheader("OpenSea Collection Intelligence (API v2)")
        st.write(
            "Query verified collection metadata and floor prices directly from OpenSea's official API endpoints. "
            "Requires an optional `OPENSEA_API_KEY` in environment variables or Streamlit secrets."
        )

        col_search1, col_search2 = st.columns([3, 1])
        with col_search1:
            collection_slug = st.text_input(
                "OpenSea Collection Slug",
                value="boredapeyachtclub",
                help="Identifier slug from OpenSea URL (e.g. 'boredapeyachtclub', 'doodles-official', 'azuki')",
            )
        with col_search2:
            st.write("")
            st.write("")
            fetch_btn = st.button("Fetch Live Data", width="stretch")

        if fetch_btn or collection_slug:
            os_res = get_opensea_collection_stats(collection_slug)
            if os_res.get("status") == "success":
                st.success(f"Retrieved data for **{os_res.get('name')}** ({os_res.get('source')})")
                os_kpi1, os_kpi2, os_kpi3 = st.columns(3)
                with os_kpi1:
                    floor_val = os_res.get("floor_price")
                    render_kpi("Floor Price", f"{floor_val:.4f} ETH" if floor_val else "N/A", "Active marketplace floor")
                with os_kpi2:
                    render_kpi("Total Supply", f"{os_res.get('total_supply', 0):,}", "Minted NFT count")
                with os_kpi3:
                    render_kpi("Retrieval Time", os_res.get("retrieval_time", "—")[:19], "UTC Timestamp")
                st.write(f"**Description:** {os_res.get('description')}")
            elif os_res.get("status") == "no_credentials":
                st.info(f"ℹ️ **OpenSea API Notice:** {os_res.get('message')}")
                st.caption(os_res.get("guide", ""))
                st.markdown(
                    """
                    <div class="empty-feature-item">
                        <b>Offline Demonstration Fallback:</b> Without an API key, the dashboard runs in full offline mode. 
                        All CSV time series, pricing predictions, and valuation models operate with zero cloud dependency.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.warning(f"Notice: {os_res.get('message')}")
