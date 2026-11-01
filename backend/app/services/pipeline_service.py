"""Central dataset analysis pipeline and session orchestration service.

Executes a complete 9-step automated analysis pipeline upon dataset ingestion:
1. File validation and type parsing (CSV, Excel, JSON, Parquet)
2. Data cleaning, normalization, and deduplication
3. Analytical feature detection (date, price, volume, collection, social signals)
4. Module 1: Chronological price trends & multi-model ML regression with 60-component PCA
5. Module 2: Market activity KPIs, collection distributions, and 3-tier valuation classifiers
6. Module 3: Social sentiment correlation vectors (if social signals present)
7. Module 4: Live marketplace API intelligence synchronization
8. Workspace snapshot persistence (Supabase PostgreSQL / Storage with user isolation)
9. Active dataset session synchronization across all dashboard sections
"""

from __future__ import annotations

import datetime
import io
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from app.core.data_loader import (
    load_uploaded_dataset,
    validate_and_diagnose_dataset,
)
from app.core.nft_analysis import (
    clean_dataframe,
    discover_social_columns,
    infer_column,
    parse_dates,
    parse_numeric,
)
from app.services.analysis_service import AnalysisService
from app.services.marketplace_service import MarketplaceService
from app.services.ml_service import MLService
from app.services.storage_service import StorageService

logger = logging.getLogger("nft_trend_analyzer.pipeline")

# Per-user active analysis session cache: user_email -> session data
_USER_ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}


class PipelineService:

    @classmethod
    def get_active_session(cls, user_email: str) -> Dict[str, Any]:
        """Retrieve active dataset and analytical bundle for user, restoring from persistent storage if needed."""
        clean_email = user_email.strip().lower()

        # 1. In-memory cached active session
        if clean_email in _USER_ACTIVE_SESSIONS and _USER_ACTIVE_SESSIONS[clean_email].get("dataframe") is not None:
            session = _USER_ACTIVE_SESSIONS[clean_email]
            if not session["dataframe"].empty:
                return session

        # 2. Restore most recent saved project from persistent storage
        projects = StorageService.list_projects(clean_email)
        if projects:
            latest_project = projects[0]
            project_id = str(latest_project.get("id"))
            df, msg = StorageService.load_project_dataframe(project_id, clean_email)
            if df is not None and not df.empty:
                summary = latest_project.get("summary_json") or {}
                if isinstance(summary, str):
                    try:
                        summary = json.loads(summary)
                    except Exception:
                        summary = {}

                # If project was saved with complete bundle, restore directly
                if "module_statuses" in summary and "price_trends" in summary:
                    session_data = {
                        "project_id": project_id,
                        "dataset_name": latest_project.get("dataset_name", "Saved Dataset"),
                        "dataframe": df,
                        "bundle": summary,
                        "updated_at": latest_project.get("updated_at", datetime.datetime.now(datetime.timezone.utc).isoformat()),
                    }
                    _USER_ACTIVE_SESSIONS[clean_email] = session_data
                    return session_data

                # Recompute analytical bundle for legacy saved project
                bundle = cls._orchestrate_analysis_bundle(df, latest_project.get("dataset_name", "Saved Dataset"))
                session_data = {
                    "project_id": project_id,
                    "dataset_name": latest_project.get("dataset_name", "Saved Dataset"),
                    "dataframe": df,
                    "bundle": bundle,
                    "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }
                _USER_ACTIVE_SESSIONS[clean_email] = session_data
                return session_data

        # 3. Default fallback: synthesize demo dataset and run complete pipeline once
        demo_df = AnalysisService.get_demo_dataset(n_rows=160)
        demo_bundle = cls._orchestrate_analysis_bundle(demo_df, "Educational NFT Benchmark Dataset (Demo)")
        session_data = {
            "project_id": "demo-active-session",
            "dataset_name": "Educational NFT Benchmark Dataset (Demo)",
            "dataframe": demo_df,
            "bundle": demo_bundle,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        _USER_ACTIVE_SESSIONS[clean_email] = session_data
        return session_data

    @classmethod
    def get_active_dataframe(cls, user_email: str) -> pd.DataFrame:
        """Helper returning the active DataFrame for the given user."""
        session = cls.get_active_session(user_email)
        return session.get("dataframe") or AnalysisService.get_demo_dataset(120)

    @classmethod
    def set_active_project(cls, project_id: str, user_email: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Activate a previously saved project from user workspace across all four dashboard modules."""
        clean_email = user_email.strip().lower()
        project = StorageService.get_project(project_id, clean_email)
        if not project:
            return False, "Project not found or access denied.", None

        df, msg = StorageService.load_project_dataframe(project_id, clean_email)
        if df is None or df.empty:
            return False, f"Could not restore dataset: {msg}", None

        summary = project.get("summary_json") or {}
        if isinstance(summary, str):
            try:
                summary = json.loads(summary)
            except Exception:
                summary = {}

        if "module_statuses" in summary and "price_trends" in summary:
            bundle = summary
        else:
            bundle = cls._orchestrate_analysis_bundle(df, project.get("dataset_name", "Saved Dataset"))

        session_data = {
            "project_id": project_id,
            "dataset_name": project.get("dataset_name", "Saved Dataset"),
            "dataframe": df,
            "bundle": bundle,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        _USER_ACTIVE_SESSIONS[clean_email] = session_data

        # Synchronize backward-compatible session cache in routes_analysis
        from app.api.routes_analysis import _USER_ACTIVE_DF
        _USER_ACTIVE_DF[clean_email] = df

        return True, f"Project '{project.get('project_name')}' activated successfully.", bundle

    @classmethod
    def process_and_analyze_dataset(
        cls,
        file_bytes: bytes,
        filename: str,
        user_email: str,
        project_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute full automated pipeline on uploaded dataset bytes with automatic persistence and section sync."""
        clean_email = user_email.strip().lower()

        # Step 1: Validation
        if not file_bytes:
            raise ValueError("Uploaded file is empty.")
        if len(file_bytes) > 200 * 1024 * 1024:
            raise ValueError("File exceeds maximum allowable size (200MB).")

        # Step 2: Tabular Deserialization & Preprocessing
        try:
            raw_df, meta = load_uploaded_dataset(file_bytes, filename)
        except Exception as exc:
            raise ValueError(f"Failed to parse dataset file: {exc}")

        if raw_df.empty:
            raise ValueError("Parsed dataset contains 0 records.")

        cleaned_df, cleaning_meta = clean_dataframe(raw_df)
        if cleaned_df.empty:
            raise ValueError("Dataset has no valid records after cleaning and validation.")

        # Step 3: Run Central Analysis Orchestration
        bundle = cls._orchestrate_analysis_bundle(cleaned_df, filename)

        # Step 4: Persist dataset and analysis snapshot into user's persistent workspace
        proj_name = project_name.strip() if project_name and project_name.strip() else f"Research - {filename}"
        save_ok, save_res = StorageService.save_project(
            user_email=clean_email,
            project_name=proj_name,
            dataset_name=filename,
            analysis_type="Automatic 4-Section Pipeline",
            summary_json=bundle,
            dataframe=cleaned_df,
        )

        project_id = save_res if save_ok else "session-only"
        bundle["project_id"] = project_id
        bundle["storage_status"] = "persisted" if save_ok else f"local_session_only: {save_res}"

        # Step 5: Update active session state for this user
        session_data = {
            "project_id": project_id,
            "dataset_name": filename,
            "dataframe": cleaned_df,
            "bundle": bundle,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        _USER_ACTIVE_SESSIONS[clean_email] = session_data

        # Synchronize backward-compatible session cache in routes_analysis
        from app.api.routes_analysis import _USER_ACTIVE_DF
        _USER_ACTIVE_DF[clean_email] = cleaned_df

        # Build concise modules summary
        price_trends_mod = bundle.get("price_trends", {})
        market_activity_mod = bundle.get("market_activity", {})
        social_mod = bundle.get("social_engagement", {})
        marketplace_mod = bundle.get("marketplace_hub", {})

        modules_summary = {
            "price_trends": {
                "available": price_trends_mod.get("available", False),
                "time_series_count": len(price_trends_mod.get("data", [])),
                "best_model": price_trends_mod.get("best_model", "Random Forest"),
            },
            "market_activity": {
                "available": market_activity_mod.get("available", False),
                "total_sales": (market_activity_mod.get("kpis") or {}).get("total_sales", len(cleaned_df)),
                "unique_collections": (market_activity_mod.get("kpis") or {}).get("unique_collections", 1),
            },
            "social_engagement": {
                "available": social_mod.get("available", False),
                "tracked_signals_count": len(social_mod.get("social_columns", [])),
                "correlations": social_mod.get("correlations", []),
                "top_feature": social_mod.get("top_feature"),
            },
            "marketplace_hub": {
                "available": marketplace_mod.get("available", True),
                "live_sync": marketplace_mod.get("is_live", True),
                "eth_rate_usd": marketplace_mod.get("eth_rate_usd", 2268.0),
            },
        }

        return {
            "success": True,
            "status": "success",
            "message": "Dataset successfully analyzed. Your dashboard sections have been updated.",
            "project_id": project_id,
            "dataset_name": filename,
            "valid_records": len(cleaned_df),
            "total_records": len(cleaned_df),
            "total_columns": len(cleaned_df.columns),
            "features_detected": bundle["features_detected"],
            "module_statuses": bundle["module_statuses"],
            "modules_summary": modules_summary,
            "summary": bundle,
        }

    @classmethod
    def _orchestrate_analysis_bundle(cls, df: pd.DataFrame, dataset_name: str) -> Dict[str, Any]:
        """Execute all four analytical modules across the provided DataFrame."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Feature Detection
        d_col = infer_column(df, "date")
        p_col = infer_column(df, "price")
        s_col = infer_column(df, "sales")
        c_col = None
        for cand in df.columns:
            low = str(cand).lower().replace(" ", "_").replace("-", "_")
            if any(term in low for term in ("collection", "slug", "project", "contract", "asset_contract")):
                c_col = str(cand)
                break
        social_cols = discover_social_columns(df)

        features_detected = {
            "date_column": d_col,
            "price_column": p_col,
            "sales_column": s_col,
            "collection_column": c_col,
            "social_columns": social_cols,
            "numeric_columns": [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])],
        }

        module_statuses: Dict[str, str] = {}
        warnings: List[str] = []

        # ----------------------------------------------------------------------
        # MODULE 1: Price Trends & ML Prediction (Time-Series, ML Models, PCA)
        # ----------------------------------------------------------------------
        price_trends_result: Dict[str, Any] = {
            "available": False,
            "data": [],
            "stats": None,
            "models": [],
            "best_model": "N/A",
            "test_predictions": [],
            "evaluation_metrics": {},
            "pca_diagnostics": {
                "enabled": False,
                "cumulative_variance_ratio": [],
                "explained_variance_ratio": [],
                "status_message": "PCA requires numeric price and feature columns.",
            },
        }

        if d_col and p_col:
            try:
                # 1. Time-series aggregation
                ts_series = AnalysisService.get_time_series_data(df, date_col=d_col, price_col=p_col, sales_col=s_col)

                # Compute summary stats
                parsed_prices = parse_numeric(df[p_col]).dropna()
                mean_p = float(parsed_prices.mean()) if not parsed_prices.empty else 0.0
                max_p = float(parsed_prices.max()) if not parsed_prices.empty else 0.0
                min_p = float(parsed_prices.min()) if not parsed_prices.empty else 0.0
                std_p = float(parsed_prices.std()) if len(parsed_prices) > 1 else 0.0

                ts_stats = {
                    "mean_price": mean_p,
                    "max_price": max_p,
                    "min_price": min_p,
                    "price_std": std_p,
                    "data_points": len(ts_series),
                    "total_volume": float(parsed_prices.sum()),
                }

                price_trends_result["available"] = True
                price_trends_result["data"] = ts_series
                price_trends_result["series"] = ts_series
                price_trends_result["stats"] = ts_stats

                # 2. ML Price Prediction Models & PCA (min 10 rows for meaningful train/test split)
                if len(df) >= 10:
                    try:
                        ml_res = MLService.train_price_models(
                            df, date_col=d_col, target_col=p_col, use_pca=True, target_pca_components=60
                        )
                        models_list = ml_res.get("models", [])
                        eval_metrics = {
                            m["model_name"]: {
                                "rmse": m["rmse"],
                                "mae": m["mae"],
                                "r2": m["r2"],
                            }
                            for m in models_list
                        }
                        price_trends_result["models"] = models_list
                        price_trends_result["best_model"] = ml_res.get("best_model", "Random Forest")
                        price_trends_result["test_predictions"] = ml_res.get("actual_vs_predicted_sample", [])
                        price_trends_result["evaluation_metrics"] = eval_metrics
                        if ml_res.get("pca_diagnostics"):
                            price_trends_result["pca_diagnostics"] = ml_res["pca_diagnostics"]
                        module_statuses["price_trends"] = "completed"
                    except Exception as ml_err:
                        logger.warning(f"ML regression training note: {ml_err}")
                        price_trends_result["ml_note"] = str(ml_err)
                        module_statuses["price_trends"] = "time_series_only"
                else:
                    module_statuses["price_trends"] = "time_series_only"
                    price_trends_result["ml_note"] = "Dataset contains fewer than 10 records for ML regression."
            except Exception as ts_err:
                logger.error(f"Time-series computation error: {ts_err}")
                price_trends_result["error"] = str(ts_err)
                module_statuses["price_trends"] = "error"
                warnings.append(f"Price trends: {ts_err}")
        else:
            module_statuses["price_trends"] = "not_available"
            price_trends_result["message"] = (
                f"Missing required fields for chronological price modeling. "
                f"Detected date column: {d_col or 'None'}, price column: {p_col or 'None'}."
            )
            warnings.append("Price trends: requires both a timestamp and numeric price column.")

        # ----------------------------------------------------------------------
        # MODULE 2: Market Activity & Valuation Tiers
        # ----------------------------------------------------------------------
        market_activity_result: Dict[str, Any] = {
            "available": False,
            "kpis": None,
            "distribution": [],
            "classifiers": [],
        }

        try:
            # 1. Market KPIs
            kpis = AnalysisService.get_market_kpis(
                df, date_col=d_col, price_col=p_col, sales_col=s_col, collection_col=c_col
            )
            market_activity_result["kpis"] = kpis
            market_activity_result["available"] = True

            # 2. Valuation Tiers & Classification (Random Forest, Logistic Regression, SVM)
            if p_col and p_col in df.columns:
                try:
                    val_res = MLService.evaluate_valuation_tiers(df, target_col=p_col)
                    market_activity_result["distribution"] = val_res.get("distribution", [])
                    market_activity_result["classifiers"] = val_res.get("classifiers", [])
                    module_statuses["market_activity"] = "completed"
                except Exception as val_err:
                    logger.warning(f"Valuation tier classification note: {val_err}")
                    market_activity_result["classification_note"] = str(val_err)
                    module_statuses["market_activity"] = "kpis_only"
            else:
                module_statuses["market_activity"] = "kpis_only"
        except Exception as ma_err:
            logger.error(f"Market activity computation error: {ma_err}")
            market_activity_result["error"] = str(ma_err)
            module_statuses["market_activity"] = "error"
            warnings.append(f"Market activity: {ma_err}")

        # ----------------------------------------------------------------------
        # MODULE 3: Social Engagement & Sentiment Vectors
        # ----------------------------------------------------------------------
        social_engagement_result: Dict[str, Any] = {
            "available": False,
            "price_column": p_col,
            "social_columns": social_cols,
            "correlations": [],
            "top_feature": None,
            "scatter_samples": [],
            "message": "",
        }

        if social_cols and p_col:
            try:
                soc_data = AnalysisService.get_social_engagement_data(df, price_col=p_col, social_cols=social_cols)
                social_engagement_result["available"] = True
                social_engagement_result["correlations"] = soc_data.get("correlations", [])
                social_engagement_result["top_feature"] = soc_data.get("top_feature")
                social_engagement_result["scatter_samples"] = soc_data.get("scatter_samples", [])
                module_statuses["social_engagement"] = "completed"
            except Exception as soc_err:
                logger.warning(f"Social correlation computation error: {soc_err}")
                social_engagement_result["error"] = str(soc_err)
                module_statuses["social_engagement"] = "error"
        else:
            module_statuses["social_engagement"] = "not_available"
            social_engagement_result["message"] = (
                f"No social engagement columns detected in dataset '{dataset_name}'. "
                "To explore social sentiment correlations, upload a dataset with indicators such as "
                "twitter_sentiment, discord_messages, likes, or comments (or use the Dual Join workflow)."
            )

        # ----------------------------------------------------------------------
        # MODULE 4: Marketplace Hub (Live Telemetry Synchronization)
        # ----------------------------------------------------------------------
        marketplace_result: Dict[str, Any] = {
            "available": True,
            "is_live": True,
            "source": "CoinGecko & OpenSea Live APIs",
            "refreshed_at": now_iso,
            "eth_rate_usd": 2268.0,
            "status": "synchronized",
        }
        try:
            eth_data = MarketplaceService.get_eth_price()
            marketplace_result["eth_price"] = eth_data
            marketplace_result["eth_rate_usd"] = eth_data.get("rate_usd", 2268.0)
            marketplace_result["source"] = eth_data.get("source", "Live API Data (CoinGecko)")
            marketplace_result["is_live"] = eth_data.get("is_live", True)
            module_statuses["marketplace_hub"] = "synchronized"
        except Exception as mp_err:
            logger.warning(f"Marketplace telemetry sync note: {mp_err}")
            marketplace_result["eth_price"] = {"rate_usd": 2268.0, "is_live": False, "source": "Cached Fallback"}
            marketplace_result["status"] = "cached"
            marketplace_result["note"] = str(mp_err)
            module_statuses["marketplace_hub"] = "cached_fallback"

        # Final Analytical Bundle Assembly
        return {
            "pipeline_version": "3.0.0",
            "analyzed_at": now_iso,
            "dataset_name": dataset_name,
            "rows_count": len(df),
            "columns_count": len(df.columns),
            "columns": list(df.columns),
            "features_detected": features_detected,
            "module_statuses": module_statuses,
            "warnings": warnings,
            "price_trends": price_trends_result,
            "market_activity": market_activity_result,
            "social_engagement": social_engagement_result,
            "marketplace_hub": marketplace_result,
        }
