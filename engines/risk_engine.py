"""DennTech Crypto Suite — Risk & Position Size Engine"""
from __future__ import annotations


def calculate_position(
    account_balance: float,
    risk_pct: float,
    entry_price: float,
    stop_loss_price: float,
    leverage: float = 1.0,
    fee_pct: float = 0.1,
    take_profit_price: float = 0.0,
) -> dict:
    """
    Calculate position sizing and risk metrics.

    Returns a dict with all key risk figures.
    """
    if entry_price <= 0 or stop_loss_price <= 0:
        raise ValueError("Prices must be positive")
    if entry_price == stop_loss_price:
        raise ValueError("Stop loss cannot equal entry price")
    if leverage < 1:
        leverage = 1.0

    is_long = entry_price > stop_loss_price

    risk_amount = account_balance * (risk_pct / 100)
    stop_distance_pct = abs(entry_price - stop_loss_price) / entry_price

    # Position size so that if stop is hit, loss == risk_amount
    position_size_usd = (risk_amount / stop_distance_pct) * leverage
    position_size_usd = min(position_size_usd, account_balance * leverage)
    position_size_units = position_size_usd / entry_price
    required_margin = position_size_usd / leverage

    # Fees
    fee_open = position_size_usd * (fee_pct / 100)
    fee_close = position_size_usd * (fee_pct / 100)
    total_fees = fee_open + fee_close

    # Breakeven price
    fee_move = total_fees / position_size_units
    if is_long:
        breakeven_price = entry_price + fee_move
    else:
        breakeven_price = entry_price - fee_move

    # Liquidation price (simplified — exchange maintains ~0.5% margin)
    maintenance_pct = 0.005
    if leverage > 1:
        if is_long:
            liq_price = entry_price * (1 - (1 / leverage) + maintenance_pct)
        else:
            liq_price = entry_price * (1 + (1 / leverage) - maintenance_pct)
        liq_price = round(liq_price, 6)
    else:
        liq_price = 0.0

    # Reward & R:R
    if take_profit_price > 0:
        if is_long:
            gross_reward = (take_profit_price - entry_price) * position_size_units
        else:
            gross_reward = (entry_price - take_profit_price) * position_size_units
        reward_amount = max(0.0, gross_reward - total_fees)
        rr_ratio = reward_amount / risk_amount if risk_amount > 0 else 0.0
    else:
        reward_amount = 0.0
        rr_ratio = 0.0

    max_loss = risk_amount + total_fees

    # Account risk percentage including fees
    account_risk_pct_actual = (max_loss / account_balance * 100) if account_balance > 0 else 0

    return {
        "risk_amount": round(risk_amount, 2),
        "max_loss": round(max_loss, 2),
        "account_risk_pct_actual": round(account_risk_pct_actual, 2),
        "position_size_usd": round(position_size_usd, 2),
        "position_size_units": round(position_size_units, 6),
        "required_margin": round(required_margin, 2),
        "leveraged_exposure": round(position_size_usd, 2),
        "stop_distance_pct": round(stop_distance_pct * 100, 2),
        "fee_open": round(fee_open, 2),
        "fee_close": round(fee_close, 2),
        "total_fees": round(total_fees, 2),
        "liquidation_price": liq_price if liq_price > 0 else None,
        "breakeven_price": round(breakeven_price, 6),
        "reward_amount": round(reward_amount, 2),
        "risk_reward_ratio": round(rr_ratio, 2),
        "is_long": is_long,
    }
