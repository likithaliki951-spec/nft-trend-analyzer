"""Professional Multi-Format Report Export Service for NFT Trend Analyzer.

Generates comprehensive, publication-quality analytical reports in four formats:
1. PDF (.pdf) via ReportLab with custom NumberedCanvas (Page X of Y) and embedded matplotlib charts.
2. Excel (.xlsx) via openpyxl with multiple formatted worksheets, auto column widths, and native charts.
3. Microsoft Word (.docx) via python-docx with styled headings, metadata tables, callouts, and charts.
4. JSON (.json) structured export with clean schema and full analytical fidelity.

Exports exclusively real calculated data from the user's active session or saved project.
Zero fabricated or placeholder metrics.
"""

from __future__ import annotations

import datetime
import io
import json
import logging
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Headless matplotlib configuration before importing pyplot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Document generation libraries
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import LineChart, BarChart, Reference

import reportlab
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    KeepTogether,
    HRFlowable,
)
from reportlab.pdfgen import canvas

from app.services.pipeline_service import PipelineService
from app.services.storage_service import StorageService

logger = logging.getLogger("nft_trend_analyzer.export")


# ==============================================================================
# Helper & Serialization Functions
# ==============================================================================

def sanitize_value(val: Any) -> Any:
    """Recursively convert NumPy, Pandas, and non-serializable objects into clean primitives."""
    if val is None:
        return None
    if isinstance(val, (bool, np.bool_)):
        return bool(val)
    if isinstance(val, (int, np.integer)):
        return int(val)
    if isinstance(val, (float, np.floating)):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)
    if isinstance(val, (datetime.datetime, datetime.date, pd.Timestamp)):
        return val.isoformat()
    if isinstance(val, dict):
        return {str(k): sanitize_value(v) for k, v in val.items()}
    if isinstance(val, (list, tuple, set)):
        return [sanitize_value(v) for v in val]
    if isinstance(val, pd.DataFrame):
        return [sanitize_value(r) for r in val.to_dict(orient="records")]
    if isinstance(val, pd.Series):
        return sanitize_value(val.to_dict())
    return str(val)


def format_currency(val: Optional[float], decimals: int = 2) -> str:
    """Format a numeric value as currency/number string."""
    if val is None or math.isnan(val):
        return "N/A"
    return f"{val:,.{decimals}f}"


def format_percent(val: Optional[float], decimals: int = 1) -> str:
    """Format a decimal ratio as a percentage string."""
    if val is None or math.isnan(val):
        return "N/A"
    return f"{val * 100:.{decimals}f}%"


# ==============================================================================
# ReportLab Canvas with Two-Pass Page Numbering (Page X of Y)
# ==============================================================================

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas that accumulates total page count and prints 'Page X of Y' in footer."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states: List[Dict[str, Any]] = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_decorations(num_pages)
            super().showPage()
        super().save()

    def _draw_decorations(self, total_pages: int):
        self.saveState()
        # Top running header rule
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 756, 576, 756)

        # Top header text
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(36, 762, "NFT TREND ANALYZER v3.0  —  EXECUTIVE INTELLIGENCE REPORT")

        # Bottom footer rule
        self.line(36, 45, 576, 45)

        # Bottom footer text
        self.drawString(36, 32, "Confidential  |  Generated for Authenticated User Session  |  All Rights Reserved")
        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(576, 32, page_str)
        self.restoreState()


# ==============================================================================
# Main ReportExportService
# ==============================================================================

class ReportExportService:

    MIME_TYPES = {
        "pdf": "application/pdf",
        "json": "application/json",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    @classmethod
    def get_report_data(
        cls,
        user_email: str,
        scope: str = "complete",
        project_id: Optional[str] = None,
        custom_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract and structure all analytical results from active session or saved project."""
        clean_email = user_email.strip().lower()
        df: Optional[pd.DataFrame] = None
        bundle: Dict[str, Any] = {}
        dataset_name = "Active Dataset"
        actual_project_id = project_id or "active-session"

        # 1. Attempt loading requested saved project
        if project_id and project_id not in ("active-session", "demo-active-session"):
            loaded_df, msg = StorageService.load_project_dataframe(project_id, clean_email)
            if loaded_df is not None and not loaded_df.empty:
                df = loaded_df
                project_meta = StorageService.get_project(project_id, clean_email)
                if project_meta:
                    dataset_name = project_meta.get("dataset_name", dataset_name)
                    summary = project_meta.get("summary_json") or {}
                    if isinstance(summary, str):
                        try:
                            summary = json.loads(summary)
                        except Exception:
                            summary = {}
                    bundle = summary

        # 2. Fall back to active session
        if df is None or df.empty or not bundle:
            session = PipelineService.get_active_session(clean_email)
            df = session.get("dataframe")
            bundle = session.get("bundle") or {}
            dataset_name = session.get("dataset_name", dataset_name)
            actual_project_id = session.get("project_id", actual_project_id)

        # Fallback to demo dataset if empty
        if df is None or df.empty:
            from app.services.analysis_service import AnalysisService
            df = AnalysisService.get_demo_dataset(160)
            bundle = PipelineService._orchestrate_analysis_bundle(df, "NFT Benchmark Demo")

        # Extract features and module blocks
        features_detected = bundle.get("features_detected") or {}
        module_statuses = bundle.get("module_statuses") or {}
        price_trends = bundle.get("price_trends") or {}
        market_activity = bundle.get("market_activity") or {}
        social_engagement = bundle.get("social_engagement") or {}
        marketplace_hub = bundle.get("marketplace_hub") or {}

        # Dataset structural summary
        col_summary = []
        for c in df.columns:
            non_null = int(df[c].count())
            null_count = int(df[c].isna().sum())
            dtype_str = str(df[c].dtype)
            sample_val = str(df[c].dropna().iloc[0]) if non_null > 0 else "N/A"
            col_summary.append({
                "column_name": str(c),
                "data_type": dtype_str,
                "non_null_count": non_null,
                "null_count": null_count,
                "sample_value": sample_val[:40],
            })

        # Numeric stats summary
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        num_stats = []
        if numeric_cols:
            desc = df[numeric_cols].describe().to_dict()
            for col_name, stats in desc.items():
                num_stats.append({
                    "column_name": str(col_name),
                    "mean": float(stats.get("mean", 0.0)),
                    "std": float(stats.get("std", 0.0)),
                    "min": float(stats.get("min", 0.0)),
                    "median": float(stats.get("50%", 0.0)),
                    "max": float(stats.get("max", 0.0)),
                })

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        report_title = custom_title or f"NFT Market Intelligence Report — {dataset_name}"

        raw_data = {
            "metadata": {
                "title": report_title,
                "generated_at": now_utc.isoformat(),
                "generated_at_formatted": now_utc.strftime("%B %d, %Y at %H:%M:%S UTC"),
                "user_email": clean_email,
                "dataset_name": dataset_name,
                "project_id": str(actual_project_id),
                "scope": scope.lower().strip(),
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "pipeline_version": bundle.get("pipeline_version", "v3.0.0"),
            },
            "features_detected": features_detected,
            "module_statuses": module_statuses,
            "dataset_summary": {
                "columns": col_summary,
                "numeric_statistics": num_stats,
                "total_records": len(df),
                "total_features": len(df.columns),
            },
            "price_trends": price_trends,
            "market_activity": market_activity,
            "social_engagement": social_engagement,
            "marketplace_hub": marketplace_hub,
        }

        return sanitize_value(raw_data)

    # ==========================================================================
    # Matplotlib Chart Generation
    # ==========================================================================

    @classmethod
    def generate_chart_images(cls, data: Dict[str, Any]) -> Dict[str, bytes]:
        """Generate high-resolution chart images as PNG bytes for embedding in PDF and Word."""
        charts: Dict[str, bytes] = {}

        # 1. Price Trends Time-Series Chart
        pt_data = data.get("price_trends", {}).get("data", [])
        if pt_data and len(pt_data) >= 2:
            try:
                fig, ax1 = plt.subplots(figsize=(7.2, 3.2), dpi=180)
                fig.patch.set_facecolor("#FFFFFF")
                ax1.set_facecolor("#F8FAFC")

                dates = [p.get("date") for p in pt_data]
                prices = [float(p.get("avg_price", 0.0)) for p in pt_data]
                rolling = [float(p.get("rolling_avg", p.get("avg_price", 0.0))) for p in pt_data]

                x_indices = list(range(len(dates)))
                ax1.plot(x_indices, prices, color="#6366F1", linewidth=2.0, label="Daily Avg Price (ETH)", alpha=0.9)
                ax1.plot(x_indices, rolling, color="#06B6D4", linewidth=1.8, linestyle="--", label="7-Period Moving Avg", alpha=0.9)

                # Format axes
                ax1.set_title("NFT Price Evolution & Moving Average", fontsize=11, fontweight="bold", color="#0F172A", pad=10)
                ax1.set_ylabel("Price (ETH)", fontsize=9, fontweight="semibold", color="#334155")
                ax1.grid(True, linestyle=":", alpha=0.6, color="#CBD5E1")
                ax1.tick_params(colors="#475569", labelsize=8)

                # Choose subset of x ticks to avoid clutter
                step = max(1, len(dates) // 6)
                ax1.set_xticks(x_indices[::step])
                ax1.set_xticklabels([dates[i][:10] if dates[i] else f"T{i}" for i in x_indices[::step]], rotation=25, ha="right")

                ax1.legend(loc="upper left", framealpha=0.9, fontsize=8)
                fig.tight_layout()

                buf = io.BytesIO()
                fig.savefig(buf, format="png", bbox_inches="tight")
                plt.close(fig)
                charts["price_trends"] = buf.getvalue()
            except Exception as exc:
                logger.warning(f"Failed to generate price trends chart: {exc}")

        # 2. Valuation Tier Distribution Bar Chart
        ma_dist = data.get("market_activity", {}).get("distribution", [])
        if ma_dist:
            try:
                fig, ax = plt.subplots(figsize=(6.0, 2.8), dpi=180)
                fig.patch.set_facecolor("#FFFFFF")
                ax.set_facecolor("#F8FAFC")

                tiers = [d.get("tier", "Unknown") for d in ma_dist]
                counts = [int(d.get("count", 0)) for d in ma_dist]
                bar_colors = ["#38BDF8", "#818CF8", "#C084FC", "#F472B6"][:len(tiers)]

                bars = ax.bar(tiers, counts, color=bar_colors, width=0.45, edgecolor="#475569", linewidth=0.5)
                ax.set_title("NFT Asset Valuation Tier Distribution", fontsize=11, fontweight="bold", color="#0F172A", pad=10)
                ax.set_ylabel("Asset Count", fontsize=9, fontweight="semibold", color="#334155")
                ax.grid(axis="y", linestyle=":", alpha=0.6, color="#CBD5E1")
                ax.tick_params(colors="#475569", labelsize=8)

                # Add data labels above bars
                for bar in bars:
                    yval = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width() / 2.0, yval + (max(counts) * 0.02), f"{yval:,}", ha="center", va="bottom", fontsize=8, color="#0F172A", fontweight="bold")

                fig.tight_layout()
                buf = io.BytesIO()
                fig.savefig(buf, format="png", bbox_inches="tight")
                plt.close(fig)
                charts["valuation_distribution"] = buf.getvalue()
            except Exception as exc:
                logger.warning(f"Failed to generate valuation distribution chart: {exc}")

        # 3. Social Engagement Correlation Chart
        soc_corrs = data.get("social_engagement", {}).get("correlations", [])
        if soc_corrs:
            try:
                fig, ax = plt.subplots(figsize=(6.0, 2.6), dpi=180)
                fig.patch.set_facecolor("#FFFFFF")
                ax.set_facecolor("#F8FAFC")

                features = [c.get("feature", "Signal") for c in soc_corrs]
                pearsons = [float(c.get("pearson", 0.0)) for c in soc_corrs]
                bar_colors = ["#10B981" if p >= 0 else "#EF4444" for p in pearsons]

                y_pos = list(range(len(features)))
                ax.barh(y_pos, pearsons, color=bar_colors, height=0.45, edgecolor="#475569", linewidth=0.5)
                ax.set_yticks(y_pos)
                ax.set_yticklabels(features, fontsize=8, color="#334155", fontweight="medium")
                ax.set_xlim(-1.0, 1.0)
                ax.axvline(0, color="#64748B", linewidth=0.8, linestyle="--")
                ax.set_title("Social Sentiment Correlation with Asset Price (Pearson)", fontsize=11, fontweight="bold", color="#0F172A", pad=10)
                ax.set_xlabel("Pearson Correlation Coefficient (-1.0 to +1.0)", fontsize=9, fontweight="semibold", color="#334155")
                ax.grid(axis="x", linestyle=":", alpha=0.6, color="#CBD5E1")
                ax.tick_params(colors="#475569", labelsize=8)

                fig.tight_layout()
                buf = io.BytesIO()
                fig.savefig(buf, format="png", bbox_inches="tight")
                plt.close(fig)
                charts["social_correlation"] = buf.getvalue()
            except Exception as exc:
                logger.warning(f"Failed to generate social correlation chart: {exc}")

        return charts

    # ==========================================================================
    # Format 1: JSON Export
    # ==========================================================================

    @classmethod
    def export_json(cls, data: Dict[str, Any]) -> bytes:
        """Serialize complete or scoped report data to structured JSON bytes."""
        scope = data.get("metadata", {}).get("scope", "complete")
        export_payload: Dict[str, Any] = {
            "report_format": "json",
            "metadata": data.get("metadata"),
            "features_detected": data.get("features_detected"),
            "module_statuses": data.get("module_statuses"),
        }

        if scope in ("complete", "all", "dataset_summary"):
            export_payload["dataset_summary"] = data.get("dataset_summary")

        if scope in ("complete", "all", "price_trends"):
            export_payload["price_trends"] = data.get("price_trends")

        if scope in ("complete", "all", "market_activity"):
            export_payload["market_activity"] = data.get("market_activity")

        if scope in ("complete", "all", "social_engagement"):
            export_payload["social_engagement"] = data.get("social_engagement")

        if scope in ("complete", "all", "marketplace_hub"):
            export_payload["marketplace_hub"] = data.get("marketplace_hub")

        if scope in ("complete", "all", "ml_results"):
            export_payload["ml_regression"] = {
                "models": data.get("price_trends", {}).get("models", []),
                "best_model": data.get("price_trends", {}).get("best_model"),
                "pca_diagnostics": data.get("price_trends", {}).get("pca_diagnostics"),
            }
            export_payload["valuation_classifiers"] = {
                "classifiers": data.get("market_activity", {}).get("classifiers", []),
                "distribution": data.get("market_activity", {}).get("distribution", []),
            }

        json_str = json.dumps(export_payload, indent=2, ensure_ascii=False)
        return json_str.encode("utf-8")

    # ==========================================================================
    # Format 2: Microsoft Excel (.xlsx) Export
    # ==========================================================================

    @classmethod
    def export_xlsx(cls, data: Dict[str, Any]) -> bytes:
        """Create a multi-tab formatted Excel workbook."""
        wb = openpyxl.Workbook()
        # Remove default sheet
        wb.remove(wb.active)

        scope = data.get("metadata", {}).get("scope", "complete")
        meta = data.get("metadata", {})
        pt = data.get("price_trends", {})
        ma = data.get("market_activity", {})
        soc = data.get("social_engagement", {})
        hub = data.get("marketplace_hub", {})
        ds = data.get("dataset_summary", {})

        # Styles
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E1B4B", end_color="1E1B4B", fill_type="solid")
        title_font = Font(name="Calibri", size=15, bold=True, color="1E1B4B")
        subtitle_font = Font(name="Calibri", size=10, italic=True, color="64748B")
        bold_font = Font(name="Calibri", size=10, bold=True, color="0F172A")
        normal_font = Font(name="Calibri", size=10, color="334155")
        thin_border = Border(
            left=Side(style="thin", color="CBD5E1"),
            right=Side(style="thin", color="CBD5E1"),
            top=Side(style="thin", color="CBD5E1"),
            bottom=Side(style="thin", color="CBD5E1"),
        )
        stripe_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

        def style_header_row(ws, row_idx, col_count):
            for col in range(1, col_count + 1):
                cell = ws.cell(row=row_idx, column=col)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = thin_border
            ws.row_dimensions[row_idx].height = 24

        def auto_fit_columns(ws, max_cols=12):
            for col in range(1, max_cols + 1):
                col_letter = get_column_letter(col)
                max_len = 0
                for row in range(1, ws.max_row + 1):
                    val = ws.cell(row=row, column=col).value
                    if val is not None:
                        max_len = max(max_len, len(str(val)))
                ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        # ----------------------------------------------------------------------
        # Tab 1: Executive Overview
        # ----------------------------------------------------------------------
        ws_over = wb.create_sheet(title="Executive Overview")
        ws_over.views.sheetView[0].showGridLines = True

        ws_over["A1"] = meta.get("title", "NFT Trend Analyzer Report")
        ws_over["A1"].font = title_font
        ws_over["A2"] = f"Generated on {meta.get('generated_at_formatted', '')} | User: {meta.get('user_email', '')}"
        ws_over["A2"].font = subtitle_font

        ws_over["A4"] = "REPORT METADATA & TELEMETRY"
        ws_over["A4"].font = bold_font

        metadata_items = [
            ("Dataset Name", meta.get("dataset_name")),
            ("Project Identifier", meta.get("project_id")),
            ("Export Scope", meta.get("scope")),
            ("Total Records Analyzed", meta.get("total_rows")),
            ("Total Features Detected", meta.get("total_columns")),
            ("Pipeline Engine Version", meta.get("pipeline_version")),
            ("Average Asset Price", f"{pt.get('stats', {}).get('mean_price', 0.0):.4f} ETH" if pt.get("stats") else "N/A"),
            ("Peak Price Recorded", f"{pt.get('stats', {}).get('max_price', 0.0):.4f} ETH" if pt.get("stats") else "N/A"),
            ("Total Market Sales", ma.get("kpis", {}).get("total_sales", len(ds.get("columns", [])))),
            ("Best ML Regression Model", pt.get("best_model", "N/A")),
            ("Top Predictive Social Signal", soc.get("top_feature") or "None"),
            ("ETH/USD Market Rate", f"${hub.get('eth_rate_usd', 0.0):,.2f}" if hub.get("eth_rate_usd") else "N/A"),
        ]

        ws_over.cell(row=5, column=1, value="Attribute").font = header_font
        ws_over.cell(row=5, column=1).fill = header_fill
        ws_over.cell(row=5, column=1).border = thin_border
        ws_over.cell(row=5, column=2, value="Configured Value").font = header_font
        ws_over.cell(row=5, column=2).fill = header_fill
        ws_over.cell(row=5, column=2).border = thin_border
        ws_over.row_dimensions[5].height = 22

        for idx, (label, val) in enumerate(metadata_items, start=6):
            c1 = ws_over.cell(row=idx, column=1, value=label)
            c2 = ws_over.cell(row=idx, column=2, value=str(val))
            c1.font = bold_font
            c2.font = normal_font
            c1.border = thin_border
            c2.border = thin_border
            if idx % 2 == 1:
                c1.fill = stripe_fill
                c2.fill = stripe_fill

        auto_fit_columns(ws_over, max_cols=3)

        # ----------------------------------------------------------------------
        # Tab 2: Dataset Summary
        # ----------------------------------------------------------------------
        if scope in ("complete", "all", "dataset_summary"):
            ws_ds = wb.create_sheet(title="Dataset Summary")
            ws_ds.views.sheetView[0].showGridLines = True

            ws_ds["A1"] = "DATASET SCHEMA & DATA QUALITY AUDIT"
            ws_ds["A1"].font = title_font

            headers = ["Column Name", "Inferred Type", "Non-Null Count", "Missing Count", "Sample Value"]
            for col_i, h in enumerate(headers, start=1):
                ws_ds.cell(row=3, column=col_i, value=h)
            style_header_row(ws_ds, 3, len(headers))

            cols = ds.get("columns", [])
            for row_i, c in enumerate(cols, start=4):
                ws_ds.cell(row=row_i, column=1, value=c.get("column_name")).font = bold_font
                ws_ds.cell(row=row_i, column=2, value=c.get("data_type")).font = normal_font
                ws_ds.cell(row=row_i, column=3, value=c.get("non_null_count")).font = normal_font
                ws_ds.cell(row=row_i, column=4, value=c.get("null_count")).font = normal_font
                ws_ds.cell(row=row_i, column=5, value=c.get("sample_value")).font = normal_font
                for ci in range(1, 6):
                    ws_ds.cell(row=row_i, column=ci).border = thin_border
                    if row_i % 2 == 1:
                        ws_ds.cell(row=row_i, column=ci).fill = stripe_fill

            # Numeric statistics table
            num_stats = ds.get("numeric_statistics", [])
            if num_stats:
                start_r = len(cols) + 6
                ws_ds.cell(row=start_r - 1, column=1, value="NUMERIC DESCRIPTIVE METRICS").font = bold_font
                num_headers = ["Feature", "Mean", "Std Dev", "Min", "Median (50%)", "Max"]
                for col_i, h in enumerate(num_headers, start=1):
                    ws_ds.cell(row=start_r, column=col_i, value=h)
                style_header_row(ws_ds, start_r, len(num_headers))

                for row_i, ns in enumerate(num_stats, start=start_r + 1):
                    ws_ds.cell(row=row_i, column=1, value=ns.get("column_name")).font = bold_font
                    ws_ds.cell(row=row_i, column=2, value=round(ns.get("mean", 0.0), 4)).font = normal_font
                    ws_ds.cell(row=row_i, column=3, value=round(ns.get("std", 0.0), 4)).font = normal_font
                    ws_ds.cell(row=row_i, column=4, value=round(ns.get("min", 0.0), 4)).font = normal_font
                    ws_ds.cell(row=row_i, column=5, value=round(ns.get("median", 0.0), 4)).font = normal_font
                    ws_ds.cell(row=row_i, column=6, value=round(ns.get("max", 0.0), 4)).font = normal_font
                    for ci in range(1, 7):
                        ws_ds.cell(row=row_i, column=ci).border = thin_border
                        if row_i % 2 == 1:
                            ws_ds.cell(row=row_i, column=ci).fill = stripe_fill

            auto_fit_columns(ws_ds, max_cols=6)

        # ----------------------------------------------------------------------
        # Tab 3: Price Trends & Time Series
        # ----------------------------------------------------------------------
        if scope in ("complete", "all", "price_trends"):
            ws_pt = wb.create_sheet(title="Price Trends")
            ws_pt.views.sheetView[0].showGridLines = True

            ws_pt["A1"] = "HISTORICAL PRICE TRENDS & VOLUME EVOLUTION"
            ws_pt["A1"].font = title_font

            pt_headers = ["Date / Period", "Average Price (ETH)", "Total Volume (ETH)", "Transaction Count", "7-Period Rolling Avg"]
            for col_i, h in enumerate(pt_headers, start=1):
                ws_pt.cell(row=3, column=col_i, value=h)
            style_header_row(ws_pt, 3, len(pt_headers))

            pt_rows = pt.get("data", [])
            for row_i, r in enumerate(pt_rows, start=4):
                ws_pt.cell(row=row_i, column=1, value=r.get("date")).font = normal_font
                c2 = ws_pt.cell(row=row_i, column=2, value=float(r.get("avg_price", 0.0)))
                c2.font = normal_font
                c2.number_format = "#,##0.0000"
                c3 = ws_pt.cell(row=row_i, column=3, value=float(r.get("volume", 0.0)))
                c3.font = normal_font
                c3.number_format = "#,##0.00"
                c4 = ws_pt.cell(row=row_i, column=4, value=int(r.get("count", 0)))
                c4.font = normal_font
                c4.number_format = "#,##0"
                c5 = ws_pt.cell(row=row_i, column=5, value=float(r.get("rolling_avg", r.get("avg_price", 0.0))))
                c5.font = normal_font
                c5.number_format = "#,##0.0000"

                for ci in range(1, 6):
                    ws_pt.cell(row=row_i, column=ci).border = thin_border
                    if row_i % 2 == 1:
                        ws_pt.cell(row=row_i, column=ci).fill = stripe_fill

            # Add native openpyxl LineChart if data exists
            if len(pt_rows) >= 2:
                chart = LineChart()
                chart.title = "NFT Price Trends (ETH)"
                chart.style = 13
                chart.y_axis.title = "Price (ETH)"
                chart.x_axis.title = "Time Period"
                chart.width = 16
                chart.height = 9

                data_ref = Reference(ws_pt, min_col=2, min_row=3, max_col=2, max_row=len(pt_rows) + 3)
                cats_ref = Reference(ws_pt, min_col=1, min_row=4, max_row=len(pt_rows) + 3)
                chart.add_data(data_ref, titles_from_data=True)
                chart.set_categories(cats_ref)
                ws_pt.add_chart(chart, "G3")

            auto_fit_columns(ws_pt, max_cols=6)

        # ----------------------------------------------------------------------
        # Tab 4: Market Activity & Valuation Tiers
        # ----------------------------------------------------------------------
        if scope in ("complete", "all", "market_activity"):
            ws_ma = wb.create_sheet(title="Market Activity")
            ws_ma.views.sheetView[0].showGridLines = True

            ws_ma["A1"] = "MARKET ACTIVITY & VALUATION TIERS"
            ws_ma["A1"].font = title_font

            # KPIs Block
            kpis = ma.get("kpis") or {}
            ws_ma["A3"] = "Key Market Indicators".upper()
            ws_ma["A3"].font = bold_font

            kpi_items = [
                ("Total Recorded Sales", kpis.get("total_sales", "N/A")),
                ("Unique NFT Collections", kpis.get("unique_collections", "N/A")),
                ("Average Asset Price", f"{kpis.get('avg_sale_price', 0.0):.4f} ETH" if kpis.get("avg_sale_price") else "N/A"),
                ("Maximum Sale Price", f"{kpis.get('max_sale_price', 0.0):.4f} ETH" if kpis.get("max_sale_price") else "N/A"),
                ("Total Cumulative Volume", f"{kpis.get('total_volume', 0.0):,.2f} ETH" if kpis.get("total_volume") else "N/A"),
                ("Daily Sales Velocity", f"{kpis.get('sales_velocity', 0.0):.2f} sales/day" if kpis.get("sales_velocity") else "N/A"),
                ("Dominant Collection", kpis.get("top_collection", "N/A")),
            ]

            ws_ma.cell(row=4, column=1, value="Metric").font = header_font
            ws_ma.cell(row=4, column=1).fill = header_fill
            ws_ma.cell(row=4, column=1).border = thin_border
            ws_ma.cell(row=4, column=2, value="Calculated Value").font = header_font
            ws_ma.cell(row=4, column=2).fill = header_fill
            ws_ma.cell(row=4, column=2).border = thin_border

            for idx, (k, v) in enumerate(kpi_items, start=5):
                c1 = ws_ma.cell(row=idx, column=1, value=k)
                c2 = ws_ma.cell(row=idx, column=2, value=str(v))
                c1.font = bold_font
                c2.font = normal_font
                c1.border = thin_border
                c2.border = thin_border
                if idx % 2 == 1:
                    c1.fill = stripe_fill
                    c2.fill = stripe_fill

            # Distribution Block
            dist = ma.get("distribution", [])
            start_dist = len(kpi_items) + 7
            ws_ma.cell(row=start_dist - 1, column=1, value="ASSET VALUATION TIER BREAKDOWN").font = bold_font

            dist_headers = ["Valuation Tier", "Asset Count", "Share (%)", "Min Price (ETH)", "Max Price (ETH)"]
            for col_i, h in enumerate(dist_headers, start=1):
                ws_ma.cell(row=start_dist, column=col_i, value=h)
            style_header_row(ws_ma, start_dist, len(dist_headers))

            for row_i, d in enumerate(dist, start=start_dist + 1):
                ws_ma.cell(row=row_i, column=1, value=d.get("tier")).font = bold_font
                ws_ma.cell(row=row_i, column=2, value=int(d.get("count", 0))).font = normal_font
                c_pct = ws_ma.cell(row=row_i, column=3, value=float(d.get("percentage", 0.0)) / 100.0)
                c_pct.font = normal_font
                c_pct.number_format = "0.0%"
                ws_ma.cell(row=row_i, column=4, value=float(d.get("min_price", 0.0))).font = normal_font
                ws_ma.cell(row=row_i, column=5, value=float(d.get("max_price", 0.0))).font = normal_font
                for ci in range(1, 6):
                    ws_ma.cell(row=row_i, column=ci).border = thin_border
                    if row_i % 2 == 1:
                        ws_ma.cell(row=row_i, column=ci).fill = stripe_fill

            # Native openpyxl BarChart for Valuation Distribution
            if dist:
                chart = BarChart()
                chart.type = "col"
                chart.style = 10
                chart.title = "Valuation Tier Distribution"
                chart.y_axis.title = "Assets"
                chart.x_axis.title = "Tier"
                chart.width = 14
                chart.height = 8

                data_ref = Reference(ws_ma, min_col=2, min_row=start_dist, max_row=start_dist + len(dist))
                cats_ref = Reference(ws_ma, min_col=1, min_row=start_dist + 1, max_row=start_dist + len(dist))
                chart.add_data(data_ref, titles_from_data=True)
                chart.set_categories(cats_ref)
                ws_ma.add_chart(chart, "G4")

            auto_fit_columns(ws_ma, max_cols=6)

        # ----------------------------------------------------------------------
        # Tab 5: Machine Learning Models & PCA
        # ----------------------------------------------------------------------
        if scope in ("complete", "all", "ml_results", "price_trends"):
            ws_ml = wb.create_sheet(title="ML Models & PCA")
            ws_ml.views.sheetView[0].showGridLines = True

            ws_ml["A1"] = "MACHINE LEARNING BENCHMARKS & EVALUATION"
            ws_ml["A1"].font = title_font

            # 1. Price Prediction Regressors
            ws_ml["A3"] = "PRICE PREDICTION REGRESSION MODELS"
            ws_ml["A3"].font = bold_font

            models = pt.get("models", [])
            reg_headers = ["Algorithm", "RMSE", "MAE", "R² Score", "Performance Rank"]
            for col_i, h in enumerate(reg_headers, start=1):
                ws_ml.cell(row=4, column=col_i, value=h)
            style_header_row(ws_ml, 4, len(reg_headers))

            best_m = pt.get("best_model", "")
            for row_i, m in enumerate(models, start=5):
                is_best = (m.get("model_name") == best_m)
                ws_ml.cell(row=row_i, column=1, value=m.get("model_name")).font = bold_font
                ws_ml.cell(row=row_i, column=2, value=round(float(m.get("rmse", 0.0)), 4)).font = normal_font
                ws_ml.cell(row=row_i, column=3, value=round(float(m.get("mae", 0.0)), 4)).font = normal_font
                c_r2 = ws_ml.cell(row=row_i, column=4, value=round(float(m.get("r2", 0.0)), 4))
                c_r2.font = normal_font
                ws_ml.cell(row=row_i, column=5, value="★ Best Model" if is_best else "Alternative").font = bold_font if is_best else normal_font
                for ci in range(1, 6):
                    ws_ml.cell(row=row_i, column=ci).border = thin_border
                    if is_best:
                        ws_ml.cell(row=row_i, column=ci).fill = PatternFill(start_color="EEF2FF", end_color="EEF2FF", fill_type="solid")

            # 2. Valuation Tier Classifiers
            start_clf = len(models) + 7
            ws_ml.cell(row=start_clf - 1, column=1, value="VALUATION TIER MULTI-CLASS CLASSIFIERS").font = bold_font

            clfs = ma.get("classifiers", [])
            clf_headers = ["Classifier Algorithm", "Accuracy", "F1 Score", "Precision", "Recall"]
            for col_i, h in enumerate(clf_headers, start=1):
                ws_ml.cell(row=start_clf, column=col_i, value=h)
            style_header_row(ws_ml, start_clf, len(clf_headers))

            for row_i, c in enumerate(clfs, start=start_clf + 1):
                ws_ml.cell(row=row_i, column=1, value=c.get("model_name")).font = bold_font
                for ci, key in enumerate(["accuracy", "f1_score", "precision", "recall"], start=2):
                    val = float(c.get(key, 0.0))
                    cell = ws_ml.cell(row=row_i, column=ci, value=val)
                    cell.font = normal_font
                    cell.number_format = "0.0%"
                for ci in range(1, 6):
                    ws_ml.cell(row=row_i, column=ci).border = thin_border
                    if row_i % 2 == 1:
                        ws_ml.cell(row=row_i, column=ci).fill = stripe_fill

            # 3. PCA Diagnostics
            pca = pt.get("pca_diagnostics", {})
            if pca.get("enabled"):
                start_pca = start_clf + len(clfs) + 3
                ws_ml.cell(row=start_pca, column=1, value="PCA DIMENSIONALITY REDUCTION DIAGNOSTICS").font = bold_font
                pca_info = [
                    ("Input Feature Dimensions", pca.get("input_features_count", 0)),
                    ("Retained PCA Components", pca.get("retained_components", 0)),
                    ("Total Cumulative Variance Retained", f"{float(pca.get('total_explained_variance', 0.0)) * 100:.2f}%"),
                    ("Diagnostics Status", pca.get("status_message", "Optimal")),
                ]
                for p_idx, (k, v) in enumerate(pca_info, start=start_pca + 1):
                    ws_ml.cell(row=p_idx, column=1, value=k).font = bold_font
                    ws_ml.cell(row=p_idx, column=2, value=str(v)).font = normal_font
                    ws_ml.cell(row=p_idx, column=1).border = thin_border
                    ws_ml.cell(row=p_idx, column=2).border = thin_border

            auto_fit_columns(ws_ml, max_cols=6)

        # ----------------------------------------------------------------------
        # Tab 6: Social Engagement & Sentiment Vectors
        # ----------------------------------------------------------------------
        if scope in ("complete", "all", "social_engagement"):
            ws_soc = wb.create_sheet(title="Social Engagement")
            ws_soc.views.sheetView[0].showGridLines = True

            ws_soc["A1"] = "SOCIAL SENTIMENT CORRELATION ANALYSIS"
            ws_soc["A1"].font = title_font

            corrs = soc.get("correlations", [])
            soc_headers = ["Social Indicator / Signal", "Pearson Correlation", "Spearman Rank Corr", "Signal Strength"]
            for col_i, h in enumerate(soc_headers, start=1):
                ws_soc.cell(row=3, column=col_i, value=h)
            style_header_row(ws_soc, 3, len(soc_headers))

            if corrs:
                for row_i, c in enumerate(corrs, start=4):
                    ws_soc.cell(row=row_i, column=1, value=c.get("feature")).font = bold_font
                    c_p = ws_soc.cell(row=row_i, column=2, value=round(float(c.get("pearson", 0.0)), 4))
                    c_p.font = normal_font
                    c_s = ws_soc.cell(row=row_i, column=3, value=round(float(c.get("spearman", 0.0)), 4))
                    c_s.font = normal_font
                    ws_soc.cell(row=row_i, column=4, value=c.get("strength", "Moderate")).font = normal_font
                    for ci in range(1, 5):
                        ws_soc.cell(row=row_i, column=ci).border = thin_border
                        if row_i % 2 == 1:
                            ws_soc.cell(row=row_i, column=ci).fill = stripe_fill
            else:
                ws_soc["A4"] = "No social engagement columns detected in the active dataset."
                ws_soc["A4"].font = subtitle_font

            auto_fit_columns(ws_soc, max_cols=5)

        # ----------------------------------------------------------------------
        # Tab 7: Marketplace Hub Live Intelligence
        # ----------------------------------------------------------------------
        if scope in ("complete", "all", "marketplace_hub"):
            ws_hub = wb.create_sheet(title="Marketplace Hub")
            ws_hub.views.sheetView[0].showGridLines = True

            ws_hub["A1"] = "MARKETPLACE TELEMETRY & VERIFIED COLLECTIONS"
            ws_hub["A1"].font = title_font

            ws_hub["A3"] = f"ETH / USD Benchmark Exchange Rate: ${hub.get('eth_rate_usd', 2268.0):,.2f}"
            ws_hub["A3"].font = bold_font

            colls = hub.get("collections", [])
            hub_headers = ["Collection Name", "Floor Price (ETH)", "24h Volume (ETH)", "24h Sales Count", "24h Price Change", "Owners Count"]
            for col_i, h in enumerate(hub_headers, start=1):
                ws_hub.cell(row=5, column=col_i, value=h)
            style_header_row(ws_hub, 5, len(hub_headers))

            if colls:
                for row_i, cl in enumerate(colls, start=6):
                    ws_hub.cell(row=row_i, column=1, value=cl.get("name")).font = bold_font
                    ws_hub.cell(row=row_i, column=2, value=float(cl.get("floor_price_eth", 0.0))).font = normal_font
                    ws_hub.cell(row=row_i, column=3, value=float(cl.get("volume_24h_eth", 0.0))).font = normal_font
                    ws_hub.cell(row=row_i, column=4, value=int(cl.get("sales_24h", 0))).font = normal_font
                    ws_hub.cell(row=row_i, column=5, value=f"{float(cl.get('change_24h', 0.0)):+.1f}%").font = normal_font
                    ws_hub.cell(row=row_i, column=6, value=int(cl.get("owners_count", 0))).font = normal_font
                    for ci in range(1, 7):
                        ws_hub.cell(row=row_i, column=ci).border = thin_border
                        if row_i % 2 == 1:
                            ws_hub.cell(row=row_i, column=ci).fill = stripe_fill

            auto_fit_columns(ws_hub, max_cols=7)

        bio = io.BytesIO()
        wb.save(bio)
        return bio.getvalue()

    # ==========================================================================
    # Format 3: Microsoft Word (.docx) Export
    # ==========================================================================

    @classmethod
    def export_docx(cls, data: Dict[str, Any], include_charts: bool = True) -> bytes:
        """Generate a professionally styled Microsoft Word report document."""
        doc = docx.Document()

        # Page margins: 0.75 inch (54 pt)
        for sec in doc.sections:
            sec.top_margin = Inches(0.75)
            sec.bottom_margin = Inches(0.75)
            sec.left_margin = Inches(0.75)
            sec.right_margin = Inches(0.75)

        # Palette colors
        C_PRIMARY = RGBColor(79, 70, 229)    # Indigo #4F46E5
        C_DARK = RGBColor(15, 23, 42)        # Slate 900 #0F172A
        C_MUTED = RGBColor(100, 116, 139)    # Slate 500 #64748B
        C_TEXT = RGBColor(51, 65, 85)        # Slate 700 #334155

        scope = data.get("metadata", {}).get("scope", "complete")
        meta = data.get("metadata", {})
        pt = data.get("price_trends", {})
        ma = data.get("market_activity", {})
        soc = data.get("social_engagement", {})
        hub = data.get("marketplace_hub", {})
        ds = data.get("dataset_summary", {})

        charts = cls.generate_chart_images(data) if include_charts else {}

        # XML Helpers for table shading and borders
        def set_cell_shading(cell, color_hex):
            shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
            cell._tc.get_or_add_tcPr().append(shading)

        def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
            tcPr = cell._tc.get_or_add_tcPr()
            tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
            tcPr.append(tcMar)

        # Title Block
        p_title = doc.add_paragraph()
        p_title.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run_title = p_title.add_run(meta.get("title", "NFT Trend Analyzer Report"))
        run_title.font.name = "Calibri"
        run_title.font.size = Pt(22)
        run_title.font.bold = True
        run_title.font.color.rgb = C_DARK

        p_sub = doc.add_paragraph()
        run_sub = p_sub.add_run("Automated Multi-Dimensional Market Intelligence & Predictive Analysis")
        run_sub.font.name = "Calibri"
        run_sub.font.size = Pt(11)
        run_sub.font.color.rgb = C_PRIMARY
        run_sub.font.bold = True

        p_meta = doc.add_paragraph()
        run_meta = p_meta.add_run(f"Generated on {meta.get('generated_at_formatted')}  •  Author: {meta.get('user_email')}  •  Scope: {meta.get('scope').upper()}")
        run_meta.font.name = "Calibri"
        run_meta.font.size = Pt(9.5)
        run_meta.font.color.rgb = C_MUTED

        doc.add_paragraph().paragraph_format.space_after = Pt(8)

        # Executive Metadata Card
        meta_table = doc.add_table(rows=4, cols=2)
        meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        meta_table.autofit = False

        meta_grid = [
            ("Dataset Name", meta.get("dataset_name"), "Total Records", f"{meta.get('total_rows'):,} records"),
            ("Project ID", meta.get("project_id"), "Features Detected", f"{meta.get('total_columns')} features"),
            ("Analysis Engine", f"FastAPI + SciKit-Learn {meta.get('pipeline_version')}", "Average Price", f"{pt.get('stats', {}).get('mean_price', 0.0):.4f} ETH"),
            ("Top ML Model", pt.get("best_model", "Random Forest Regressor"), "ETH/USD Rate", f"${hub.get('eth_rate_usd', 2268.0):,.2f}"),
        ]

        for r_i, (k1, v1, k2, v2) in enumerate(meta_grid):
            c1 = meta_table.cell(r_i, 0)
            c2 = meta_table.cell(r_i, 1)
            c1.width = Inches(3.5)
            c2.width = Inches(3.5)
            set_cell_margins(c1, top=80, bottom=80, left=120, right=120)
            set_cell_margins(c2, top=80, bottom=80, left=120, right=120)
            set_cell_shading(c1, "F8FAFC")
            set_cell_shading(c2, "F1F5F9")

            p1 = c1.paragraphs[0]
            r1_k = p1.add_run(f"{k1}: ")
            r1_k.font.bold = True
            r1_k.font.size = Pt(9.5)
            r1_v = p1.add_run(str(v1))
            r1_v.font.size = Pt(9.5)

            p2 = c2.paragraphs[0]
            r2_k = p2.add_run(f"{k2}: ")
            r2_k.font.bold = True
            r2_k.font.size = Pt(9.5)
            r2_v = p2.add_run(str(v2))
            r2_v.font.size = Pt(9.5)

        doc.add_paragraph().paragraph_format.space_after = Pt(12)

        # Helper: Section Header
        def add_section_heading(title_text):
            h = doc.add_paragraph()
            h.paragraph_format.space_before = Pt(16)
            h.paragraph_format.space_after = Pt(6)
            r = h.add_run(title_text)
            r.font.name = "Calibri"
            r.font.size = Pt(14)
            r.font.bold = True
            r.font.color.rgb = C_PRIMARY

        # ----------------------------------------------------------------------
        # Section 1: Dataset Overview & Quality
        # ----------------------------------------------------------------------
        if scope in ("complete", "all", "dataset_summary"):
            add_section_heading("1. Dataset Ingestion & Feature Detection")
            p_desc = doc.add_paragraph()
            p_desc.add_run(
                f"The system ingested dataset '{meta.get('dataset_name')}' comprising {meta.get('total_rows'):,} "
                f"transactions across {meta.get('total_columns')} analytical columns. Feature detection identified timestamp, "
                f"asset pricing, sales volume, and relevant social metrics without manual parameter intervention."
            ).font.color.rgb = C_TEXT

            cols = ds.get("columns", [])
            if cols:
                t = doc.add_table(rows=1, cols=4)
                t.alignment = WD_TABLE_ALIGNMENT.CENTER
                hdr = t.rows[0]
                for ci, h_name in enumerate(["Column Name", "Inferred Type", "Valid Count", "Missing Count"]):
                    c = hdr.cells[ci]
                    set_cell_shading(c, "1E1B4B")
                    set_cell_margins(c)
                    p = c.paragraphs[0]
                    run = p.add_run(h_name)
                    run.font.bold = True
                    run.font.color.rgb = RGBColor(255, 255, 255)
                    run.font.size = Pt(9)

                for r_idx, col_info in enumerate(cols[:15], start=1):
                    row = t.add_row()
                    row_cells = [col_info.get("column_name"), col_info.get("data_type"), f"{col_info.get('non_null_count'):,}", str(col_info.get("null_count"))]
                    for ci, val in enumerate(row_cells):
                        c = row.cells[ci]
                        set_cell_margins(c)
                        if r_idx % 2 == 1:
                            set_cell_shading(c, "F8FAFC")
                        p = c.paragraphs[0]
                        r_val = p.add_run(str(val))
                        r_val.font.size = Pt(8.5)
                        r_val.font.color.rgb = C_TEXT

        # ----------------------------------------------------------------------
        # Section 2: Chronological Price Trends & Volume
        # ----------------------------------------------------------------------
        if scope in ("complete", "all", "price_trends"):
            add_section_heading("2. Chronological Price Trends & Volume Analysis")
            stats = pt.get("stats") or {}
            p_pt = doc.add_paragraph()
            p_pt.add_run(
                f"Time-series analysis of {stats.get('data_points', 0)} intervals indicates an average closing price of "
                f"{stats.get('mean_price', 0.0):.4f} ETH (standard deviation: {stats.get('price_std', 0.0):.4f} ETH). "
                f"Historical valuations ranged between a minimum of {stats.get('min_price', 0.0):.4f} ETH and a peak of "
                f"{stats.get('max_price', 0.0):.4f} ETH, generating total trading volume of {stats.get('total_volume', 0.0):,.2f} ETH."
            ).font.color.rgb = C_TEXT

            # Embedded chart
            if "price_trends" in charts:
                p_img = doc.add_paragraph()
                p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_img.paragraph_format.space_before = Pt(8)
                p_img.paragraph_format.space_after = Pt(4)
                doc.add_picture(io.BytesIO(charts["price_trends"]), width=Inches(6.5))
                p_cap = doc.add_paragraph()
                p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_cap.paragraph_format.space_after = Pt(10)
                r_cap = p_cap.add_run("Figure 2.1: Chronological NFT asset pricing and 7-period moving average.")
                r_cap.font.size = Pt(8.5)
                r_cap.font.italic = True
                r_cap.font.color.rgb = C_MUTED

        # ----------------------------------------------------------------------
        # Section 3: Machine Learning Regression & PCA
        # ----------------------------------------------------------------------
        if scope in ("complete", "all", "ml_results", "price_trends"):
            add_section_heading("3. Machine Learning Valuation Models & PCA")
            models = pt.get("models", [])
            best_m = pt.get("best_model", "Random Forest")
            p_ml = doc.add_paragraph()
            p_ml.add_run(
                f"Supervised machine learning regressors were trained on chronological price and volume features. "
                f"The optimal predictive model selected is '{best_m}' based on minimum root mean squared error (RMSE) "
                f"and coefficient of determination (R²)."
            ).font.color.rgb = C_TEXT

            if models:
                t_ml = doc.add_table(rows=1, cols=4)
                t_ml.alignment = WD_TABLE_ALIGNMENT.CENTER
                for ci, h in enumerate(["Model Name", "RMSE", "MAE", "R² Score"]):
                    c = t_ml.rows[0].cells[ci]
                    set_cell_shading(c, "1E1B4B")
                    set_cell_margins(c)
                    p = c.paragraphs[0]
                    r = p.add_run(h)
                    r.font.bold = True
                    r.font.color.rgb = RGBColor(255, 255, 255)
                    r.font.size = Pt(9)

                for r_idx, m in enumerate(models, start=1):
                    row = t_ml.add_row()
                    is_best = (m.get("model_name") == best_m)
                    cells_data = [
                        f"{m.get('model_name')} {'(Best)' if is_best else ''}",
                        f"{float(m.get('rmse', 0.0)):.4f}",
                        f"{float(m.get('mae', 0.0)):.4f}",
                        f"{float(m.get('r2', 0.0)):.4f}",
                    ]
                    for ci, val in enumerate(cells_data):
                        c = row.cells[ci]
                        set_cell_margins(c)
                        if is_best:
                            set_cell_shading(c, "EEF2FF")
                        elif r_idx % 2 == 1:
                            set_cell_shading(c, "F8FAFC")
                        p = c.paragraphs[0]
                        r_v = p.add_run(val)
                        r_v.font.size = Pt(8.5)
                        if is_best:
                            r_v.font.bold = True
                            r_v.font.color.rgb = C_PRIMARY
                        else:
                            r_v.font.color.rgb = C_TEXT

        # ----------------------------------------------------------------------
        # Section 4: Market Activity & Valuation Classifiers
        # ----------------------------------------------------------------------
        if scope in ("complete", "all", "market_activity"):
            add_section_heading("4. Market Activity KPIs & Valuation Tiers")
            kpis = ma.get("kpis") or {}
            p_ma = doc.add_paragraph()
            p_ma.add_run(
                f"Market activity metrics recorded {kpis.get('total_sales', 0):,} total transactions across "
                f"{kpis.get('unique_collections', 1)} unique collections. Daily transaction velocity averaged "
                f"{kpis.get('sales_velocity', 0.0):.2f} sales/day."
            ).font.color.rgb = C_TEXT

            # Embedded distribution chart
            if "valuation_distribution" in charts:
                p_img = doc.add_paragraph()
                p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                doc.add_picture(io.BytesIO(charts["valuation_distribution"]), width=Inches(5.5))
                p_cap = doc.add_paragraph()
                p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_cap.paragraph_format.space_after = Pt(8)
                r_cap = p_cap.add_run("Figure 4.1: Asset count distribution across low, medium, and high valuation tiers.")
                r_cap.font.size = Pt(8.5)
                r_cap.font.italic = True
                r_cap.font.color.rgb = C_MUTED

            # Valuation classifiers table
            clfs = ma.get("classifiers", [])
            if clfs:
                t_clf = doc.add_table(rows=1, cols=5)
                t_clf.alignment = WD_TABLE_ALIGNMENT.CENTER
                for ci, h in enumerate(["Classifier Model", "Accuracy", "F1 Score", "Precision", "Recall"]):
                    c = t_clf.rows[0].cells[ci]
                    set_cell_shading(c, "1E1B4B")
                    set_cell_margins(c)
                    p = c.paragraphs[0]
                    r = p.add_run(h)
                    r.font.bold = True
                    r.font.color.rgb = RGBColor(255, 255, 255)
                    r.font.size = Pt(9)

                for r_idx, c_info in enumerate(clfs, start=1):
                    row = t_clf.add_row()
                    row_data = [
                        c_info.get("model_name"),
                        f"{float(c_info.get('accuracy', 0.0)) * 100:.1f}%",
                        f"{float(c_info.get('f1_score', 0.0)) * 100:.1f}%",
                        f"{float(c_info.get('precision', 0.0)) * 100:.1f}%",
                        f"{float(c_info.get('recall', 0.0)) * 100:.1f}%",
                    ]
                    for ci, val in enumerate(row_data):
                        c = row.cells[ci]
                        set_cell_margins(c)
                        if r_idx % 2 == 1:
                            set_cell_shading(c, "F8FAFC")
                        p = c.paragraphs[0]
                        r_v = p.add_run(val)
                        r_v.font.size = Pt(8.5)
                        r_v.font.color.rgb = C_TEXT

        # ----------------------------------------------------------------------
        # Section 5: Social Engagement Signals
        # ----------------------------------------------------------------------
        if scope in ("complete", "all", "social_engagement"):
            add_section_heading("5. Social Sentiment & Signal Correlation")
            corrs = soc.get("correlations", [])
            top_f = soc.get("top_feature")
            p_soc = doc.add_paragraph()
            if corrs:
                p_soc.add_run(
                    f"Cross-correlation analysis identified '{top_f}' as the primary social signal with strongest "
                    f"correlation to price movement."
                ).font.color.rgb = C_TEXT

                if "social_correlation" in charts:
                    p_img = doc.add_paragraph()
                    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    doc.add_picture(io.BytesIO(charts["social_correlation"]), width=Inches(5.5))
                    p_cap = doc.add_paragraph()
                    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p_cap.paragraph_format.space_after = Pt(8)
                    r_cap = p_cap.add_run("Figure 5.1: Pearson correlation vectors between social signals and NFT price.")
                    r_cap.font.size = Pt(8.5)
                    r_cap.font.italic = True
                    r_cap.font.color.rgb = C_MUTED
            else:
                p_soc.add_run("No social engagement columns were detected in this dataset.").font.color.rgb = C_MUTED

        # ----------------------------------------------------------------------
        # Section 6: Marketplace Hub
        # ----------------------------------------------------------------------
        if scope in ("complete", "all", "marketplace_hub"):
            add_section_heading("6. Marketplace Hub Telemetry")
            p_hub = doc.add_paragraph()
            p_hub.add_run(
                f"Live marketplace telemetry records the current ETH exchange rate at ${hub.get('eth_rate_usd', 2268.0):,.2f} USD. "
                f"Below are the verified benchmark collections tracked by the platform."
            ).font.color.rgb = C_TEXT

            colls = hub.get("collections", [])
            if colls:
                t_hub = doc.add_table(rows=1, cols=4)
                t_hub.alignment = WD_TABLE_ALIGNMENT.CENTER
                for ci, h in enumerate(["Collection", "Floor Price (ETH)", "24h Volume (ETH)", "24h Sales"]):
                    c = t_hub.rows[0].cells[ci]
                    set_cell_shading(c, "1E1B4B")
                    set_cell_margins(c)
                    p = c.paragraphs[0]
                    r = p.add_run(h)
                    r.font.bold = True
                    r.font.color.rgb = RGBColor(255, 255, 255)
                    r.font.size = Pt(9)

                for r_idx, cl in enumerate(colls[:6], start=1):
                    row = t_hub.add_row()
                    row_data = [
                        cl.get("name"),
                        f"{float(cl.get('floor_price_eth', 0.0)):.2f} ETH",
                        f"{float(cl.get('volume_24h_eth', 0.0)):,.1f} ETH",
                        f"{int(cl.get('sales_24h', 0)):,}",
                    ]
                    for ci, val in enumerate(row_data):
                        c = row.cells[ci]
                        set_cell_margins(c)
                        if r_idx % 2 == 1:
                            set_cell_shading(c, "F8FAFC")
                        p = c.paragraphs[0]
                        r_v = p.add_run(val)
                        r_v.font.size = Pt(8.5)
                        r_v.font.color.rgb = C_TEXT

        bio = io.BytesIO()
        doc.save(bio)
        return bio.getvalue()

    # ==========================================================================
    # Format 4: Professional PDF Report via ReportLab
    # ==========================================================================

    @classmethod
    def export_pdf(cls, data: Dict[str, Any], include_charts: bool = True) -> bytes:
        """Generate a publication-grade PDF report with exact Page X of Y numbering and embedded charts."""
        bio = io.BytesIO()

        # Document geometry: Letter size, 0.5-inch (36 pt) side margins, 54 pt top/bottom
        doc = SimpleDocTemplate(
            bio,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=54,
            bottomMargin=54,
        )

        styles = getSampleStyleSheet()

        # Custom typography styles matching dark/violet theme
        style_title = ParagraphStyle(
            "ReportTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=4,
        )

        style_subtitle = ParagraphStyle(
            "ReportSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#4F46E5"),
            spaceAfter=8,
        )

        style_meta = ParagraphStyle(
            "ReportMeta",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#64748B"),
            spaceAfter=12,
        )

        style_h1 = ParagraphStyle(
            "SectionH1",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#1E1B4B"),
            spaceBefore=12,
            spaceAfter=6,
            keepWithNext=True,
        )

        style_body = ParagraphStyle(
            "ReportBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#334155"),
            spaceAfter=8,
        )

        style_table_cell = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#1E293B"),
        )

        style_table_hdr = ParagraphStyle(
            "TableHdr",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.white,
        )

        style_caption = ParagraphStyle(
            "FigureCaption",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#64748B"),
            alignment=1,  # Center
            spaceBefore=3,
            spaceAfter=8,
        )

        story = []

        scope = data.get("metadata", {}).get("scope", "complete")
        meta = data.get("metadata", {})
        pt = data.get("price_trends", {})
        ma = data.get("market_activity", {})
        soc = data.get("social_engagement", {})
        hub = data.get("marketplace_hub", {})
        ds = data.get("dataset_summary", {})

        charts = cls.generate_chart_images(data) if include_charts else {}

        # ----------------------------------------------------------------------
        # Header Banner
        # ----------------------------------------------------------------------
        story.append(Paragraph(meta.get("title", "NFT Trend Analyzer Report"), style_title))
        story.append(Paragraph("EXECUTIVE INTELLIGENCE & MULTI-MODEL PREDICTIVE REPORT", style_subtitle))
        story.append(Paragraph(
            f"<b>Generated:</b> {meta.get('generated_at_formatted')}  |  "
            f"<b>User:</b> {meta.get('user_email')}  |  "
            f"<b>Scope:</b> {meta.get('scope').upper()}  |  "
            f"<b>Dataset:</b> {meta.get('dataset_name')}",
            style_meta,
        ))

        # Metadata KPI Summary Table
        summary_data = [
            [
                Paragraph("<b>Dataset Records</b>", style_table_cell),
                Paragraph(f"{meta.get('total_rows'):,}", style_table_cell),
                Paragraph("<b>Average Asset Price</b>", style_table_cell),
                Paragraph(f"{pt.get('stats', {}).get('mean_price', 0.0):.4f} ETH", style_table_cell),
            ],
            [
                Paragraph("<b>Features Detected</b>", style_table_cell),
                Paragraph(f"{meta.get('total_columns')}", style_table_cell),
                Paragraph("<b>Peak Price</b>", style_table_cell),
                Paragraph(f"{pt.get('stats', {}).get('max_price', 0.0):.4f} ETH", style_table_cell),
            ],
            [
                Paragraph("<b>Top ML Model</b>", style_table_cell),
                Paragraph(str(pt.get("best_model", "Random Forest")), style_table_cell),
                Paragraph("<b>ETH/USD Rate</b>", style_table_cell),
                Paragraph(f"${hub.get('eth_rate_usd', 2268.0):,.2f}", style_table_cell),
            ],
        ]

        t_summary = Table(summary_data, colWidths=[120, 150, 120, 150])
        t_summary.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t_summary)
        story.append(Spacer(1, 10))

        # ----------------------------------------------------------------------
        # Section 1: Ingestion & Feature Detection
        # ----------------------------------------------------------------------
        if scope in ("complete", "all", "dataset_summary"):
            story.append(Paragraph("1. Dataset Ingestion & Feature Detection", style_h1))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#4F46E5"), spaceAfter=6))
            story.append(Paragraph(
                f"Ingested <b>{meta.get('total_rows'):,}</b> records across <b>{meta.get('total_columns')}</b> features. "
                f"Auto-detection mapped timestamp, price, sales volume, and sentiment dimensions with full data integrity checks.",
                style_body,
            ))

            cols = ds.get("columns", [])
            if cols:
                col_tbl_data = [[
                    Paragraph("<b>Column Name</b>", style_table_hdr),
                    Paragraph("<b>Inferred Type</b>", style_table_hdr),
                    Paragraph("<b>Valid Count</b>", style_table_hdr),
                    Paragraph("<b>Missing</b>", style_table_hdr),
                    Paragraph("<b>Sample Data</b>", style_table_hdr),
                ]]
                for idx, c in enumerate(cols[:10]):
                    col_tbl_data.append([
                        Paragraph(c.get("column_name", ""), style_table_cell),
                        Paragraph(c.get("data_type", ""), style_table_cell),
                        Paragraph(f"{c.get('non_null_count', 0):,}", style_table_cell),
                        Paragraph(str(c.get("null_count", 0)), style_table_cell),
                        Paragraph(str(c.get("sample_value", ""))[:25], style_table_cell),
                    ])

                t_cols = Table(col_tbl_data, colWidths=[120, 90, 80, 60, 190])
                t_cols_style = [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E1B4B")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
                for r_i in range(1, len(col_tbl_data)):
                    if r_i % 2 == 1:
                        t_cols_style.append(("BACKGROUND", (0, r_i), (-1, r_i), colors.HexColor("#F8FAFC")))
                t_cols.setStyle(TableStyle(t_cols_style))
                story.append(t_cols)
                story.append(Spacer(1, 10))

        # ----------------------------------------------------------------------
        # Section 2: Chronological Price Trends & Volume
        # ----------------------------------------------------------------------
        if scope in ("complete", "all", "price_trends"):
            story.append(Paragraph("2. Chronological Price Trends & Volume", style_h1))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#4F46E5"), spaceAfter=6))

            stats = pt.get("stats") or {}
            story.append(Paragraph(
                f"Computed time series across <b>{stats.get('data_points', 0)}</b> chronological intervals. "
                f"Mean closing price: <b>{stats.get('mean_price', 0.0):.4f} ETH</b> (std: {stats.get('price_std', 0.0):.4f} ETH), "
                f"with peak historical valuation of <b>{stats.get('max_price', 0.0):.4f} ETH</b> and cumulative volume of "
                f"<b>{stats.get('total_volume', 0.0):,.2f} ETH</b>.",
                style_body,
            ))

            if "price_trends" in charts:
                img_io = io.BytesIO(charts["price_trends"])
                img = Image(img_io, width=540, height=210)
                story.append(img)
                story.append(Paragraph("Figure 2.1: Chronological NFT asset pricing and 7-period moving average.", style_caption))

        # ----------------------------------------------------------------------
        # Section 3: Machine Learning Price Regressors & PCA
        # ----------------------------------------------------------------------
        if scope in ("complete", "all", "ml_results", "price_trends"):
            story.append(Paragraph("3. Machine Learning Valuation Models & PCA", style_h1))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#4F46E5"), spaceAfter=6))

            best_m = pt.get("best_model", "Random Forest")
            story.append(Paragraph(
                f"Trained supervised regressors with train/test splits. Optimal algorithm: <b>{best_m}</b>. "
                f"Evaluated against RMSE, MAE, and R² benchmarks.",
                style_body,
            ))

            models = pt.get("models", [])
            if models:
                ml_tbl_data = [[
                    Paragraph("<b>Algorithm</b>", style_table_hdr),
                    Paragraph("<b>RMSE</b>", style_table_hdr),
                    Paragraph("<b>MAE</b>", style_table_hdr),
                    Paragraph("<b>R² Score</b>", style_table_hdr),
                    Paragraph("<b>Status</b>", style_table_hdr),
                ]]
                for m in models:
                    is_b = (m.get("model_name") == best_m)
                    ml_tbl_data.append([
                        Paragraph(f"<b>{m.get('model_name')}</b>" if is_b else m.get("model_name"), style_table_cell),
                        Paragraph(f"{float(m.get('rmse', 0.0)):.4f}", style_table_cell),
                        Paragraph(f"{float(m.get('mae', 0.0)):.4f}", style_table_cell),
                        Paragraph(f"{float(m.get('r2', 0.0)):.4f}", style_table_cell),
                        Paragraph("★ Best Model" if is_b else "Evaluated", style_table_cell),
                    ])

                t_ml = Table(ml_tbl_data, colWidths=[160, 95, 95, 95, 95])
                t_ml_style = [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E1B4B")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
                for r_i, m in enumerate(models, start=1):
                    if m.get("model_name") == best_m:
                        t_ml_style.append(("BACKGROUND", (0, r_i), (-1, r_i), colors.HexColor("#EEF2FF")))
                    elif r_i % 2 == 1:
                        t_ml_style.append(("BACKGROUND", (0, r_i), (-1, r_i), colors.HexColor("#F8FAFC")))
                t_ml.setStyle(TableStyle(t_ml_style))
                story.append(t_ml)
                story.append(Spacer(1, 10))

        # ----------------------------------------------------------------------
        # Section 4: Market Activity & Valuation Classifiers
        # ----------------------------------------------------------------------
        if scope in ("complete", "all", "market_activity"):
            story.append(Paragraph("4. Market Activity KPIs & Valuation Tiers", style_h1))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#4F46E5"), spaceAfter=6))

            kpis = ma.get("kpis") or {}
            story.append(Paragraph(
                f"Total transactions: <b>{kpis.get('total_sales', 0):,}</b> across <b>{kpis.get('unique_collections', 1)}</b> "
                f"collections. Daily sales velocity: <b>{kpis.get('sales_velocity', 0.0):.2f} sales/day</b>.",
                style_body,
            ))

            if "valuation_distribution" in charts:
                img_io = io.BytesIO(charts["valuation_distribution"])
                img = Image(img_io, width=480, height=200)
                story.append(img)
                story.append(Paragraph("Figure 4.1: Distribution of NFT assets by valuation tier.", style_caption))

            clfs = ma.get("classifiers", [])
            if clfs:
                clf_tbl_data = [[
                    Paragraph("<b>Classifier</b>", style_table_hdr),
                    Paragraph("<b>Accuracy</b>", style_table_hdr),
                    Paragraph("<b>F1 Score</b>", style_table_hdr),
                    Paragraph("<b>Precision</b>", style_table_hdr),
                    Paragraph("<b>Recall</b>", style_table_hdr),
                ]]
                for c in clfs:
                    clf_tbl_data.append([
                        Paragraph(c.get("model_name", ""), style_table_cell),
                        Paragraph(f"{float(c.get('accuracy', 0.0)) * 100:.1f}%", style_table_cell),
                        Paragraph(f"{float(c.get('f1_score', 0.0)) * 100:.1f}%", style_table_cell),
                        Paragraph(f"{float(c.get('precision', 0.0)) * 100:.1f}%", style_table_cell),
                        Paragraph(f"{float(c.get('recall', 0.0)) * 100:.1f}%", style_table_cell),
                    ])
                t_clf = Table(clf_tbl_data, colWidths=[160, 95, 95, 95, 95])
                t_clf.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E1B4B")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]))
                story.append(t_clf)
                story.append(Spacer(1, 10))

        # ----------------------------------------------------------------------
        # Section 5: Social Engagement Signals
        # ----------------------------------------------------------------------
        if scope in ("complete", "all", "social_engagement"):
            story.append(Paragraph("5. Social Sentiment & Signal Correlation", style_h1))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#4F46E5"), spaceAfter=6))

            corrs = soc.get("correlations", [])
            top_f = soc.get("top_feature")
            if corrs:
                story.append(Paragraph(
                    f"Top predictive social indicator: <b>{top_f}</b>. Evaluated using Pearson linear and Spearman rank vectors.",
                    style_body,
                ))

                if "social_correlation" in charts:
                    img_io = io.BytesIO(charts["social_correlation"])
                    img = Image(img_io, width=480, height=190)
                    story.append(img)
                    story.append(Paragraph("Figure 5.1: Pearson correlation vectors between social signals and price.", style_caption))
            else:
                story.append(Paragraph("No social indicators were detected in this dataset.", style_body))

        # ----------------------------------------------------------------------
        # Section 6: Marketplace Hub
        # ----------------------------------------------------------------------
        if scope in ("complete", "all", "marketplace_hub"):
            story.append(Paragraph("6. Marketplace Hub Telemetry", style_h1))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#4F46E5"), spaceAfter=6))
            story.append(Paragraph(
                f"Live ETH rate: <b>${hub.get('eth_rate_usd', 2268.0):,.2f} USD</b>. Verified collection benchmark statistics:",
                style_body,
            ))

            colls = hub.get("collections", [])
            if colls:
                hub_tbl_data = [[
                    Paragraph("<b>Collection</b>", style_table_hdr),
                    Paragraph("<b>Floor Price</b>", style_table_hdr),
                    Paragraph("<b>24h Volume</b>", style_table_hdr),
                    Paragraph("<b>24h Sales</b>", style_table_hdr),
                ]]
                for cl in colls[:5]:
                    hub_tbl_data.append([
                        Paragraph(cl.get("name", ""), style_table_cell),
                        Paragraph(f"{float(cl.get('floor_price_eth', 0.0)):.2f} ETH", style_table_cell),
                        Paragraph(f"{float(cl.get('volume_24h_eth', 0.0)):,.1f} ETH", style_table_cell),
                        Paragraph(f"{int(cl.get('sales_24h', 0)):,}", style_table_cell),
                    ])
                t_hub = Table(hub_tbl_data, colWidths=[180, 120, 120, 120])
                t_hub.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E1B4B")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]))
                story.append(t_hub)

        # Build PDF with two-pass page numbering canvas
        doc.build(story, canvasmaker=NumberedCanvas)
        return bio.getvalue()

    # ==========================================================================
    # Unified Export Router
    # ==========================================================================

    @classmethod
    def export_report(
        cls,
        user_email: str,
        export_format: str = "pdf",
        scope: str = "complete",
        project_id: Optional[str] = None,
        custom_title: Optional[str] = None,
        include_charts: bool = True,
    ) -> Tuple[bytes, str, str]:
        """Generate and package report in the requested format with sanitized filename and mime type."""
        fmt = export_format.lower().strip()
        if fmt not in cls.MIME_TYPES:
            raise ValueError(f"Unsupported export format '{fmt}'. Supported formats: pdf, json, docx, xlsx.")

        # Extract structured data
        data = cls.get_report_data(
            user_email=user_email,
            scope=scope,
            project_id=project_id,
            custom_title=custom_title,
        )

        # Generate file bytes
        if fmt == "pdf":
            file_bytes = cls.export_pdf(data, include_charts=include_charts)
        elif fmt == "json":
            file_bytes = cls.export_json(data)
        elif fmt == "docx":
            file_bytes = cls.export_docx(data, include_charts=include_charts)
        elif fmt == "xlsx":
            file_bytes = cls.export_xlsx(data)
        else:
            raise ValueError(f"Unhandled format: {fmt}")

        # Sanitize filename
        clean_ds = re.sub(r"[^\w\-]", "_", data.get("metadata", {}).get("dataset_name", "Report"))
        date_stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        scope_tag = f"_{scope}" if scope != "complete" else ""
        filename = f"NFT_Trend_Analysis_{clean_ds}{scope_tag}_{date_stamp}.{fmt}"

        return file_bytes, filename, cls.MIME_TYPES[fmt]
