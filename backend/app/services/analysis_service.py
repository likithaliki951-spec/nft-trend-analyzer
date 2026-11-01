"""Service layer for dataset loading, joining, and core exploratory analytics."""

from __future__ import annotations

import io
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from app.core.data_loader import (
    discover_join_keys,
    join_market_and_social_datasets,
    load_uploaded_dataset,
    validate_and_diagnose_dataset,
    validate_join_keys,
)
from app.core.nft_analysis import (
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


class AnalysisService:

    @staticmethod
    def get_demo_dataset(n_rows: int = 150) -> pd.DataFrame:
        """Generate educational demo NFT dataset."""
        df = make_synthetic_demo_data(rows=n_rows)
        cleaned_df, _ = clean_dataframe(df)
        return cleaned_df

    @staticmethod
    def process_file_upload(file_bytes: bytes, filename: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Parse raw uploaded file into cleaned DataFrame and diagnostics."""
        raw_df, meta = load_uploaded_dataset(file_bytes, filename)
        cleaned_df, _ = clean_dataframe(raw_df)
        diagnostics = validate_and_diagnose_dataset(cleaned_df)
        return cleaned_df, {
            "filename": filename,
            "raw_rows": meta.get("raw_rows", len(cleaned_df)),
            "clean_rows": len(cleaned_df),
            "columns": list(cleaned_df.columns),
            "extension": meta.get("extension", ""),
            "size_formatted": meta.get("size_formatted", ""),
            "diagnostics": diagnostics,
        }

    @staticmethod
    def join_datasets(
        market_bytes: bytes,
        market_name: str,
        social_bytes: bytes,
        social_name: str,
        market_key: str,
        social_key: str,
        how: str = "inner",
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Join separate market and social datasets."""
        merged_df, diag = join_market_and_social_datasets(
            market_bytes, market_name, social_bytes, social_name,
            market_key=market_key, social_key=social_key, how=how,
        )
        cleaned_df, _ = clean_dataframe(merged_df)
        return cleaned_df, diag

    @staticmethod
    def get_market_kpis(
        df: pd.DataFrame,
        date_col: Optional[str] = None,
        price_col: Optional[str] = None,
        sales_col: Optional[str] = None,
        collection_col: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compute comprehensive high-level market activity KPIs."""
        if df.empty:
            return {}

        d_col = date_col or infer_column(df, "date")
        p_col = price_col or infer_column(df, "price")
        s_col = sales_col or infer_column(df, "sales")
        c_col = collection_col or ("collection" if "collection" in df.columns else None)

        kpis = compute_market_kpis(df, p_col, s_col)
        unique_colls, detected_c = count_unique_assets(df)
        if not c_col:
            c_col = detected_c

        # Calculate collection distribution if column exists
        collection_breakdown = []
        if c_col and c_col in df.columns and p_col and p_col in df.columns:
            grouped = df.groupby(c_col).agg(
                total_volume=(p_col, "sum"),
                total_sales=(s_col if s_col in df.columns else p_col, "count"),
                avg_price=(p_col, "mean"),
            ).reset_index()
            grouped = grouped.sort_values(by="total_volume", ascending=False).head(10)
            collection_breakdown = grouped.to_dict(orient="records")

        start_date = str(df[d_col].min())[:10] if d_col and d_col in df.columns else "N/A"
        end_date = str(df[d_col].max())[:10] if d_col and d_col in df.columns else "N/A"

        total_sales = int(pd.to_numeric(df[s_col], errors="coerce").sum()) if s_col and s_col in df.columns else kpis.get("valid_records", len(df))
        total_volume = float(kpis.get("total_volume", 0.0))

        return {
            "date_column": d_col,
            "price_column": p_col,
            "sales_column": s_col,
            "collection_column": c_col,
            "total_sales": total_sales,
            "total_volume_eth": total_volume,
            "total_volume_usd": total_volume * 2800.0,
            "average_price_eth": float(kpis.get("avg_price", 0.0)),
            "median_price_eth": float(kpis.get("median_price", 0.0)),
            "unique_collections": unique_colls or 1,
            "date_range": {
                "start": start_date,
                "end": end_date,
            },
            "collection_breakdown": collection_breakdown,
        }

    @staticmethod
    def get_time_series_data(
        df: pd.DataFrame,
        date_col: Optional[str] = None,
        price_col: Optional[str] = None,
        sales_col: Optional[str] = None,
        freq: str = "D",
    ) -> List[Dict[str, Any]]:
        """Aggregate price and sales volume time series."""
        if df.empty:
            return []

        d_col = date_col or infer_column(df, "date")
        p_col = price_col or infer_column(df, "price")
        s_col = sales_col or infer_column(df, "sales")

        if not d_col or not p_col:
            return []

        work_df = df.copy()
        work_df["_dt"] = parse_dates(work_df[d_col])
        work_df = work_df.dropna(subset=["_dt"]).sort_values(by="_dt")

        work_df["_price"] = parse_numeric(work_df[p_col])
        if s_col and s_col in work_df.columns:
            work_df["_sales"] = parse_numeric(work_df[s_col]).fillna(1)
        else:
            work_df["_sales"] = 1

        work_df = work_df.set_index("_dt")
        # Resample
        resampled = work_df.resample(freq).agg(
            price_avg=("_price", "mean"),
            price_max=("_price", "max"),
            price_min=("_price", "min"),
            total_sales=("_sales", "sum"),
            total_volume=("_price", "sum"),
        ).reset_index()

        # Add 7-day rolling average
        resampled["price_7d_ma"] = resampled["price_avg"].rolling(7, min_periods=1).mean()

        # Fill NaNs
        resampled = resampled.fillna(0.0)
        resampled["date"] = resampled["_dt"].dt.strftime("%Y-%m-%d")
        return resampled[["date", "price_avg", "price_max", "price_min", "total_sales", "total_volume", "price_7d_ma"]].to_dict(orient="records")

    @staticmethod
    def get_social_engagement_data(
        df: pd.DataFrame,
        price_col: Optional[str] = None,
        social_cols: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Compute correlations between social engagement signals and asset prices."""
        if df.empty:
            return {}

        p_col = price_col or infer_column(df, "price")
        detected_social = social_cols or discover_social_columns(df)

        if not p_col or not detected_social:
            return {"price_column": p_col, "social_columns": [], "correlations": []}

        soc_list = [detected_social] if isinstance(detected_social, str) else list(detected_social)
        target_list = [p_col] if isinstance(p_col, str) else list(p_col)

        corr_df = compute_engagement_correlations(df, soc_list, target_list)
        correlations = []
        if not corr_df.empty:
            for _, r in corr_df.iterrows():
                feat = r.get("Engagement Metric") or r.get("feature")
                val = r.get("Pearson Correlation") if r.get("Pearson Correlation") is not None else (r.get("correlation") or 0.0)
                correlations.append({
                    "feature": feat,
                    "target": r.get("Market Metric") or p_col,
                    "pearson_correlation": float(val),
                    "correlation": float(val),
                    "observations": int(r.get("Observations", len(df))),
                })
            correlations.sort(key=lambda x: abs(x["pearson_correlation"]), reverse=True)

        # Scatter samples for the top correlated social feature
        scatter_points = []
        if correlations:
            top_feature = correlations[0]["feature"]
            if top_feature in df.columns and p_col in df.columns:
                sub_df = df[[top_feature, p_col]].dropna().head(100)
                scatter_points = [
                    {"x": float(r[top_feature]), "y": float(r[p_col])}
                    for _, r in sub_df.iterrows()
                ]

        return {
            "price_column": p_col,
            "social_columns": detected_social,
            "correlations": correlations,
            "top_feature": correlations[0]["feature"] if correlations else None,
            "scatter_samples": scatter_points,
        }
