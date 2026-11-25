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


COLLECTION_BENCHMARKS: Dict[str, Dict[str, Any]] = {
    "boredapeyachtclub": {
        "name": "Bored Ape Yacht Club",
        "contract": "0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        "floor_price_eth": 12.50,
        "total_supply": 10000,
        "total_volume_eth": 1450000.0,
    },
    "cryptopunks": {
        "name": "CryptoPunks",
        "contract": "0xb47e3cd837dDF8e4c57F05d70Ab865de6e193BBB",
        "floor_price_eth": 28.50,
        "total_supply": 10000,
        "total_volume_eth": 1210000.0,
    },
    "mutant-ape-yacht-club": {
        "name": "Mutant Ape Yacht Club",
        "contract": "0x60E4d786628Fea6478F785A6d7e70474ff65292e",
        "floor_price_eth": 2.15,
        "total_supply": 19500,
        "total_volume_eth": 590000.0,
    },
    "azuki": {
        "name": "Azuki",
        "contract": "0xED5AF388653567Af2F388E6224dC7C31432C952d",
        "floor_price_eth": 4.80,
        "total_supply": 10000,
        "total_volume_eth": 685000.0,
    },
    "pudgypenguins": {
        "name": "Pudgy Penguins",
        "contract": "0xBd3531dA5CF5857e7CfAA92426877b022e612cf8",
        "floor_price_eth": 9.20,
        "total_supply": 8888,
        "total_volume_eth": 345000.0,
    },
    "doodles-official": {
        "name": "Doodles",
        "contract": "0x8a90CAb2b38dba80c64b7734e58Ee1dB38B8992e",
        "floor_price_eth": 1.75,
        "total_supply": 10000,
        "total_volume_eth": 312000.0,
    },
    "doodles": {
        "name": "Doodles",
        "contract": "0x8a90CAb2b38dba80c64b7734e58Ee1dB38B8992e",
        "floor_price_eth": 1.75,
        "total_supply": 10000,
        "total_volume_eth": 312000.0,
    },
}


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
        """Fetch OpenSea collection statistics with accurate per-collection benchmarks and live API support."""
        clean_slug = (slug or "boredapeyachtclub").strip().lower()
        benchmark = COLLECTION_BENCHMARKS.get(clean_slug)
        if not benchmark:
            for k, v in COLLECTION_BENCHMARKS.items():
                if k in clean_slug or clean_slug in k:
                    benchmark = v
                    break
        if not benchmark:
            benchmark = COLLECTION_BENCHMARKS["boredapeyachtclub"]

        data = get_opensea_collection_stats(clean_slug)
        is_live = data.get("status") == "success"

        name = data.get("name") if is_live and data.get("name") else benchmark["name"]
        contract = benchmark["contract"]

        raw_floor = (data.get("floor_price") or data.get("floor_price_eth")) if is_live else None
        floor_val = float(raw_floor) if raw_floor is not None else float(benchmark["floor_price_eth"])

        raw_supply = data.get("total_supply") if is_live else None
        total_supply_val = int(raw_supply) if raw_supply is not None else int(benchmark["total_supply"])

        raw_vol = (data.get("total_volume") or data.get("total_volume_eth")) if is_live else None
        vol_val = float(raw_vol) if raw_vol is not None else float(benchmark["total_volume_eth"])

        eth_info = MarketplaceService.get_eth_price()
        eth_rate = float(eth_info.get("rate_usd") or 2800.0)

        implied_cap_eth = round(floor_val * total_supply_val, 2)
        implied_cap_usd = round(implied_cap_eth * eth_rate, 2)

        source_label = "Live OpenSea API" if is_live else "Verified Collection Benchmark (Fallback Data)"

        return {
            "slug": clean_slug,
            "name": name,
            "contract": contract,
            "floor_price_eth": floor_val,
            "total_supply": total_supply_val,
            "total_volume_eth": vol_val,
            "implied_market_cap_eth": implied_cap_eth,
            "implied_market_cap_usd": implied_cap_usd,
            "is_live": is_live,
            "source": source_label,
            "eth_rate_used": eth_rate,
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
