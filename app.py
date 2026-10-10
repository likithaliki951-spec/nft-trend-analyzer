"""Interactive student dashboard for analysis of NFT time-series datasets."""

from __future__ import annotations

import hashlib
import io
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from nft_analysis import (
    clean_dataframe,
    discover_social_columns,
    evaluate_models,
    infer_column,
    make_synthetic_demo_data,
    parse_dates,
    parse_numeric,
)


PROJECT_TITLE = "Analysis of Trending NFTs Using Time-Series Data and Machine Learning"
PAGE_NAMES = (
    "NFT Market Overview",
    "Time-Series Analysis",
    "Social-Media Engagement",
    "Price Prediction",
    "Model Evaluation",
)
NO_FIELD = "Not selected"

st.set_page_config(page_title=PROJECT_TITLE, layout="wide")


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
) -> pd.DataFrame:
    if not date_column or not value_column:
        return pd.DataFrame()
    dates = parse_dates(dataframe[date_column])
    values = parse_numeric(dataframe[value_column])
    valid = dates.notna() & values.notna() & np.isfinite(values)
    if not valid.any():
        return pd.DataFrame()
    chart_data = pd.DataFrame(
        {
            "Period": period_start(dates.loc[valid], frequency).to_numpy(),
            "Value": values.loc[valid].astype(float).to_numpy(),
        }
    )
    operation = "sum" if aggregation == "sum" else "mean"
    return (
        chart_data.groupby("Period", as_index=False)["Value"]
        .agg(operation)
        .sort_values("Period")
    )


def show_price_chart(
    dataframe: pd.DataFrame, date_column: str | None, price_column: str | None, frequency: str
) -> bool:
    if not date_column:
        st.info("Choose a date/time column to plot prices over time.")
        return False
    if not price_column:
        st.info("Choose a price column in the sidebar to show a price trend.")
        return False
    chart_data = time_series_data(dataframe, date_column, price_column, frequency, "mean")
    if chart_data.empty:
        st.warning("The selected price field has no usable numeric values paired with valid dates.")
        return False
    chart_data["Rolling average"] = chart_data["Value"].rolling(7, min_periods=1).mean()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=chart_data["Period"], y=chart_data["Value"], mode="lines", name="Period average"))
    fig.add_trace(
        go.Scatter(
            x=chart_data["Period"],
            y=chart_data["Rolling average"],
            mode="lines",
            name="7-period rolling average",
        )
    )
    fig.update_layout(
        title=f"NFT price trend ({frequency.lower()} average)",
        xaxis_title="Date",
        yaxis_title=f"Average {price_column}",
        hovermode="x unified",
        legend_title_text="",
    )
    st.plotly_chart(fig, width="stretch")
    return True


def show_activity_chart(
    dataframe: pd.DataFrame, date_column: str | None, sales_column: str | None, frequency: str
) -> bool:
    if not date_column:
        st.info("Choose a date/time column to show market activity over time.")
        return False

    if sales_column:
        chart_data = time_series_data(dataframe, date_column, sales_column, frequency, "sum")
        title = f"Recorded {sales_column} by {frequency.lower()} period"
        y_label = f"Recorded {sales_column}"
        note = "This chart sums the selected sales/activity field; it does not add external marketplace data."
    else:
        dates = parse_dates(dataframe[date_column])
        valid_dates = dates.dropna()
        if valid_dates.empty:
            st.warning("The selected date/time field contains no valid dates.")
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
        st.warning("The selected activity field has no usable numeric values paired with valid dates.")
        return False
    st.caption(note)
    fig = px.bar(chart_data, x="Period", y="Value", title=title)
    fig.update_layout(xaxis_title="Date", yaxis_title=y_label)
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
    st.dataframe(
        metric_table.style.format({"MAE": "{:.4f}", "RMSE": "{:.4f}", "R²": "{:.4f}"}),
        width="stretch",
        hide_index=True,
    )
    st.caption(
        f"Chronological split: {results['training_rows']:,} training rows followed by "
        f"{results['test_rows']:,} test rows, beginning {results['split_date']:%Y-%m-%d}. "
        "No shuffled split was used. Test predictions are rolling one-step-ahead forecasts "
        "using only the previous observation as history."
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
        )
    )
    for name, predictions in results["predictions"].items():
        all_values.append(np.asarray(predictions))
        fig.add_trace(
            go.Scatter(
                x=results["dates"],
                y=predictions,
                mode="lines+markers",
                name=f"{name} prediction",
            )
        )
    fig.update_layout(
        title="Actual vs. predicted prices (chronological test set)",
        xaxis_title="Date",
        yaxis_title="Price / target value",
        hovermode="x unified",
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
            )
        )
    low = float(np.nanmin(np.concatenate(all_values)))
    high = float(np.nanmax(np.concatenate(all_values)))
    scatter.add_trace(
        go.Scatter(x=[low, high], y=[low, high], mode="lines", name="Perfect prediction", line={"dash": "dash"})
    )
    scatter.update_layout(
        title="Actual-versus-predicted values",
        xaxis_title="Actual",
        yaxis_title="Predicted",
    )
    st.plotly_chart(scatter, width="stretch")


def train_for_selection(
    dataframe: pd.DataFrame, date_column: str | None, target_column: str | None
) -> dict[str, Any] | None:
    if not date_column:
        st.warning("A valid date/time column is required for chronological model evaluation.")
        return None
    if not target_column:
        st.warning("Select a numeric price/target field in the sidebar.")
        return None
    try:
        return evaluate_models(dataframe, date_column, target_column)
    except ValueError as error:
        st.info(str(error))
    except Exception as error:  # Keep malformed user uploads from crashing the dashboard.
        st.error(f"Model training could not complete: {error}")
    return None


st.title(PROJECT_TITLE)
st.caption(
    "An upload-driven student project for exploring NFT market time series, social engagement, "
    "and machine-learning price estimates. Analyses use only the dataset you provide."
)

with st.sidebar:
    st.header("Dataset")
    uploaded_file = st.file_uploader(
        "Upload a CSV dataset",
        type=["csv"],
        help="Column names and sample values are inspected after upload. Your file is held in this app session.",
        max_upload_size=200,
    )
    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        signature = hashlib.sha256(file_bytes).hexdigest()
        if st.session_state.get("dataset_signature") != signature:
            try:
                raw_dataframe = pd.read_csv(io.BytesIO(file_bytes))
                if raw_dataframe.empty and len(raw_dataframe.columns) == 0:
                    raise ValueError("The CSV has no header or data columns.")
                set_dataset(raw_dataframe, signature, f"Uploaded: {uploaded_file.name}")
            except Exception as error:
                st.session_state["dataset"] = None
                st.session_state["dataset_signature"] = signature
                st.error(f"Could not read this CSV: {error}")
    if st.button("Load generated synthetic demo", width="stretch"):
        set_dataset(make_synthetic_demo_data(), "synthetic-demo-v1", "Synthetic educational demo")
    st.caption("The demo is generated for illustration; it is not actual NFT, OpenSea, or social-media data.")

    dataframe = st.session_state.get("dataset")
    if isinstance(dataframe, pd.DataFrame) and not dataframe.empty:
        columns = [str(column) for column in dataframe.columns]
        st.divider()
        st.subheader("Map dataset fields")
        st.selectbox("Date / time", field_options(columns), key="date_col")
        st.selectbox("Price / target", field_options(columns), key="price_col")
        st.selectbox("Sales / activity", field_options(columns), key="sales_col")
        nav_page = st.radio("Dashboard pages", PAGE_NAMES, label_visibility="visible")
        source_label = st.session_state.get("dataset_source", "Dataset")
        st.caption(f"Active source: {source_label}")
    else:
        nav_page = st.radio("Dashboard pages", PAGE_NAMES, label_visibility="visible")
        st.caption("Upload a CSV or choose the generated synthetic demo to begin.")

dataframe = st.session_state.get("dataset")
if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
    st.info("Start by uploading a CSV in the sidebar, or load the clearly labeled synthetic demo.")
    st.subheader("Common fields that enable each analysis")
    st.dataframe(
        pd.DataFrame(
            [
                {"Analysis": "Price trends and prediction", "Useful fields": "A date/time field and a numeric NFT price"},
                {"Analysis": "Market activity", "Useful fields": "A date/time field and a sales, trade, or volume field"},
                {"Analysis": "Social engagement", "Useful fields": "Numeric likes, comments, views, shares, or engagement"},
                {"Analysis": "Model evaluation", "Useful fields": "At least 12 dated numeric target observations"},
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
    st.warning(
        "Synthetic demo data is active. The generated values are for demonstrating this dashboard only "
        "and do not represent real NFT transactions or live social-media activity."
    )

if nav_page == "NFT Market Overview":
    st.header("NFT Market Overview")
    stats = st.session_state.get("cleaning_stats", {})
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Dataset rows", f"{len(dataframe):,}")
    col2.metric("Available columns", f"{len(dataframe.columns):,}")
    col3.metric("Duplicate rows removed", f"{stats.get('duplicate_rows_removed', 0):,}")
    col4.metric("Empty rows removed", f"{stats.get('empty_rows_removed', 0):,}")

    st.subheader("Dataset inspection")
    st.caption("Headers were trimmed, blank cells normalized to missing values, empty rows removed, and exact duplicates dropped.")
    st.dataframe(inspect_table(dataframe), width="stretch", hide_index=True)
    st.subheader("Market snapshots")
    chart_left, chart_right = st.columns(2)
    with chart_left:
        show_price_chart(dataframe, date_column, price_column, frequency)
    with chart_right:
        show_activity_chart(dataframe, date_column, sales_column, frequency)

elif nav_page == "Time-Series Analysis":
    st.header("Time-Series Analysis")
    st.write(
        "Choose a date field and interval in the sidebar. Price charts show period averages; "
        "the rolling line summarizes the plotted periods."
    )
    show_price_chart(dataframe, date_column, price_column, frequency)
    st.subheader("Sales and observed activity")
    show_activity_chart(dataframe, date_column, sales_column, frequency)

elif nav_page == "Social-Media Engagement":
    st.header("Social-Media Engagement Analysis")
    social_columns = discover_social_columns(dataframe)
    if not social_columns:
        st.info(
            "No numeric social-engagement fields were detected. Expected fields include likes, comments, "
            "replies, retweets, shares, views, impressions, followers, or engagement."
        )
    else:
        selected_social = st.multiselect(
            "Engagement fields to plot",
            social_columns,
            default=social_columns[: min(5, len(social_columns))],
        )
        if not selected_social:
            st.info("Select at least one detected metric.")
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
                            pd.DataFrame({"Period": [str(column)], "Metric": [str(column)], "Value": [numeric_values.sum()]})
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
                        title=f"Recorded social metrics by {frequency.lower()} period",
                    )
                    fig.update_layout(xaxis_title="Date", yaxis_title="Recorded metric total")
                else:
                    totals = engagement.groupby("Metric", as_index=False)["Value"].sum()
                    fig = px.bar(totals, x="Metric", y="Value", title="Social metric totals in uploaded dataset")
                    fig.update_layout(xaxis_title="Metric", yaxis_title="Sum of uploaded values")
                st.plotly_chart(fig, width="stretch")
                st.caption(
                    "Only selected numeric columns from the uploaded file are shown. "
                    "This dashboard does not fetch or infer live social-media activity."
                )
            else:
                st.warning("The detected engagement fields contain no usable numeric values.")

elif nav_page == "Price Prediction":
    st.header("Price Prediction")
    st.write(
        "The comparison predicts the selected target one observation ahead. Features include known "
        "calendar values and lagged target/market fields from prior observations only."
    )
    results = train_for_selection(dataframe, date_column, price_column)
    if results:
        show_model_results(results)
        actual_predicted_chart(results)
        st.caption(
            "No accuracy is assumed in advance: the scores below are computed from this dataset's held-out test period."
        )

elif nav_page == "Model Evaluation":
    st.header("Model Evaluation")
    st.write(
        "Both models use the same chronological 80/20 split: earlier observations train the models, "
        "and the latest observations are held out for evaluation."
    )
    results = train_for_selection(dataframe, date_column, price_column)
    if results:
        show_model_results(results)
        st.subheader("Held-out test predictions")
        actual_predicted_chart(results)
        comparison = pd.DataFrame(
            {
                "Date": results["dates"],
                "Actual": results["actual"],
                **{f"{name} predicted": values for name, values in results["predictions"].items()},
            }
        )
        st.dataframe(comparison, width="stretch", hide_index=True)
        st.caption(
            "MAE and RMSE are in the target field's units. R² may be negative when predictions perform "
            "worse than predicting the test-set mean; it is not a percentage accuracy score."
        )
