"""Read-only connector for Elite Bot telemetry endpoints."""
from __future__ import annotations

from typing import Optional

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


DEFAULT_BASE_URL = "http://127.0.0.1:8765"


def _normalize_base_url(base_url: str) -> str:
    value = (base_url or "").strip()
    if not value:
        return DEFAULT_BASE_URL
    if not value.startswith("http://") and not value.startswith("https://"):
        value = f"http://{value}"
    return value.rstrip("/")


def _headers(api_key: str) -> dict:
    if api_key:
        return {"X-API-Key": api_key}
    return {}


def _get_json(url: str, api_key: str = "", timeout: float = 2.5) -> dict:
    if requests is None:
        raise RuntimeError("requests is not installed in this environment")
    resp = requests.get(url, headers=_headers(api_key), timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected bot bridge response format")
    return data


def fetch_bot_health(base_url: str = DEFAULT_BASE_URL, timeout: float = 2.5) -> dict:
    url = f"{_normalize_base_url(base_url)}/health"
    return _get_json(url, timeout=timeout)


def fetch_bot_snapshot(
    base_url: str = DEFAULT_BASE_URL,
    api_key: str = "",
    timeout: float = 2.5,
) -> dict:
    url = f"{_normalize_base_url(base_url)}/snapshot"
    return _get_json(url, api_key=api_key, timeout=timeout)
