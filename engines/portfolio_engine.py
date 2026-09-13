"""DennTech Crypto Suite — Portfolio Engine
Local portfolio management with persistence.
"""
from __future__ import annotations

import json
import pathlib
from typing import Optional

PORTFOLIO_FILE = "portfolio.json"


def _path(data_dir: pathlib.Path) -> pathlib.Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / PORTFOLIO_FILE


def load_portfolio(data_dir: pathlib.Path) -> list[dict]:
    p = _path(data_dir)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_portfolio(portfolio: list[dict], data_dir: pathlib.Path) -> None:
    _path(data_dir).write_text(json.dumps(portfolio, indent=2), encoding="utf-8")


def add_holding(
    portfolio: list[dict],
    coin_id: str,
    symbol: str,
    amount: float,
    avg_buy_price: float,
    name: str = "",
    notes: str = "",
) -> list[dict]:
    """Add or update a holding. If coin_id exists, update via weighted average."""
    for h in portfolio:
        if h["coin_id"] == coin_id:
            # Weighted average buy price
            total_units = h["amount"] + amount
            if total_units > 0:
                h["avg_buy_price"] = (
                    (h["amount"] * h["avg_buy_price"] + amount * avg_buy_price)
                    / total_units
                )
            h["amount"] = total_units
            if notes:
                h["notes"] = notes
            return portfolio
    portfolio.append({
        "coin_id": coin_id,
        "symbol": symbol.upper(),
        "name": name or symbol.upper(),
        "amount": amount,
        "avg_buy_price": avg_buy_price,
        "notes": notes,
    })
    return portfolio


def remove_holding(portfolio: list[dict], coin_id: str) -> list[dict]:
    return [h for h in portfolio if h["coin_id"] != coin_id]


def update_holding(
    portfolio: list[dict],
    coin_id: str,
    amount: Optional[float] = None,
    avg_buy_price: Optional[float] = None,
    notes: Optional[str] = None,
) -> list[dict]:
    for h in portfolio:
        if h["coin_id"] == coin_id:
            if amount is not None:
                h["amount"] = amount
            if avg_buy_price is not None:
                h["avg_buy_price"] = avg_buy_price
            if notes is not None:
                h["notes"] = notes
            break
    return portfolio


def calculate_pnl(portfolio: list[dict], current_prices: dict[str, float]) -> list[dict]:
    """Enrich portfolio with current prices and PnL metrics."""
    result = []
    for h in portfolio:
        cid = h["coin_id"]
        current_price = current_prices.get(cid)
        if current_price is not None:
            cost_basis = h["amount"] * h["avg_buy_price"]
            current_value = h["amount"] * current_price
            pnl = current_value - cost_basis
            pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0.0
        else:
            current_price = None
            current_value = None
            pnl = None
            pnl_pct = None
        result.append({
            **h,
            "current_price": current_price,
            "current_value": round(current_value, 2) if current_value is not None else None,
            "cost_basis": round(h["amount"] * h["avg_buy_price"], 2),
            "pnl": round(pnl, 2) if pnl is not None else None,
            "pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
        })
    return result


def get_allocation(enriched: list[dict]) -> list[tuple[str, float]]:
    """Return (symbol, value) pairs for portfolio allocation chart."""
    items = [(h["symbol"], h["current_value"]) for h in enriched if h.get("current_value")]
    total = sum(v for _, v in items)
    if total == 0:
        return items
    return sorted(items, key=lambda x: x[1], reverse=True)


def parse_csv_import(filepath: str) -> list[dict]:
    """
    Import holdings from CSV.
    Expected columns (flexible): symbol, coin_id, amount, avg_buy_price
    Also accepts: ticker, qty, quantity, price, average_price, avg_price
    """
    import csv
    holdings = []
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_lower = {k.lower().strip(): v.strip() for k, v in row.items()}
            symbol = (
                row_lower.get("symbol") or row_lower.get("ticker") or
                row_lower.get("coin") or ""
            ).upper()
            coin_id = (
                row_lower.get("coin_id") or row_lower.get("id") or symbol.lower()
            )
            amount_str = (
                row_lower.get("amount") or row_lower.get("qty") or
                row_lower.get("quantity") or "0"
            )
            price_str = (
                row_lower.get("avg_buy_price") or row_lower.get("avg_price") or
                row_lower.get("average_price") or row_lower.get("price") or "0"
            )
            try:
                amount = float(amount_str.replace(",", ""))
                price = float(price_str.replace(",", "").replace("$", ""))
            except ValueError:
                continue
            if symbol and amount > 0 and price > 0:
                holdings.append({
                    "coin_id": coin_id,
                    "symbol": symbol,
                    "name": symbol,
                    "amount": amount,
                    "avg_buy_price": price,
                    "notes": "",
                })
    return holdings
