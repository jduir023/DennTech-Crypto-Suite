"""DennTech Crypto Suite — Portfolio History Engine
Saves daily snapshots of total portfolio value and tracks equity over time.
"""
from __future__ import annotations

import json
import pathlib
from datetime import datetime


HISTORY_FILE = "portfolio_history.json"


def _path(data_dir: pathlib.Path) -> pathlib.Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / HISTORY_FILE


def load_history(data_dir: pathlib.Path) -> list[dict]:
    """Load snapshot history. Each entry: {date, total_value, cost_basis, pnl}"""
    p = _path(data_dir)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_snapshot(
    data_dir: pathlib.Path,
    total_value: float,
    cost_basis: float,
) -> list[dict]:
    """
    Append or update today's snapshot. Returns updated history.
    Only one snapshot per calendar day is kept (overwrites same-day entry).
    """
    history = load_history(data_dir)
    today = datetime.now().strftime("%Y-%m-%d")
    pnl = total_value - cost_basis
    pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0.0

    snapshot = {
        "date": today,
        "total_value": round(total_value, 2),
        "cost_basis": round(cost_basis, 2),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
    }

    # Replace today's entry if already exists
    for i, entry in enumerate(history):
        if entry.get("date") == today:
            history[i] = snapshot
            _path(data_dir).write_text(json.dumps(history, indent=2), encoding="utf-8")
            return history

    history.append(snapshot)
    _path(data_dir).write_text(json.dumps(history, indent=2), encoding="utf-8")
    return history
