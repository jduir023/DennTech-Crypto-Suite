"""
DennTech Crypto Suite — Smoke Test
Tests all engine modules for calculation accuracy and edge-case guards.
Run: python smoke_test.py
"""
from __future__ import annotations
import sys, traceback
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
WARN_C = "\033[33mWARN\033[0m"

results: list[tuple[str, bool, str]] = []

def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, condition, detail))
    status = PASS if condition else FAIL
    print(f"  [{status}] {name}" + (f"  —  {detail}" if detail else ""))

def section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ===========================================================================
# 1. RISK ENGINE
# ===========================================================================
section("1. Risk Engine")

from engines.risk_engine import calculate_position

# Basic LONG position
r = calculate_position(
    account_balance=10_000, risk_pct=1.0,
    entry_price=50_000, stop_loss_price=49_000,
    leverage=1.0, fee_pct=0.1, take_profit_price=0,
)
expected_risk = 100.0                          # 10_000 * 1% = $100
stop_dist_pct = abs(50_000 - 49_000) / 50_000  # 0.02 = 2%
expected_pos  = 100.0 / stop_dist_pct          # $5_000

check("LONG risk_amount = balance × risk_pct/100",
      abs(r["risk_amount"] - expected_risk) < 0.01,
      f"got ${r['risk_amount']}, expected ${expected_risk}")

check("LONG position_size_usd",
      abs(r["position_size_usd"] - expected_pos) < 1.0,
      f"got ${r['position_size_usd']}, expected ${expected_pos}")

check("LONG is_long = True",
      r["is_long"] is True)

check("LONG stop_distance_pct = 2.00%",
      abs(r["stop_distance_pct"] - 2.00) < 0.01,
      f"got {r['stop_distance_pct']}%")

# Breakeven > entry for LONG
check("LONG breakeven > entry (covers fees)",
      r["breakeven_price"] > 50_000)

# SHORT position (with fees so breakeven is meaningful)
r_short = calculate_position(
    account_balance=10_000, risk_pct=2.0,
    entry_price=50_000, stop_loss_price=51_000,
    leverage=1.0, fee_pct=0.1, take_profit_price=0,
)
check("SHORT is_long = False",
      r_short["is_long"] is False)
check("SHORT breakeven < entry (fees create a lower breakeven for shorts)",
      r_short["breakeven_price"] < 50_000)

# R:R ratio with TP
r_rr = calculate_position(
    account_balance=10_000, risk_pct=1.0,
    entry_price=50_000, stop_loss_price=49_000,
    leverage=1.0, fee_pct=0.0, take_profit_price=53_000,
)
# reward gross = (53000 - 50000) * pos_units; risk = 100
# pos = 100 / 0.02 = 5000; units = 5000/50000 = 0.1
# gross_reward = 3000 * 0.1 = 300; rr = 300/100 = 3.0
expected_rr = 3.0
check("R:R ratio accuracy (3:1 trade)",
      abs(r_rr["risk_reward_ratio"] - expected_rr) < 0.05,
      f"got {r_rr['risk_reward_ratio']}, expected {expected_rr}")

# Leverage liq price
r_lev = calculate_position(
    account_balance=10_000, risk_pct=1.0,
    entry_price=50_000, stop_loss_price=49_000,
    leverage=10.0, fee_pct=0.1,
)
check("Leveraged position has liquidation price",
      r_lev["liquidation_price"] is not None and r_lev["liquidation_price"] > 0)
check("Liq price < entry for LONG leveraged",
      r_lev["liquidation_price"] < 50_000)

# Error guards
try:
    calculate_position(10_000, 1.0, 100, 100)  # same entry & SL
    check("stop==entry raises ValueError", False, "no exception raised")
except ValueError:
    check("stop==entry raises ValueError", True)

try:
    calculate_position(10_000, 1.0, 0, 100)  # zero entry price
    check("entry=0 raises ValueError", False, "no exception raised")
except ValueError:
    check("entry=0 raises ValueError", True)

# ===========================================================================
# 2. DCA ENGINE
# ===========================================================================
section("2. DCA Engine")

from engines.dca_engine import simulate_dca

# Build synthetic 90-day price history (flat $1000)
base = datetime(2024, 1, 1)
flat_history = [(base + timedelta(days=i), 1000.0) for i in range(90)]

r = simulate_dca(flat_history, amount_per_period=100, frequency_days=7)
check("DCA no error on flat history", "error" not in r)

summ = r["summary"]
# Weekly on 90 days → ~12 or 13 purchases
check("DCA purchase count > 0", r["purchases"] and len(r["purchases"]) > 0,
      f"purchases={len(r['purchases'])}")
expected_invested = len(r["purchases"]) * 100.0
check("DCA total_invested = count × amount",
      abs(summ["total_invested"] - expected_invested) < 0.01,
      f"got {summ['total_invested']}, expected {expected_invested}")

# At flat price, DCA and lump sum should have same return_pct (0%)
check("DCA return = 0% on flat prices",
      abs(summ["total_return_pct"]) < 0.01,
      f"got {summ['total_return_pct']:.4f}%")
check("Lump sum return = 0% on flat prices",
      abs(summ["lump_sum_return_pct"]) < 0.01,
      f"got {summ['lump_sum_return_pct']:.4f}%")

# Rising price: DCA should underperform lump sum (higher avg cost)
rising_history = [(base + timedelta(days=i), 1000.0 + i * 10) for i in range(90)]
r2 = simulate_dca(rising_history, amount_per_period=100, frequency_days=7)
check("DCA < lump_sum in rising market",
      r2["summary"]["final_value"] <= r2["summary"]["lump_sum_value"],
      f"dca={r2['summary']['final_value']}, ls={r2['summary']['lump_sum_value']}")

# Falling price: DCA should outperform lump sum
falling_history = [(base + timedelta(days=i), max(1000.0 - i * 5, 10)) for i in range(90)]
r3 = simulate_dca(falling_history, amount_per_period=100, frequency_days=7)
check("DCA >= lump_sum in falling market",
      r3["summary"]["final_value"] >= r3["summary"]["lump_sum_value"],
      f"dca={r3['summary']['final_value']}, ls={r3['summary']['lump_sum_value']}")

# final_value = total_units × last_price
last_price = flat_history[-1][1]
expected_final = summ["total_units"] * last_price
check("DCA final_value = total_units × last_price",
      abs(summ["final_value"] - expected_final) < 0.01,
      f"got {summ['final_value']}, expected {expected_final}")

# Empty history
r_empty = simulate_dca([], 100, 7)
check("DCA returns error on empty history", "error" in r_empty)

# Short history (< 2 points)
r_short = simulate_dca([(base, 1000.0)], 100, 7)
check("DCA returns error on 1-point history", "error" in r_short)

# ===========================================================================
# 3. PORTFOLIO ENGINE
# ===========================================================================
section("3. Portfolio Engine")

from engines.portfolio_engine import add_holding, calculate_pnl, remove_holding, update_holding

port = []
port = add_holding(port, "bitcoin", "BTC", 1.0, 40_000.0, "Bitcoin")
check("Add holding creates entry", len(port) == 1)
check("Holding amount = 1.0", port[0]["amount"] == 1.0)
check("Holding avg_buy_price = 40000", port[0]["avg_buy_price"] == 40_000.0)

# Weighted average on duplicate
port = add_holding(port, "bitcoin", "BTC", 1.0, 60_000.0, "Bitcoin")
check("Duplicate holding merges", len(port) == 1)
check("Merged amount = 2.0", port[0]["amount"] == 2.0)
expected_avg = (1.0 * 40_000 + 1.0 * 60_000) / 2.0  # 50_000
check("Weighted avg price = 50000",
      abs(port[0]["avg_buy_price"] - expected_avg) < 0.01,
      f"got {port[0]['avg_buy_price']}")

# PnL accuracy
enriched = calculate_pnl(port, {"bitcoin": 55_000.0})
check("calculate_pnl returns enriched list", len(enriched) == 1)
e = enriched[0]
cost_basis = 2.0 * 50_000  # 100_000
current_value = 2.0 * 55_000  # 110_000
expected_pnl = current_value - cost_basis  # 10_000
expected_pnl_pct = expected_pnl / cost_basis * 100  # 10%
check("PnL = (current - avg_buy) × amount",
      abs(e["pnl"] - expected_pnl) < 0.01,
      f"got {e['pnl']}, expected {expected_pnl}")
check("PnL % = 10.00%",
      abs(e["pnl_pct"] - expected_pnl_pct) < 0.01,
      f"got {e['pnl_pct']:.2f}%, expected {expected_pnl_pct:.2f}%")
check("current_value = amount × current_price",
      abs(e["current_value"] - current_value) < 0.01,
      f"got {e['current_value']}, expected {current_value}")

# Negative PnL
enriched_loss = calculate_pnl(port, {"bitcoin": 40_000.0})
check("Negative PnL when price < avg_buy",
      enriched_loss[0]["pnl"] < 0)

# Remove holding
port = remove_holding(port, "bitcoin")
check("remove_holding empties portfolio", len(port) == 0)

# ===========================================================================
# 4. TAX ENGINE
# ===========================================================================
section("4. Tax Engine")

from engines.tax_engine import _calculate_gains, generate_report

# Build synthetic transactions
now = datetime(2023, 6, 1)
txns = [
    # Buy 1 BTC at $20,000
    {"date": now, "type": "buy", "coin": "BTC", "amount": 1.0,
     "price_usd": 20_000, "fee_usd": 0, "cost_basis": 20_000.0, "proceeds": 0.0},
    # Buy 1 BTC at $30,000 (1 day later)
    {"date": now + timedelta(days=1), "type": "buy", "coin": "BTC", "amount": 1.0,
     "price_usd": 30_000, "fee_usd": 0, "cost_basis": 30_000.0, "proceeds": 0.0},
    # Sell 1.5 BTC at $40,000 (still <1yr)
    {"date": now + timedelta(days=30), "type": "sell", "coin": "BTC", "amount": 1.5,
     "price_usd": 40_000, "fee_usd": 0, "cost_basis": 0.0, "proceeds": 60_000.0},
]

# FIFO: consume $20k lot first, then $30k lot
fifo_events = _calculate_gains(txns, "fifo")
fifo_gain = sum(e["gain_loss"] for e in fifo_events)
# Sell 1.5: 1 BTC from $20k lot = $20k cost + 0.5 BTC from $30k lot = $15k cost = $35k total cost
# proceeds = $60k, gain = $25k
check("FIFO gain = $25,000",
      abs(fifo_gain - 25_000) < 0.01,
      f"got ${fifo_gain:,.2f}")

# LIFO: consume $30k lot first, then $20k lot
lifo_events = _calculate_gains(txns, "lifo")
lifo_gain = sum(e["gain_loss"] for e in lifo_events)
# Sell 1.5: 1 BTC from $30k lot = $30k cost + 0.5 BTC from $20k lot = $10k cost = $40k total cost
# proceeds = $60k, gain = $20k
check("LIFO gain = $20,000",
      abs(lifo_gain - 20_000) < 0.01,
      f"got ${lifo_gain:,.2f}")

# HIFO: consume highest cost first — $30k first, then $20k (same as LIFO here)
hifo_events = _calculate_gains(txns, "hifo")
hifo_gain = sum(e["gain_loss"] for e in hifo_events)
check("HIFO gain = $20,000 (same as LIFO here)",
      abs(hifo_gain - 20_000) < 0.01,
      f"got ${hifo_gain:,.2f}")

# FIFO < LIFO (maximizes gains; LIFO minimizes here)
check("FIFO gain > HIFO gain (HIFO minimizes gain)",
      fifo_gain >= hifo_gain,
      f"FIFO={fifo_gain}, HIFO={hifo_gain}")

# Short-term flag: held < 365 days → short-term
for e in fifo_events:
    check(f"FIFO event term = short-term (held {(e['date'] - e.get('lot_date', e['date'])).days} days)",
          e.get("term", "short") == "short")
    break  # just check first one

# generate_report summary
report = generate_report(fifo_events)
check("report has net_total key", "net_total" in report)
check("report net_total matches sum of gains",
      abs(report["net_total"] - fifo_gain) < 0.01,
      f"report={report['net_total']}, sum={fifo_gain}")

# Long-term: sell after 366 days
txns_lt = [
    {"date": now, "type": "buy", "coin": "ETH", "amount": 10.0,
     "price_usd": 1_000, "fee_usd": 0, "cost_basis": 10_000.0, "proceeds": 0.0},
    {"date": now + timedelta(days=366), "type": "sell", "coin": "ETH", "amount": 10.0,
     "price_usd": 2_000, "fee_usd": 0, "cost_basis": 0.0, "proceeds": 20_000.0},
]
lt_events = _calculate_gains(txns_lt, "fifo")
check("Long-term flag set for holdings > 365 days",
      lt_events and lt_events[0].get("term") == "long",
      f"term={lt_events[0].get('term') if lt_events else 'no events'}")

# ===========================================================================
# 5. STRATEGY ENGINE
# ===========================================================================
section("5. Strategy Engine")

from engines.strategy_engine import run_backtest, STRATEGIES

# Build synthetic OHLCV: 90 candles, slow uptrend
ohlcv = []
price = 30_000.0
for i in range(90):
    o = price
    c = price * (1 + 0.001)  # 0.1% daily gain
    h = max(o, c) * 1.005
    l = min(o, c) * 0.995
    ohlcv.append([i * 86_400_000, o, h, l, c])
    price = c

# All 25 strategies should run without error
strategy_errors = []
for pack, strategies in STRATEGIES.items():
    for strat_name, strat_def in strategies.items():
        param_list = strat_def.get("params", [])
        params = {p["name"]: p.get("default", p.get("min", 1)) for p in param_list}
        params["capital"] = 10_000
        params["fee_pct"] = 0.1
        params["trade_size_pct"] = 10
        r = run_backtest(ohlcv, pack, strat_name, params)
        if "error" in r and r["error"] not in ("No trades were generated.", "Insufficient data for this strategy."):
            strategy_errors.append(f"{pack}/{strat_name}: {r['error']}")

check(f"All 25 strategies run without unexpected errors",
      len(strategy_errors) == 0,
      "; ".join(strategy_errors) if strategy_errors else "")

# Equity curve starts at capital
r = run_backtest(ohlcv, "Trend Following", "SMA Crossover", {
    "fast": 5, "slow": 20, "capital": 10_000, "fee_pct": 0.0, "trade_size_pct": 100,
})
if "error" not in r:
    equity = r.get("equity_curve", [10_000])
    check("Equity curve starts at capital",
          abs(equity[0] - 10_000) < 0.01,
          f"got {equity[0]}")

    # win_rate = wins/total_trades * 100
    total = r.get("total_trades", 0)
    wins  = r.get("wins", 0)
    if total > 0:
        expected_wr = wins / total * 100
        check("win_rate = wins/total_trades × 100",
              abs(r["win_rate"] - expected_wr) < 0.01,
              f"wins={wins}, total={total}, wr={r['win_rate']:.1f}%")

# <30 candles guard
r_short = run_backtest(ohlcv[:10], "Trend Following", "SMA Crossover", {
    "fast": 5, "slow": 20, "capital": 10_000, "fee_pct": 0.0, "trade_size_pct": 100,
})
check("run_backtest handles <30 candles gracefully",
      "error" in r_short or r_short.get("total_trades", 0) == 0)

# ===========================================================================
# SUMMARY
# ===========================================================================
section("SUMMARY")
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
total  = len(results)
print(f"\n  Total: {total}   Passed: {passed}   Failed: {failed}\n")

if failed:
    print("  Failed tests:")
    for name, ok, detail in results:
        if not ok:
            print(f"    ✗  {name}" + (f"  ({detail})" if detail else ""))
    sys.exit(1)
else:
    print("  All tests passed!")
    sys.exit(0)
