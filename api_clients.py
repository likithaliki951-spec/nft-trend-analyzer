"""Secure, cached API clients for CoinGecko and OpenSea with rate-limit and offline protection."""

from __future__ import annotations

import datetime
import os
import time
from typing import Any

import requests

# In-memory TTL caches to prevent repeated requests and respect rate limits
_CACHE: dict[str, tuple[float, Any]] = {}
CACHE_TTL_SECONDS = 300.0  # 5 minutes


def _get_cached(key: str) -> Any | None:
    if key in _CACHE:
        timestamp, value = _CACHE[key]
        if time.time() - timestamp < CACHE_TTL_SECONDS:
            return value
    return None


def _set_cached(key: str, value: Any) -> None:
    _CACHE[key] = (time.time(), value)


def clear_api_cache() -> None:
    """Clear all in-memory API response caches."""
    _CACHE.clear()


# ==============================================================================
# CoinGecko Integration
# ==============================================================================

COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"


def get_current_eth_usd_price() -> dict[str, Any]:
    """Retrieve the current ETH/USD exchange rate from CoinGecko.

    Respects rate limits, uses in-memory caching, and handles network failures gracefully.
    """
    cache_key = "coingecko_eth_usd_current"
    cached = _get_cached(cache_key)
    if cached is not None:
        return {**cached, "is_cached": True}

    api_key = os.environ.get("COINGECKO_API_KEY", "")
    headers = {"Accept": "application/json"}
    if api_key:
        headers["x-cg-demo-api-key"] = api_key

    url = f"{COINGECKO_BASE_URL}/simple/price"
    params = {"ids": "ethereum", "vs_currencies": "usd"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=6.0)
        if response.status_code == 200:
            data = response.json()
            rate = float(data.get("ethereum", {}).get("usd", 0.0))
            if rate > 0:
                result = {
                    "status": "success",
                    "rate_usd": rate,
                    "currency_pair": "ETH/USD",
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "source": "CoinGecko API (Live)",
                    "is_cached": False,
                }
                _set_cached(cache_key, result)
                return result
        elif response.status_code == 429:
            return {
                "status": "rate_limited",
                "message": "CoinGecko public rate limit exceeded. Please wait a moment or configure COINGECKO_API_KEY.",
                "rate_usd": None,
            }
        else:
            return {
                "status": "http_error",
                "message": f"CoinGecko API returned HTTP status {response.status_code}.",
                "rate_usd": None,
            }
    except requests.exceptions.Timeout:
        return {"status": "timeout", "message": "CoinGecko request timed out after 6 seconds.", "rate_usd": None}
    except requests.exceptions.RequestException as error:
        return {"status": "network_error", "message": f"Network error contacting CoinGecko: {error}", "rate_usd": None}

    return {"status": "unknown_error", "message": "Could not parse CoinGecko price.", "rate_usd": None}


def get_historical_eth_usd_price(target_date: datetime.date | str) -> dict[str, Any]:
    """Retrieve historical ETH/USD price for a specific date (DD-MM-YYYY) from CoinGecko."""
    if isinstance(target_date, str):
        try:
            parsed_d = datetime.date.fromisoformat(target_date)
        except ValueError:
            return {"status": "invalid_date", "message": f"Invalid date string format: {target_date}"}
    else:
        parsed_d = target_date

    date_param = parsed_d.strftime("%d-%m-%Y")
    cache_key = f"coingecko_eth_hist_{date_param}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return {**cached, "is_cached": True}

    api_key = os.environ.get("COINGECKO_API_KEY", "")
    headers = {"Accept": "application/json"}
    if api_key:
        headers["x-cg-demo-api-key"] = api_key

    url = f"{COINGECKO_BASE_URL}/coins/ethereum/history"
    params = {"date": date_param, "localization": "false"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=6.0)
        if response.status_code == 200:
            data = response.json()
            market_data = data.get("market_data", {})
            current_price = market_data.get("current_price", {})
            rate = float(current_price.get("usd", 0.0))
            if rate > 0:
                result = {
                    "status": "success",
                    "rate_usd": rate,
                    "date": parsed_d.isoformat(),
                    "source": "CoinGecko Historical API",
                    "is_cached": False,
                }
                _set_cached(cache_key, result)
                return result
        elif response.status_code == 429:
            return {"status": "rate_limited", "message": "CoinGecko rate limit exceeded.", "rate_usd": None}
    except Exception as error:
        return {"status": "error", "message": str(error), "rate_usd": None}

    return {"status": "not_found", "message": f"Historical price unavailable for {parsed_d}.", "rate_usd": None}


def convert_eth_to_usd(
    eth_amount: float, historical_date: datetime.date | None = None
) -> dict[str, Any]:
    """Convert ETH to USD using timestamp-matched historical price when available, or labeled current rate."""
    if eth_amount <= 0:
        return {"usd_amount": 0.0, "rate_used": 0.0, "rate_type": "zero_amount"}

    # Attempt timestamp-matched historical conversion
    if historical_date is not None:
        hist_res = get_historical_eth_usd_price(historical_date)
        if hist_res.get("status") == "success" and hist_res.get("rate_usd"):
            rate = hist_res["rate_usd"]
            return {
                "usd_amount": round(eth_amount * rate, 2),
                "rate_used": rate,
                "rate_type": f"Historical rate on {historical_date}",
                "is_estimate": False,
            }

    # Fallback to current rate
    current_res = get_current_eth_usd_price()
    if current_res.get("status") == "success" and current_res.get("rate_usd"):
        rate = current_res["rate_usd"]
        return {
            "usd_amount": round(eth_amount * rate, 2),
            "rate_used": rate,
            "rate_type": "Current spot rate (Estimate)",
            "is_estimate": True,
        }

    # Ultimate offline static fallback with clear labeling
    fallback_rate = 2600.0
    return {
        "usd_amount": round(eth_amount * fallback_rate, 2),
        "rate_used": fallback_rate,
        "rate_type": "Offline benchmark default ($2,600/ETH)",
        "is_estimate": True,
    }


# ==============================================================================
# OpenSea Integration
# ==============================================================================

OPENSEA_API_URL = "https://api.opensea.io/api/v2"


def get_opensea_collection_stats(collection_slug: str) -> dict[str, Any]:
    """Retrieve collection details and floor prices from the official OpenSea API v2.

    Safely reads credentials from OPENSEA_API_KEY environment variable. Never hardcodes secrets.
    """
    clean_slug = collection_slug.strip().lower()
    if not clean_slug:
        return {"status": "error", "message": "Please enter a valid collection slug."}

    cache_key = f"opensea_coll_{clean_slug}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return {**cached, "is_cached": True}

    api_key = os.environ.get("OPENSEA_API_KEY", "")
    if not api_key:
        return {
            "status": "no_credentials",
            "message": "OpenSea API key not configured.",
            "guide": (
                "To enable live OpenSea queries, set the OPENSEA_API_KEY environment variable "
                "or configure it in your Streamlit Cloud secrets management. "
                "The application functions normally in offline CSV mode without an API key."
            ),
        }

    headers = {
        "accept": "application/json",
        "x-api-key": api_key,
    }
    url = f"{OPENSEA_API_URL}/collections/{clean_slug}"

    try:
        response = requests.get(url, headers=headers, timeout=7.0)
        if response.status_code == 200:
            data = response.json()
            collection = data.get("collection", {}) or data

            # Extract metrics
            floor_price = None
            if "floor_price" in collection:
                floor_price = collection.get("floor_price")
            elif "stats" in collection and "floor_price" in collection["stats"]:
                floor_price = collection["stats"]["floor_price"]

            result = {
                "status": "success",
                "collection_slug": clean_slug,
                "name": collection.get("name", clean_slug.title()),
                "description": collection.get("description", "No description available.")[:250],
                "floor_price": floor_price,
                "floor_price_symbol": "ETH",
                "total_supply": collection.get("total_supply"),
                "retrieval_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "source": "OpenSea API v2",
                "is_cached": False,
            }
            _set_cached(cache_key, result)
            return result
        elif response.status_code == 404:
            return {"status": "not_found", "message": f"Collection '{clean_slug}' not found on OpenSea."}
        elif response.status_code == 401 or response.status_code == 403:
            return {"status": "auth_error", "message": "Invalid or expired OPENSEA_API_KEY."}
        elif response.status_code == 429:
            return {"status": "rate_limited", "message": "OpenSea API rate limit reached. Please retry later."}
        else:
            return {"status": "http_error", "message": f"OpenSea API returned HTTP {response.status_code}."}
    except requests.exceptions.Timeout:
        return {"status": "timeout", "message": "OpenSea request timed out after 7 seconds."}
    except requests.exceptions.RequestException as error:
        return {"status": "network_error", "message": f"Network error contacting OpenSea: {error}"}
