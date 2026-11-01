"""Section 4: Marketplace Hub, live external crypto APIs, and currency conversion."""

from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user
from app.schemas import CurrencyConvertRequest
from app.services.marketplace_service import MarketplaceService

router = APIRouter(prefix="/marketplace", tags=["Marketplace Hub"])


@router.get("/eth-usd")
async def get_eth_price(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Get live CoinGecko Ethereum price in USD with data source label."""
    price_info = MarketplaceService.get_eth_price()
    return {"success": True, "data": price_info}


@router.get("/historical-eth")
async def get_historical_eth(
    days: int = Query(30, ge=1, le=365),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get historical Ethereum price points."""
    series = MarketplaceService.get_historical_eth_series(days=days)
    return {"success": True, "series": series}


@router.get("/collection-stats")
async def get_collection_stats(
    slug: str = Query("boredapeyachtclub", min_length=2),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get live OpenSea collection stats (floor price, supply, total volume)."""
    stats = MarketplaceService.get_collection_stats(slug=slug)
    return {"success": True, "stats": stats}


@router.post("/convert")
async def convert_currency(
    req: CurrencyConvertRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Live interactive currency converter from ETH to USD."""
    conv = MarketplaceService.convert_eth(req.eth_amount)
    return {"success": True, "conversion": conv}
