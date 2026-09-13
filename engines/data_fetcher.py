"""DennTech Crypto Suite — Data Fetcher
Fetches price and OHLCV data from CoinGecko free API with local caching.
"""
from __future__ import annotations

import json
import time
import pathlib
from typing import Optional

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

BASE_URL = "https://api.coingecko.com/api/v3"
CACHE_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "cache"
CACHE_TTL = 300  # seconds

COMMON_COINS: dict[str, str] = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
    "BNB": "binancecoin", "XRP": "ripple", "ADA": "cardano",
    "DOGE": "dogecoin", "AVAX": "avalanche-2", "DOT": "polkadot",
    "LINK": "chainlink", "MATIC": "matic-network", "LTC": "litecoin",
    "UNI": "uniswap", "ATOM": "cosmos", "XLM": "stellar",
    "ALGO": "algorand", "FIL": "filecoin", "TRX": "tron",
    "SHIB": "shiba-inu", "NEAR": "near", "APT": "aptos",
    "ARB": "arbitrum", "OP": "optimism", "INJ": "injective-protocol",
    "SUI": "sui",
}

COIN_DISPLAY: list[str] = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX",
    "DOT", "LINK", "MATIC", "LTC", "UNI", "ATOM", "XLM", "ALGO",
    "NEAR", "APT", "ARB", "INJ",
]


def _cache_path(key: str) -> pathlib.Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe = key.replace("/", "_").replace("?", "_").replace("&", "_").replace("=", "_")
    return CACHE_DIR / f"{safe[:120]}.json"


def _read_cache(key: str) -> Optional[object]:
    p = _cache_path(key)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if time.time() - data.get("_ts", 0) < CACHE_TTL:
            return data.get("payload")
    except Exception:
        pass
    return None


def _write_cache(key: str, payload: object) -> None:
    try:
        _cache_path(key).write_text(
            json.dumps({"_ts": time.time(), "payload": payload}),
            encoding="utf-8",
        )
    except Exception:
        pass


def _get(endpoint: str, params: dict | None = None) -> Optional[object]:
    if not REQUESTS_OK:
        return None
    cache_key = endpoint + str(sorted((params or {}).items()))
    cached = _read_cache(cache_key)
    if cached is not None:
        return cached
    try:
        resp = requests.get(
            f"{BASE_URL}{endpoint}", params=params or {}, timeout=20,
            headers={"User-Agent": "DennTech-Crypto-Suite/1.0"}
        )
        resp.raise_for_status()
        data = resp.json()
        _write_cache(cache_key, data)
        return data
    except Exception as exc:
        print(f"[DataFetcher] {exc}")
        return None


def symbol_to_id(symbol: str) -> str:
    return COMMON_COINS.get(symbol.upper(), symbol.lower())


def get_price(coin_id: str) -> Optional[float]:
    data = _get("/simple/price", {"ids": coin_id, "vs_currencies": "usd"})
    if data and coin_id in data:
        return data[coin_id].get("usd")
    return None


def get_prices(coin_ids: list[str]) -> dict[str, float]:
    if not coin_ids:
        return {}
    ids_str = ",".join(coin_ids)
    data = _get("/simple/price", {"ids": ids_str, "vs_currencies": "usd"})
    if not data:
        return {}
    return {cid: data[cid]["usd"] for cid in coin_ids if cid in data and "usd" in data[cid]}


def get_ohlcv(coin_id: str, days: int = 90) -> list[list[float]]:
    """Returns list of [timestamp_ms, open, high, low, close]."""
    data = _get(f"/coins/{coin_id}/ohlc", {"vs_currency": "usd", "days": str(days)})
    return data if data else []


def get_market_chart(coin_id: str, days: int = 365) -> dict:
    """Returns dict with 'prices', 'market_caps', 'total_volumes' each as [[ts, val], ...]."""
    data = _get(
        f"/coins/{coin_id}/market_chart",
        {"vs_currency": "usd", "days": str(days), "interval": "daily"},
    )
    return data or {}


def get_fear_and_greed() -> dict:
    """
    Fetch the Fear & Greed Index from alternative.me (free, no key required).
    Returns dict: {value, value_classification, timestamp} or {} on failure.
    """
    if not REQUESTS_OK:
        return {}
    cache_key = "fear_and_greed_index"
    cached = _read_cache(cache_key)
    if cached:
        return cached
    try:
        resp = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10,
                            headers={"User-Agent": "DennTech-Crypto-Suite/1.0"})
        resp.raise_for_status()
        data = resp.json()
        if data and "data" in data and data["data"]:
            result = {
                "value": int(data["data"][0]["value"]),
                "value_classification": data["data"][0]["value_classification"],
                "timestamp": int(data["data"][0]["timestamp"]),
            }
            _write_cache(cache_key, result)
            return result
    except Exception as exc:
        print(f"[FearGreed] {exc}")
    return {}
