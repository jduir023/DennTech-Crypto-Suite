"""DennTech Crypto Suite — Tax Estimator Engine
Calculates realized gains/losses using FIFO, LIFO, or HIFO methods.
Supports CSV import from common exchange formats.
"""
from __future__ import annotations

import csv
import json
import pathlib
from datetime import datetime, timedelta
from typing import Optional


# ---------------------------------------------------------------------------
# CSV Import
# ---------------------------------------------------------------------------

def parse_transactions(filepath: str) -> list[dict]:
    """
    Parse a transaction CSV file.

    Expected columns (flexible):
      date, type (buy/sell/trade/income/fee), coin/asset, amount, price_usd, fee_usd

    Supported exchange formats:
      - Generic (date, type, coin, amount, price_usd, fee_usd)
      - Coinbase (Timestamp, Transaction Type, Asset, Quantity Transacted, Spot Price at Transaction, Fees)
      - Binance.US (Date(UTC), Pair, Type, Order Price, Order Amount, Total)
      - Kraken (txid, refid, time, type, subtype, aclass, asset, amount, fee)
    """
    transactions = []
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = [h.lower().strip() for h in (reader.fieldnames or [])]

        for row in reader:
            r = {k.lower().strip(): v.strip() for k, v in row.items()}

            # ---- Date ----
            date_str = (
                r.get("date") or r.get("timestamp") or r.get("time") or
                r.get("date(utc)") or ""
            )
            try:
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%m/%d/%Y",
                            "%Y-%m-%d", "%d/%m/%Y"):
                    try:
                        tx_date = datetime.strptime(date_str[:19], fmt[:len(date_str[:19])])
                        break
                    except ValueError:
                        continue
                else:
                    continue
            except Exception:
                continue

            # ---- Type ----
            tx_type = (
                r.get("type") or r.get("transaction type") or r.get("subtype") or ""
            ).lower()
            if tx_type in ("buy", "deposit", "receive", "rewards income",
                           "coinbase earn", "learning reward", "staking income", "income"):
                tx_type = "buy"
            elif tx_type in ("sell", "send", "withdrawal"):
                tx_type = "sell"
            elif tx_type in ("trade", "convert", "conversion"):
                tx_type = "trade"
            else:
                continue  # skip unsupported types

            # ---- Coin ----
            coin = (
                r.get("coin") or r.get("asset") or r.get("currency") or ""
            ).upper().split("/")[0].strip()

            # ---- Amount ----
            amount_str = (
                r.get("amount") or r.get("quantity transacted") or
                r.get("order amount") or "0"
            )
            # ---- Price ----
            price_str = (
                r.get("price_usd") or r.get("spot price at transaction") or
                r.get("order price") or r.get("price") or "0"
            )
            # ---- Fee ----
            fee_str = (
                r.get("fee_usd") or r.get("fees") or r.get("fee") or "0"
            )

            try:
                amount = abs(float(amount_str.replace(",", "").replace("$", "")))
                price = abs(float(price_str.replace(",", "").replace("$", "")))
                fee = abs(float(fee_str.replace(",", "").replace("$", "")))
            except ValueError:
                continue

            if amount == 0 or coin == "":
                continue

            transactions.append({
                "date": tx_date,
                "type": tx_type,
                "coin": coin,
                "amount": amount,
                "price_usd": price,
                "fee_usd": fee,
                "cost_basis": round(amount * price + fee, 8),
                "proceeds": round(amount * price - fee, 8) if tx_type == "sell" else 0.0,
            })

    return sorted(transactions, key=lambda x: x["date"])


# ---------------------------------------------------------------------------
# FIFO / LIFO / HIFO lot matching
# ---------------------------------------------------------------------------

def _calculate_gains(transactions: list[dict], method: str) -> list[dict]:
    """Core lot-matching engine. method: 'fifo', 'lifo', or 'hifo'."""
    # Build buy lots per coin: {coin: [{"date", "amount", "cost_per_unit"}]}
    lots: dict[str, list[dict]] = {}
    gain_events: list[dict] = []

    for tx in transactions:
        coin = tx["coin"]
        if coin not in lots:
            lots[coin] = []

        if tx["type"] in ("buy", "trade"):
            cost_per_unit = tx["cost_basis"] / tx["amount"] if tx["amount"] > 0 else 0
            lots[coin].append({
                "date": tx["date"],
                "amount": tx["amount"],
                "cost_per_unit": cost_per_unit,
            })

        elif tx["type"] == "sell":
            remaining_to_sell = tx["amount"]
            proceeds = tx["proceeds"]
            total_cost = 0.0
            available = lots.get(coin, [])

            if not available:
                # No lots to match — record as $0 cost basis (not ideal but graceful)
                gain_events.append({
                    "date": tx["date"],
                    "coin": coin,
                    "amount": tx["amount"],
                    "proceeds": round(proceeds, 2),
                    "cost_basis": 0.0,
                    "gain_loss": round(proceeds, 2),
                    "holding_days": 0,
                    "term": "short",
                    "method": method,
                })
                continue

            # Sort lots by method
            if method == "fifo":
                sorted_lots = available  # already ascending by date
            elif method == "lifo":
                sorted_lots = list(reversed(available))
            elif method == "hifo":
                sorted_lots = sorted(available, key=lambda x: x["cost_per_unit"], reverse=True)
            else:
                sorted_lots = available

            used_indices = []
            for i, lot in enumerate(sorted_lots):
                if remaining_to_sell <= 0:
                    break
                sell_qty = min(lot["amount"], remaining_to_sell)
                total_cost += sell_qty * lot["cost_per_unit"]
                holding_days = (tx["date"] - lot["date"]).days

                gain_events.append({
                    "date": tx["date"],
                    "coin": coin,
                    "amount": round(sell_qty, 8),
                    "proceeds": round((sell_qty / tx["amount"]) * proceeds, 2),
                    "cost_basis": round(sell_qty * lot["cost_per_unit"], 2),
                    "gain_loss": round(
                        (sell_qty / tx["amount"]) * proceeds - sell_qty * lot["cost_per_unit"], 2
                    ),
                    "holding_days": holding_days,
                    "term": "long" if holding_days >= 365 else "short",
                    "method": method,
                })
                remaining_to_sell -= sell_qty
                lot["amount"] -= sell_qty
                if lot["amount"] <= 1e-10:
                    used_indices.append(i)

            # Remove exhausted lots from the original list
            lots[coin] = [l for l in available if l["amount"] > 1e-10]

    return gain_events


def calculate_gains_fifo(transactions: list[dict]) -> list[dict]:
    return _calculate_gains(transactions, "fifo")


def calculate_gains_lifo(transactions: list[dict]) -> list[dict]:
    return _calculate_gains(transactions, "lifo")


def calculate_gains_hifo(transactions: list[dict]) -> list[dict]:
    return _calculate_gains(transactions, "hifo")


def generate_report(gain_events: list[dict], tax_year: Optional[int] = None) -> dict:
    """Summarise gain events into a tax report."""
    events = gain_events
    if tax_year:
        events = [e for e in events if e["date"].year == tax_year]

    short_term = [e for e in events if e["term"] == "short"]
    long_term = [e for e in events if e["term"] == "long"]

    st_gains = sum(e["gain_loss"] for e in short_term if e["gain_loss"] > 0)
    st_losses = sum(e["gain_loss"] for e in short_term if e["gain_loss"] < 0)
    lt_gains = sum(e["gain_loss"] for e in long_term if e["gain_loss"] > 0)
    lt_losses = sum(e["gain_loss"] for e in long_term if e["gain_loss"] < 0)

    net_st = st_gains + st_losses
    net_lt = lt_gains + lt_losses
    net_total = net_st + net_lt

    # Per-coin summary
    by_coin: dict[str, dict] = {}
    for e in events:
        coin = e["coin"]
        if coin not in by_coin:
            by_coin[coin] = {"total_gain_loss": 0.0, "num_sales": 0}
        by_coin[coin]["total_gain_loss"] += e["gain_loss"]
        by_coin[coin]["num_sales"] += 1

    return {
        "tax_year": tax_year,
        "total_events": len(events),
        "short_term_gains": round(st_gains, 2),
        "short_term_losses": round(st_losses, 2),
        "net_short_term": round(net_st, 2),
        "long_term_gains": round(lt_gains, 2),
        "long_term_losses": round(lt_losses, 2),
        "net_long_term": round(net_lt, 2),
        "net_total": round(net_total, 2),
        "by_coin": {k: round(v["total_gain_loss"], 2) for k, v in by_coin.items()},
        "events": events,
    }


def export_csv(report: dict, filepath: str) -> None:
    """Export gain events to a CSV file."""
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Date", "Coin", "Amount Sold", "Proceeds ($)", "Cost Basis ($)",
            "Gain/Loss ($)", "Holding Days", "Term", "Method"
        ])
        for e in report.get("events", []):
            writer.writerow([
                e["date"].strftime("%Y-%m-%d"),
                e["coin"],
                e["amount"],
                e["proceeds"],
                e["cost_basis"],
                e["gain_loss"],
                e["holding_days"],
                e["term"].capitalize(),
                e["method"].upper(),
            ])
