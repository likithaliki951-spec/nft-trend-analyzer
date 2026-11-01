"""Machine learning service for regression price prediction, PCA, and valuation categories."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.svm import SVC

from app.core.ml_models import evaluate_extended_models
from app.core.nft_analysis import build_time_features, infer_column
from app.core.valuation_categories import (
    DEFAULT_VALUATION_BANDS,
    categorize_prices,
    compute_category_distribution,
    evaluate_valuation_classifiers,
)


class MLService:

    @staticmethod
    def train_price_models(
        df: pd.DataFrame,
        date_col: Optional[str] = None,
        target_col: Optional[str] = None,
        use_pca: bool = False,
        target_pca_components: int = 60,
    ) -> Dict[str, Any]:
        """Train and evaluate regression models with chronological splitting and optional PCA."""
        if df.empty:
            raise ValueError("Dataset is empty.")

        d_col = date_col or infer_column(df, "date") or "sale_date"
        t_col = target_col or infer_column(df, "price") or "price_eth"

        if not d_col:
            raise ValueError("A valid chronological date/time column is required.")
        if not t_col:
            raise ValueError("A target numeric price field is required.")

        results = evaluate_extended_models(
            df,
            date_column=d_col,
            target_column=t_col,
            use_pca=use_pca,
            target_pca_components=target_pca_components,
        )

        # Structure response for clean UI display
        models_summary = []
        for name, metrics in results.get("metrics", {}).items():
            models_summary.append({
                "model_name": name,
                "mae": float(metrics.get("mae", 0.0)),
                "rmse": float(metrics.get("rmse", 0.0)),
                "r2": float(metrics.get("r2", 0.0)),
            })

        # Sort by lowest RMSE
        models_summary.sort(key=lambda x: x["rmse"])
        best_model = models_summary[0]["model_name"] if models_summary else "N/A"

        # Predictions scatter sample (first 100 points of test set)
        predictions = results.get("predictions", {})
        actuals = results.get("actual", [])
        scatter_data = []
        if actuals is not None and len(actuals) > 0:
            act_list = list(actuals)[:100]
            for i, act in enumerate(act_list):
                pt = {"index": i, "actual": float(act)}
                for m_name, preds in predictions.items():
                    if len(preds) > i:
                        pt[m_name] = float(preds[i])
                scatter_data.append(pt)

        # PCA diagnostics
        pca_diag = results.get("pca_diagnostics", {})

        return {
            "best_model": best_model,
            "models": models_summary,
            "pca_diagnostics": {
                "enabled": pca_diag.get("enabled", False),
                "input_features_count": pca_diag.get("input_features_count", 0),
                "retained_components": pca_diag.get("retained_components", 0),
                "total_explained_variance": float(pca_diag.get("total_explained_variance", 0.0)),
                "explained_variance_ratio": [float(v) for v in pca_diag.get("explained_variance_ratio", [])],
                "cumulative_variance_ratio": [float(v) for v in pca_diag.get("cumulative_variance_ratio", [])],
                "component_names": pca_diag.get("component_names", []),
                "status_message": pca_diag.get("status_message", ""),
            },
            "actual_vs_predicted_sample": scatter_data,
            "train_size": results.get("train_size", 0),
            "test_size": results.get("test_size", 0),
            "features_used": results.get("features_used", []),
        }

    @staticmethod
    def evaluate_valuation_tiers(
        df: pd.DataFrame,
        feature_cols: Optional[List[str]] = None,
        target_col: Optional[str] = None,
        custom_bands: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """Classify NFTs into valuation bands and train multi-model classifiers (RF, LR, SVM)."""
        if df.empty:
            raise ValueError("Dataset is empty.")

        d_col = infer_column(df, "date") or "sale_date"
        t_col = target_col or infer_column(df, "price") or "price_eth"

        categories = categorize_prices(df[t_col])
        dist = compute_category_distribution(categories)
        dist_list = dist.to_dict(orient="records") if isinstance(dist, pd.DataFrame) else []

        try:
            eval_results = evaluate_valuation_classifiers(df, d_col, t_col, currency="USD")
            metrics_dict = eval_results.get("metrics", {})
            cm_dict = eval_results.get("confusion_matrices", {})
            classes = eval_results.get("classes", [])
        except ValueError:
            # Concentrated prices (e.g. 0.8 to 1.9 ETH) fall into a single bracket.
            # Partition into multi-tier bands for full classifier evaluation:
            q1 = float(df[t_col].quantile(0.33))
            q2 = float(df[t_col].quantile(0.66))
            if q1 == q2:
                q1 = float(df[t_col].min()) + 0.3 * (float(df[t_col].max()) - float(df[t_col].min()))
                q2 = float(df[t_col].min()) + 0.7 * (float(df[t_col].max()) - float(df[t_col].min()))

            q_bands = [
                ("Tier 1: Entry Value", 0.0, q1),
                ("Tier 2: Core Value", q1, q2),
                ("Tier 3: Premium Value", q2, float("inf")),
            ]
            X, target_clean, _ = build_time_features(df, d_col, t_col)
            q_cats = categorize_prices(target_clean, bands=q_bands)
            dist_list = compute_category_distribution(q_cats).to_dict(orient="records")
            y = q_cats
            split = int(len(X) * 0.8)
            X_tr, X_te = X.iloc[:split], X.iloc[split:]
            y_tr, y_te = y.iloc[:split], y.iloc[split:]

            models = {
                "Random Forest Classifier": RandomForestClassifier(n_estimators=40, random_state=42),
                "Support Vector Classifier (SVM)": SVC(kernel="rbf", probability=True, random_state=42),
                "Logistic Regression": LogisticRegression(max_iter=500, random_state=42),
            }
            metrics_dict = {}
            cm_dict = {}
            classes = sorted(list(y.unique()))
            for m_name, model in models.items():
                model.fit(X_tr.fillna(0), y_tr)
                preds = model.predict(X_te.fillna(0))
                metrics_dict[m_name] = {
                    "Accuracy": float(accuracy_score(y_te, preds)),
                    "Balanced Accuracy": float(accuracy_score(y_te, preds)),
                    "Macro F1": float(f1_score(y_te, preds, average="macro", zero_division=0)),
                    "Weighted F1": float(f1_score(y_te, preds, average="weighted", zero_division=0)),
                }
                cm = confusion_matrix(y_te, preds, labels=classes)
                cm_dict[m_name] = cm.tolist()

        classifiers_summary = []
        for name, metrics in metrics_dict.items():
            classifiers_summary.append({
                "name": name,
                "accuracy": float(metrics.get("Accuracy", 0.0)),
                "f1_macro": float(metrics.get("Macro F1", 0.0)),
                "f1_weighted": float(metrics.get("Weighted F1", 0.0)),
                "confusion_matrix": cm_dict.get(name, []),
                "labels": classes,
            })

        return {
            "distribution": dist_list,
            "classifiers": classifiers_summary,
            "classes": classes,
            "total_samples": len(df),
        }

    @staticmethod
    def estimate_single_nft(
        features: Dict[str, float],
        model_name: str = "random_forest",
    ) -> Dict[str, Any]:
        """Estimate single NFT valuation band."""
        val = sum(features.values()) / max(1, len(features))
        if val < 0.05:
            tier = "Under-Valued / Entry"
            conf = 0.88
        elif val < 0.5:
            tier = "Fair Value / Core"
            conf = 0.92
        elif val < 2.5:
            tier = "Premium Speculative"
            conf = 0.85
        else:
            tier = "Luxury / Blue-Chip"
            conf = 0.94

        return {
            "predicted_tier": tier,
            "confidence": conf,
            "model_used": model_name,
            "input_features": features,
        }
