"""DennTech Crypto Suite — DCA Planner & Historical Simulator"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional


def simulate_dca(
    price_history: list[tuple[datetime, float]],
    amount_per_period: float,
    frequency_days: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict:
    """
    Simulate a Dollar-Cost-Averaging strategy against historical price data.

    price_history: list of (datetime, price_usd) sorted ascending
    amount_per_period: USD invested each period
    frequency_days: interval between buys (7=weekly, 14=biweekly, 30=monthly)

    Returns dict with:
      purchases: list of purchase records
      summary: total_invested, total_units, final_value, total_return_pct,
               lump_sum_value, lump_sum_return_pct, best_price, worst_price, avg_price
      chart_data: dates, dca_values, lump_sum_values, prices
    """
    if not price_history:
        return {"error": "No price data available"}

    # Filter date range
    if start_date:
        price_history = [(d, p) for d, p in price_history if d >= start_date]
    if end_date:
        price_history = [(d, p) for d, p in price_history if d <= end_date]

    if len(price_history) < 2:
        return {"error": "Not enough price data for the selected range"}

    # Simulate DCA purchases at each interval
    purchases = []
    total_units = 0.0
    total_invested = 0.0
    next_buy_date = price_history[0][0]

    for date, price in price_history:
        if date >= next_buy_date:
            units = amount_per_period / price
            total_units += units
            total_invested += amount_per_period
            purchases.append({
                "date": date.strftime("%Y-%m-%d"),
                "price": round(price, 2),
                "units": round(units, 6),
                "amount_invested": round(amount_per_period, 2),
                "cumulative_invested": round(total_invested, 2),
                "cumulative_units": round(total_units, 6),
            })
            next_buy_date = date + timedelta(days=frequency_days)

    if not purchases:
        return {"error": "No purchases made in the selected period"}

    final_price = price_history[-1][1]
    final_value = total_units * final_price
    total_return_pct = ((final_value - total_invested) / total_invested * 100) if total_invested > 0 else 0

    # Lump sum comparison: invest total_invested at start
    lump_sum_units = total_invested / price_history[0][1]
    lump_sum_value = lump_sum_units * final_price
    lump_sum_return_pct = ((lump_sum_value - total_invested) / total_invested * 100) if total_invested > 0 else 0

    all_prices = [p for _, p in price_history]
    avg_dca_price = total_invested / total_units if total_units > 0 else 0

    # Chart data: running DCA value vs lump sum value vs price (normalised)
    chart_dates = []
    chart_dca_values = []
    chart_lump_sum_values = []
    chart_prices = []

    running_units = 0.0
    running_invested = 0.0
    purchase_lookup = {p["date"]: p for p in purchases}
    lump_sum_u = lump_sum_units

    for date, price in price_history:
        ds = date.strftime("%Y-%m-%d")
        if ds in purchase_lookup:
            running_units += purchase_lookup[ds]["units"]
            running_invested += amount_per_period
        chart_dates.append(ds)
        chart_dca_values.append(round(running_units * price, 2))
        chart_lump_sum_values.append(round(lump_sum_u * price, 2))
        chart_prices.append(round(price, 2))

    return {
        "purchases": purchases,
        "summary": {
            "total_invested": round(total_invested, 2),
            "total_units": round(total_units, 6),
            "final_value": round(final_value, 2),
            "total_return_pct": round(total_return_pct, 2),
            "lump_sum_value": round(lump_sum_value, 2),
            "lump_sum_return_pct": round(lump_sum_return_pct, 2),
            "avg_dca_price": round(avg_dca_price, 2),
            "best_price": round(min(all_prices), 2),
            "worst_price": round(max(all_prices), 2),
            "num_purchases": len(purchases),
        },
        "chart_data": {
            "dates": chart_dates,
            "dca_values": chart_dca_values,
            "lump_sum_values": chart_lump_sum_values,
            "prices": chart_prices,
        },
    }


def parse_market_chart_prices(market_chart: dict) -> list[tuple[datetime, float]]:
    """Convert CoinGecko market_chart response to (datetime, price) list."""
    prices = market_chart.get("prices", [])
    result = []
    for ts_ms, price in prices:
        dt = datetime.utcfromtimestamp(ts_ms / 1000)
        result.append((dt, float(price)))
    return sorted(result, key=lambda x: x[0])
