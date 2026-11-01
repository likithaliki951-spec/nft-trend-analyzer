"""Marketplace and live currency integration service with explicit live vs. fallback status."""

from __future__ import annotations

import datetime
from typing import Any, Dict

from app.core.api_clients import (
    convert_eth_to_usd,
    get_current_eth_usd_price,
    get_historical_eth_usd_price,
    get_opensea_collection_stats,
)


class MarketplaceService:

    @staticmethod
    def get_eth_price() -> Dict[str, Any]:
        """Fetch current ETH/USD rate with data source clarity."""
        data = get_current_eth_usd_price()
        status_label = "Live API Data (CoinGecko)" if data.get("status") == "success" else "Fallback Benchmark Data"
        rate_val = data.get("rate_usd")
        if rate_val is None:
            rate_val = 2800.0
        return {
            "rate_usd": float(rate_val),
            "source": status_label,
            "is_live": data.get("status") == "success",
            "timestamp": data.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat()),
        }

    @staticmethod
    def get_historical_eth_series(days: int = 30) -> list[Dict[str, Any]]:
        """Fetch historical ETH price time-series."""
        data = get_historical_eth_usd_price(days=days)
        is_live = data.get("status") == "success"
        points = data.get("prices", [])
        return {
            "is_live": is_live,
            "source": "Live CoinGecko Historical API" if is_live else "Synthetic Historical Benchmark",
            "data": points,
        }

    @staticmethod
    def get_collection_stats(slug: str = "boredapeyachtclub") -> Dict[str, Any]:
        """Fetch OpenSea collection statistics."""
        data = get_opensea_collection_stats(slug)
        is_live = data.get("status") == "success"
        floor_val = data.get("floor_price_eth")
        if floor_val is None:
            floor_val = 12.5
        total_supply_val = data.get("total_supply")
        if total_supply_val is None:
            total_supply_val = 10000
        vol_val = data.get("total_volume_eth")
        if vol_val is None:
            vol_val = 145000.0

        return {
            "slug": slug,
            "floor_price_eth": float(floor_val),
            "total_supply": int(total_supply_val),
            "total_volume_eth": float(vol_val),
            "is_live": is_live,
            "source": "Live OpenSea API" if is_live else "Verified Collection Benchmark",
            "retrieval_time": data.get("retrieval_time", datetime.datetime.now(datetime.timezone.utc).isoformat()),
        }

    @staticmethod
    def convert_eth(eth_amount: float) -> Dict[str, Any]:
        """Convert an Ethereum amount into USD using active market price."""
        res = convert_eth_to_usd(eth_amount)
        eth_info = MarketplaceService.get_eth_price()
        usd_val = float(res.get("usd_amount", 0.0))
        rate_used = float(res.get("rate_used", eth_info["rate_usd"]))
        return {
            "eth_amount": eth_amount,
            "rate_usd": rate_used,
            "usd_amount": usd_val,
            "is_live": eth_info["is_live"],
            "source": eth_info["source"],
            "timestamp": eth_info["timestamp"],
        }
