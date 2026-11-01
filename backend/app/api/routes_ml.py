"""Machine learning endpoints for regression models, PCA reduction, and valuation classification."""

from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.routes_analysis import get_user_dataframe
from app.auth import get_current_user
from app.schemas import MLTrainRequest, SingleValuationRequest, ValuationClassifiersRequest
from app.services.ml_service import MLService

router = APIRouter(prefix="/ml", tags=["Machine Learning"])


@router.post("/predict-train")
async def train_predictive_models(
    req: MLTrainRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Section 1: Train Linear Regression, Ridge, Random Forest, Gradient Boosting; evaluate metrics and PCA."""
    df = get_user_dataframe(user["email"])
    try:
        results = MLService.train_price_models(
            df,
            date_col=req.date_column,
            target_col=req.target_column,
            use_pca=req.use_pca,
            target_pca_components=req.target_pca_components,
        )
        eval_metrics = {
            m["model_name"]: {
                "rmse": m["rmse"],
                "mae": m["mae"],
                "r2": m["r2"],
            }
            for m in results.get("models", [])
        }
        return {
            "success": True,
            "results": results,
            "best_model": results.get("best_model"),
            "models": results.get("models"),
            "pca_diagnostics": results.get("pca_diagnostics"),
            "test_predictions": results.get("actual_vs_predicted_sample"),
            "evaluation_metrics": eval_metrics,
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model training error: {exc}",
        )


@router.post("/valuation-categories")
async def evaluate_valuation_categories(
    req: ValuationClassifiersRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Section 2: Valuation categories classification (RF, Logistic Regression, SVM) and distribution."""
    df = get_user_dataframe(user["email"])
    try:
        results = MLService.evaluate_valuation_tiers(
            df,
            feature_cols=req.feature_columns,
            target_col=req.target_column,
            custom_bands=req.custom_bands,
        )
        return {"success": True, "results": results}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Classification error: {exc}",
        )


@router.post("/valuation-estimate-single")
async def estimate_single_valuation(
    req: SingleValuationRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Section 2: Estimate valuation tier for an individual NFT given feature inputs."""
    res = MLService.estimate_single_nft(
        features=req.features,
        model_name=req.model_name,
    )
    return {"success": True, "prediction": res}
