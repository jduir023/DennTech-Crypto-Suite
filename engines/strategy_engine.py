"""DennTech Crypto Suite — Strategy Engine
All 25 Elite trading strategies with backtest runner.
"""
from __future__ import annotations

import math
from typing import Optional

# OHLCV: list of [timestamp_ms, open, high, low, close]
OHLCV = list[list[float]]


# ===========================================================================
# Indicator Helpers
# ===========================================================================

def _closes(ohlcv: OHLCV) -> list[float]:
    return [c[4] for c in ohlcv]

def _highs(ohlcv: OHLCV) -> list[float]:
    return [c[2] for c in ohlcv]

def _lows(ohlcv: OHLCV) -> list[float]:
    return [c[3] for c in ohlcv]

def _sma(values: list[float], period: int) -> list[Optional[float]]:
    result: list[Optional[float]] = [None] * (period - 1)
    for i in range(period - 1, len(values)):
        result.append(sum(values[i - period + 1 : i + 1]) / period)
    return result

def _ema(values: list[float], period: int) -> list[Optional[float]]:
    if len(values) < period:
        return [None] * len(values)
    result: list[Optional[float]] = [None] * (period - 1)
    k = 2.0 / (period + 1)
    ema = sum(values[:period]) / period
    result.append(ema)
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
        result.append(ema)
    return result

def _rsi(closes: list[float], period: int = 14) -> list[Optional[float]]:
    if len(closes) <= period:
        return [None] * len(closes)
    result: list[Optional[float]] = [None] * period
    gains, losses = [], []
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_g = sum(gains) / period
    avg_l = sum(losses) / period
    result.append(100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l))
    for i in range(period + 1, len(closes)):
        diff = closes[i] - closes[i - 1]
        avg_g = (avg_g * (period - 1) + max(diff, 0.0)) / period
        avg_l = (avg_l * (period - 1) + max(-diff, 0.0)) / period
        result.append(100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l))
    return result

def _macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9):
    ef = _ema(closes, fast)
    es = _ema(closes, slow)
    macd_line = [
        None if ef[i] is None or es[i] is None else ef[i] - es[i]  # type: ignore[operator]
        for i in range(len(closes))
    ]
    valid = [(i, v) for i, v in enumerate(macd_line) if v is not None]
    signal_line: list[Optional[float]] = [None] * len(closes)
    histogram: list[Optional[float]] = [None] * len(closes)
    if len(valid) >= signal:
        vals = [v for _, v in valid]
        ema_sig = _ema(vals, signal)
        for j, (i, _) in enumerate(valid):
            if ema_sig[j] is not None:
                signal_line[i] = ema_sig[j]
                histogram[i] = macd_line[i] - ema_sig[j]  # type: ignore[operator]
    return macd_line, signal_line, histogram

def _bollinger(closes: list[float], period: int = 20, std_dev: float = 2.0):
    upper: list[Optional[float]] = [None] * len(closes)
    mid:   list[Optional[float]] = [None] * len(closes)
    lower: list[Optional[float]] = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        w = closes[i - period + 1 : i + 1]
        m = sum(w) / period
        var = sum((x - m) ** 2 for x in w) / period
        s = math.sqrt(var)
        upper[i] = m + std_dev * s
        mid[i]   = m
        lower[i] = m - std_dev * s
    return upper, mid, lower

def _atr(ohlcv: OHLCV, period: int = 14) -> list[Optional[float]]:
    trs = []
    for i in range(1, len(ohlcv)):
        h, l, pc = ohlcv[i][2], ohlcv[i][3], ohlcv[i - 1][4]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    result: list[Optional[float]] = [None] * (period)
    if len(trs) < period:
        return result + [None] * (len(ohlcv) - len(result))
    atr = sum(trs[:period]) / period
    result.append(atr)
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
        result.append(atr)
    return result

def _linear_regression(values: list[float], period: int) -> list[Optional[float]]:
    """Return predicted value from linear regression over `period` bars."""
    result: list[Optional[float]] = [None] * (period - 1)
    for i in range(period - 1, len(values)):
        w = values[i - period + 1 : i + 1]
        x_mean = (period - 1) / 2
        y_mean = sum(w) / period
        num = sum((j - x_mean) * (w[j] - y_mean) for j in range(period))
        den = sum((j - x_mean) ** 2 for j in range(period))
        slope = num / den if den != 0 else 0
        intercept = y_mean - slope * x_mean
        result.append(slope * (period - 1) + intercept)
    return result

def _std(values: list[float], period: int) -> list[Optional[float]]:
    result: list[Optional[float]] = [None] * (period - 1)
    for i in range(period - 1, len(values)):
        w = values[i - period + 1 : i + 1]
        m = sum(w) / period
        result.append(math.sqrt(sum((x - m) ** 2 for x in w) / period))
    return result


# ===========================================================================
# Backtest Runner
# ===========================================================================

def _backtest(ohlcv: OHLCV, signals: list[int], params: dict) -> dict:
    closes = _closes(ohlcv)
    capital = float(params.get("capital", 10000))
    fee_pct = float(params.get("fee_pct", 0.1)) / 100
    size_pct = float(params.get("trade_size_pct", 100)) / 100

    cash = capital
    position = 0.0
    entry_price = 0.0
    in_pos = False
    trades: list[dict] = []
    equity_curve: list[float] = []

    for i, sig in enumerate(signals):
        price = closes[i]
        equity_curve.append(cash + position * price)
        if sig == 1 and not in_pos:
            spend = cash * size_pct
            fee = spend * fee_pct
            units = (spend - fee) / price
            cash -= spend
            position = units
            entry_price = price
            in_pos = True
            trades.append({"side": "BUY", "price": price, "index": i})
        elif sig == -1 and in_pos:
            proceeds = position * price
            fee = proceeds * fee_pct
            net = proceeds - fee
            pnl = net - position * entry_price
            cash += net
            trades.append({
                "side": "SELL", "price": price, "index": i,
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl / (position * entry_price) * 100, 2),
            })
            position = 0.0
            in_pos = False

    # Close open position
    if in_pos and closes:
        lp = closes[-1]
        proceeds = position * lp
        fee = proceeds * fee_pct
        net = proceeds - fee
        pnl = net - position * entry_price
        cash += net
        trades.append({
            "side": "SELL*", "price": lp, "index": len(closes) - 1,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl / (position * entry_price) * 100, 2),
        })

    sells = [t for t in trades if "pnl" in t]
    wins = [t for t in sells if t["pnl"] > 0]
    losses_list = [t for t in sells if t["pnl"] <= 0]
    total_profit = sum(t["pnl"] for t in wins)
    total_loss = abs(sum(t["pnl"] for t in losses_list))
    pf = total_profit / total_loss if total_loss > 0 else float("inf")
    win_rate = len(wins) / len(sells) * 100 if sells else 0

    peak = capital
    max_dd = 0.0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    final_eq = cash
    total_ret = (final_eq - capital) / capital * 100

    return {
        "total_return_pct": round(total_ret, 2),
        "final_equity": round(final_eq, 2),
        "total_trades": len(sells),
        "win_rate": round(win_rate, 2),
        "profit_factor": round(pf, 2) if pf != float("inf") else 999.0,
        "max_drawdown_pct": round(max_dd, 2),
        "equity_curve": equity_curve,
        "trades": trades[-100:],
    }


# ===========================================================================
# Strategy Signal Generators
# ===========================================================================

def _sig_rsi(ohlcv, p):
    closes = _closes(ohlcv)
    rsi = _rsi(closes, int(p.get("rsi_period", 14)))
    ob, os_ = float(p.get("overbought", 70)), float(p.get("oversold", 30))
    signals = [0] * len(closes)
    for i in range(1, len(closes)):
        if rsi[i] is not None and rsi[i - 1] is not None:
            if rsi[i - 1] <= os_ and rsi[i] > os_:
                signals[i] = 1
            elif rsi[i - 1] >= ob and rsi[i] < ob:
                signals[i] = -1
    return signals

def _sig_macd(ohlcv, p):
    closes = _closes(ohlcv)
    ml, sl, _ = _macd(closes, int(p.get("fast", 12)), int(p.get("slow", 26)), int(p.get("signal", 9)))
    signals = [0] * len(closes)
    for i in range(1, len(closes)):
        if ml[i] is not None and sl[i] is not None and ml[i-1] is not None and sl[i-1] is not None:
            if ml[i-1] < sl[i-1] and ml[i] >= sl[i]:
                signals[i] = 1
            elif ml[i-1] > sl[i-1] and ml[i] <= sl[i]:
                signals[i] = -1
    return signals

def _sig_ema_spread(ohlcv, p):
    closes = _closes(ohlcv)
    ef = _ema(closes, int(p.get("fast_period", 12)))
    es = _ema(closes, int(p.get("slow_period", 26)))
    threshold = float(p.get("spread_pct", 0.5)) / 100
    signals = [0] * len(closes)
    for i in range(1, len(closes)):
        if ef[i] is not None and es[i] is not None and es[i] != 0:
            spread = (ef[i] - es[i]) / es[i]
            prev_ef, prev_es = ef[i-1], es[i-1]
            if prev_ef is None or prev_es is None or prev_es == 0:
                continue
            prev_spread = (prev_ef - prev_es) / prev_es
            if prev_spread <= threshold and spread > threshold:
                signals[i] = 1
            elif prev_spread >= -threshold and spread < -threshold:
                signals[i] = -1
    return signals

def _sig_macd_histogram(ohlcv, p):
    closes = _closes(ohlcv)
    _, _, hist = _macd(closes, int(p.get("fast", 12)), int(p.get("slow", 26)), int(p.get("signal", 9)))
    signals = [0] * len(closes)
    for i in range(1, len(closes)):
        if hist[i] is not None and hist[i-1] is not None:
            if hist[i-1] <= 0 and hist[i] > 0:
                signals[i] = 1
            elif hist[i-1] >= 0 and hist[i] < 0:
                signals[i] = -1
    return signals

def _sig_sma_cross(ohlcv, p):
    closes = _closes(ohlcv)
    ss = _sma(closes, int(p.get("short_period", 10)))
    ls = _sma(closes, int(p.get("long_period", 50)))
    signals = [0] * len(closes)
    for i in range(1, len(closes)):
        if ss[i] is not None and ls[i] is not None and ss[i-1] is not None and ls[i-1] is not None:
            if ss[i-1] < ls[i-1] and ss[i] >= ls[i]:
                signals[i] = 1
            elif ss[i-1] > ls[i-1] and ss[i] <= ls[i]:
                signals[i] = -1
    return signals

def _sig_trend_following(ohlcv, p):
    closes = _closes(ohlcv)
    ss = _sma(closes, int(p.get("short_period", 20)))
    ls = _sma(closes, int(p.get("long_period", 50)))
    rsi = _rsi(closes, 14)
    rsi_max = float(p.get("rsi_max", 65))
    signals = [0] * len(closes)
    for i in range(1, len(closes)):
        if None in (ss[i], ls[i], ss[i-1], ls[i-1], rsi[i]):
            continue
        if ss[i-1] < ls[i-1] and ss[i] >= ls[i] and rsi[i] < rsi_max:
            signals[i] = 1
        elif ss[i] < ls[i]:
            signals[i] = -1
    return signals

def _sig_momentum(ohlcv, p):
    closes = _closes(ohlcv)
    period = int(p.get("lookback", 10))
    threshold = float(p.get("trigger_pct", 3.0)) / 100
    signals = [0] * len(closes)
    for i in range(period, len(closes)):
        change = (closes[i] - closes[i - period]) / closes[i - period]
        prev_change = (closes[i-1] - closes[i - period - 1]) / closes[i - period - 1] if i > period else 0
        if prev_change <= threshold and change > threshold:
            signals[i] = 1
        elif change < 0 and prev_change >= 0:
            signals[i] = -1
    return signals

def _sig_volatility_breakout(ohlcv, p):
    closes = _closes(ohlcv)
    atr_vals = _atr(ohlcv, int(p.get("atr_period", 14)))
    mult = float(p.get("atr_multiplier", 1.5))
    period = int(p.get("lookback", 20))
    signals = [0] * len(closes)
    for i in range(period, len(closes)):
        if atr_vals[i] is None:
            continue
        high = max(_highs(ohlcv)[i - period : i])
        low  = min(_lows(ohlcv)[i - period : i])
        if closes[i] > high + mult * atr_vals[i] and signals[i-1] != 1:
            signals[i] = 1
        elif closes[i] < low - mult * atr_vals[i]:
            signals[i] = -1
    return signals

def _sig_adx_filter(ohlcv, p):
    """ADX filter with MACD direction."""
    closes = _closes(ohlcv)
    atr_vals = _atr(ohlcv, 14)
    adx_threshold = float(p.get("adx_threshold", 25))
    period = int(p.get("adx_period", 14))
    ml, sl, _ = _macd(closes)
    # Simplified ADX: price range over period normalised by ATR
    signals = [0] * len(closes)
    for i in range(period * 2, len(closes)):
        if atr_vals[i] is None or atr_vals[i] == 0:
            continue
        price_range = max(closes[i - period : i]) - min(closes[i - period : i])
        adx_approx = min(100, price_range / (atr_vals[i] * period) * 100)
        if adx_approx < adx_threshold:
            continue
        if ml[i] is not None and sl[i] is not None and ml[i-1] is not None and sl[i-1] is not None:
            if ml[i-1] < sl[i-1] and ml[i] >= sl[i]:
                signals[i] = 1
            elif ml[i-1] > sl[i-1] and ml[i] <= sl[i]:
                signals[i] = -1
    return signals

def _sig_step_gain(ohlcv, p):
    closes = _closes(ohlcv)
    period = int(p.get("dip_period", 10))
    step_pct = float(p.get("step_gain_pct", 2.0)) / 100
    signals = [0] * len(closes)
    entry = None
    for i in range(period, len(closes)):
        recent_low = min(closes[i - period : i])
        if entry is None and closes[i] <= recent_low * 1.005:
            signals[i] = 1
            entry = closes[i]
        elif entry is not None and closes[i] >= entry * (1 + step_pct):
            signals[i] = -1
            entry = None
    return signals

def _sig_mean_reversion(ohlcv, p):
    closes = _closes(ohlcv)
    period = int(p.get("period", 20))
    dev = float(p.get("std_dev", 2.0))
    upper, mid, lower = _bollinger(closes, period, dev)
    signals = [0] * len(closes)
    for i in range(1, len(closes)):
        if lower[i] is None or upper[i] is None or mid[i] is None:
            continue
        if lower[i-1] is None or upper[i-1] is None or mid[i-1] is None:
            continue
        if closes[i-1] > lower[i-1] and closes[i] <= lower[i]:
            signals[i] = 1
        elif closes[i] >= mid[i]:
            signals[i] = -1
    return signals

def _sig_grid_trading(ohlcv, p):
    closes = _closes(ohlcv)
    grid_pct = float(p.get("grid_pct", 2.0)) / 100
    levels = int(p.get("grid_levels", 5))
    signals = [0] * len(closes)
    if not closes:
        return signals
    base = closes[0]
    buy_levels = [base * (1 - (k + 1) * grid_pct) for k in range(levels)]
    sell_levels = [base * (1 + (k + 1) * grid_pct) for k in range(levels)]
    bought = [False] * levels
    for i in range(1, len(closes)):
        p_cur = closes[i]
        for k in range(levels):
            if not bought[k] and p_cur <= buy_levels[k]:
                signals[i] = 1
                bought[k] = True
                break
        for k in range(levels):
            if bought[k] and p_cur >= sell_levels[k]:
                signals[i] = -1
                bought[k] = False
                break
    return signals

def _sig_bollinger_bands(ohlcv, p):
    closes = _closes(ohlcv)
    upper, _, lower = _bollinger(closes, int(p.get("period", 20)), float(p.get("std_dev", 2.0)))
    signals = [0] * len(closes)
    for i in range(1, len(closes)):
        if lower[i] is None or upper[i] is None:
            continue
        if lower[i-1] is None or upper[i-1] is None:
            continue
        if closes[i-1] > lower[i-1] and closes[i] <= lower[i]:
            signals[i] = 1
        elif closes[i-1] < upper[i-1] and closes[i] >= upper[i]:
            signals[i] = -1
    return signals

def _sig_dca(ohlcv, p):
    closes = _closes(ohlcv)
    interval = int(p.get("interval_candles", 7))
    target_pct = float(p.get("sell_target_pct", 10.0)) / 100
    signals = [0] * len(closes)
    entry = None
    for i in range(len(closes)):
        if i % interval == 0:
            signals[i] = 1
            entry = closes[i] if entry is None else entry
        if entry and closes[i] >= entry * (1 + target_pct):
            signals[i] = -1
            entry = None
    return signals

def _sig_grid_dca_hybrid(ohlcv, p):
    closes = _closes(ohlcv)
    interval = int(p.get("interval_candles", 14))
    grid_pct = float(p.get("grid_pct", 3.0)) / 100
    sell_pct = float(p.get("sell_pct", 5.0)) / 100
    signals = [0] * len(closes)
    entry = None
    for i in range(1, len(closes)):
        is_interval = (i % interval == 0)
        big_dip = entry is not None and closes[i] <= closes[i-1] * (1 - grid_pct)
        if is_interval or big_dip:
            signals[i] = 1
            entry = closes[i] if entry is None else (entry + closes[i]) / 2
        elif entry and closes[i] >= entry * (1 + sell_pct):
            signals[i] = -1
            entry = None
    return signals

def _sig_regime_switching(ohlcv, p):
    closes = _closes(ohlcv)
    vol_period = int(p.get("vol_period", 20))
    vol_threshold = float(p.get("vol_threshold", 2.0)) / 100
    std_vals = _std(closes, vol_period)
    mr_upper, _, mr_lower = _bollinger(closes, vol_period, 2.0)
    sma_s = _sma(closes, 10)
    sma_l = _sma(closes, 30)
    signals = [0] * len(closes)
    for i in range(1, len(closes)):
        if std_vals[i] is None or mr_lower[i] is None or sma_s[i] is None or sma_l[i] is None:
            continue
        vol = std_vals[i] / closes[i]
        if vol > vol_threshold:  # high vol → mean reversion
            if closes[i] <= mr_lower[i]:
                signals[i] = 1
            elif closes[i-1] < (mr_upper[i-1] or closes[i]) and closes[i] >= mr_upper[i]:
                signals[i] = -1
        else:  # low vol → trend following
            if sma_s[i-1] is not None and sma_l[i-1] is not None:
                if sma_s[i-1] < sma_l[i-1] and sma_s[i] >= sma_l[i]:
                    signals[i] = 1
                elif sma_s[i] < sma_l[i]:
                    signals[i] = -1
    return signals

def _sig_pair_trading(ohlcv, p):
    """Simulate pair trading via Z-score mean reversion on price ratio to SMA."""
    closes = _closes(ohlcv)
    period = int(p.get("period", 30))
    z_entry = float(p.get("z_entry", 2.0))
    z_exit = float(p.get("z_exit", 0.5))
    std_vals = _std(closes, period)
    sma_vals = _sma(closes, period)
    signals = [0] * len(closes)
    for i in range(period, len(closes)):
        if std_vals[i] is None or sma_vals[i] is None or std_vals[i] == 0:
            continue
        z = (closes[i] - sma_vals[i]) / std_vals[i]
        if z <= -z_entry:
            signals[i] = 1
        elif z >= z_entry:
            signals[i] = -1
        elif abs(z) <= z_exit and i > 0 and signals[i-1] in (1, -1):
            signals[i] = -signals[i-1]
    return signals

def _sig_portfolio_rebalancing(ohlcv, p):
    closes = _closes(ohlcv)
    rebal_period = int(p.get("rebalance_period", 30))
    drift_threshold = float(p.get("drift_threshold_pct", 5.0)) / 100
    target_weight = float(p.get("target_weight_pct", 50.0)) / 100
    signals = [0] * len(closes)
    entry_price = closes[0] if closes else 0
    for i in range(1, len(closes)):
        drift = abs(closes[i] - entry_price) / entry_price if entry_price > 0 else 0
        rebal = (i % rebal_period == 0) or drift > drift_threshold
        if rebal:
            if closes[i] < entry_price:
                signals[i] = 1
            else:
                signals[i] = -1
            entry_price = closes[i]
    return signals

def _sig_tsa(ohlcv, p):
    """Time Series Analysis: linear regression channel entry."""
    closes = _closes(ohlcv)
    period = int(p.get("period", 20))
    dev_entry = float(p.get("dev_threshold_pct", 2.0)) / 100
    reg = _linear_regression(closes, period)
    std_vals = _std(closes, period)
    signals = [0] * len(closes)
    for i in range(period, len(closes)):
        if reg[i] is None or std_vals[i] is None or std_vals[i] == 0 or reg[i] == 0:
            continue
        deviation = (closes[i] - reg[i]) / reg[i]
        if deviation <= -dev_entry:
            signals[i] = 1
        elif deviation >= dev_entry:
            signals[i] = -1
    return signals

def _sig_tssl(ohlcv, p):
    """Trailing Stop-Loss Ladder."""
    closes = _closes(ohlcv)
    rsi = _rsi(closes, 14)
    trail_pct = float(p.get("trail_pct", 3.0)) / 100
    oversold = float(p.get("oversold", 35))
    signals = [0] * len(closes)
    in_pos = False
    high_water = 0.0
    for i in range(1, len(closes)):
        if rsi[i] is None:
            continue
        if not in_pos and rsi[i] < oversold:
            signals[i] = 1
            in_pos = True
            high_water = closes[i]
        elif in_pos:
            if closes[i] > high_water:
                high_water = closes[i]
            if closes[i] <= high_water * (1 - trail_pct):
                signals[i] = -1
                in_pos = False
    return signals

def _sig_arbitrage(ohlcv, p):
    """Simulate arbitrage as spread between price and VWAP approximation."""
    closes = _closes(ohlcv)
    period = int(p.get("period", 10))
    spread_pct = float(p.get("min_spread_pct", 0.5)) / 100
    sma_vals = _sma(closes, period)
    signals = [0] * len(closes)
    for i in range(period, len(closes)):
        if sma_vals[i] is None:
            continue
        deviation = (closes[i] - sma_vals[i]) / sma_vals[i]
        if deviation <= -spread_pct:
            signals[i] = 1
        elif deviation >= spread_pct:
            signals[i] = -1
    return signals

def _sig_market_making(ohlcv, p):
    """Simulate market making: buy on micro-dips, sell on micro-bounces."""
    closes = _closes(ohlcv)
    spread_pct = float(p.get("spread_pct", 0.3)) / 100
    period = int(p.get("period", 5))
    signals = [0] * len(closes)
    for i in range(period, len(closes)):
        mid = sum(closes[i - period : i]) / period
        if closes[i] <= mid * (1 - spread_pct / 2):
            signals[i] = 1
        elif closes[i] >= mid * (1 + spread_pct / 2):
            signals[i] = -1
    return signals

def _sig_scalping(ohlcv, p):
    closes = _closes(ohlcv)
    rsi = _rsi(closes, int(p.get("rsi_period", 7)))
    target_pct = float(p.get("target_pct", 0.5)) / 100
    oversold = float(p.get("oversold", 40))
    signals = [0] * len(closes)
    entry = None
    for i in range(1, len(closes)):
        if rsi[i] is None:
            continue
        if entry is None and rsi[i] < oversold:
            signals[i] = 1
            entry = closes[i]
        elif entry is not None:
            if closes[i] >= entry * (1 + target_pct):
                signals[i] = -1
                entry = None
    return signals

def _sig_gain(ohlcv, p):
    closes = _closes(ohlcv)
    rsi = _rsi(closes, 14)
    gain_pct = float(p.get("gain_pct", 3.0)) / 100
    oversold = float(p.get("oversold", 35))
    signals = [0] * len(closes)
    entry = None
    for i in range(1, len(closes)):
        if rsi[i] is None:
            continue
        if entry is None and rsi[i] < oversold:
            signals[i] = 1
            entry = closes[i]
        elif entry is not None and closes[i] >= entry * (1 + gain_pct):
            signals[i] = -1
            entry = None
    return signals

def _sig_emotionless(ohlcv, p):
    """RSI oversold + MACD bullish crossover simultaneously required."""
    closes = _closes(ohlcv)
    rsi = _rsi(closes, int(p.get("rsi_period", 14)))
    ml, sl, _ = _macd(closes, int(p.get("fast", 12)), int(p.get("slow", 26)), int(p.get("signal", 9)))
    oversold = float(p.get("oversold", 30))
    overbought = float(p.get("overbought", 70))
    signals = [0] * len(closes)
    for i in range(1, len(closes)):
        if rsi[i] is None or ml[i] is None or sl[i] is None:
            continue
        if ml[i-1] is None or sl[i-1] is None or rsi[i-1] is None:
            continue
        macd_cross_up = ml[i-1] < sl[i-1] and ml[i] >= sl[i]
        macd_cross_dn = ml[i-1] > sl[i-1] and ml[i] <= sl[i]
        if rsi[i] < oversold and macd_cross_up:
            signals[i] = 1
        elif rsi[i] > overbought and macd_cross_dn:
            signals[i] = -1
    return signals


# ===========================================================================
# Strategy Registry — 25 strategies in 5 packs
# ===========================================================================

STRATEGIES: dict[str, dict[str, dict]] = {
    "Core Signals": {
        "RSI": {
            "func": _sig_rsi,
            "description": "Buys when RSI crosses above oversold level, sells when it crosses below overbought.",
            "params": [
                {"name": "rsi_period", "label": "RSI Period", "type": "int", "default": 14, "min": 2, "max": 50},
                {"name": "oversold",   "label": "Oversold Level", "type": "float", "default": 30, "min": 10, "max": 49},
                {"name": "overbought", "label": "Overbought Level", "type": "float", "default": 70, "min": 51, "max": 90},
            ],
        },
        "MACD": {
            "func": _sig_macd,
            "description": "Buys on MACD line / signal bullish crossover; sells on bearish crossover.",
            "params": [
                {"name": "fast",   "label": "Fast EMA",    "type": "int", "default": 12, "min": 2,  "max": 50},
                {"name": "slow",   "label": "Slow EMA",    "type": "int", "default": 26, "min": 5,  "max": 100},
                {"name": "signal", "label": "Signal Period","type": "int", "default": 9,  "min": 2,  "max": 30},
            ],
        },
        "EMA Spread": {
            "func": _sig_ema_spread,
            "description": "Trades when the fast EMA spreads above/below the slow EMA by a set threshold.",
            "params": [
                {"name": "fast_period",  "label": "Fast EMA Period",  "type": "int",   "default": 12,  "min": 2, "max": 50},
                {"name": "slow_period",  "label": "Slow EMA Period",  "type": "int",   "default": 26,  "min": 5, "max": 100},
                {"name": "spread_pct",   "label": "Spread Threshold %","type": "float", "default": 0.5, "min": 0.1, "max": 5.0},
            ],
        },
        "MACD Histogram": {
            "func": _sig_macd_histogram,
            "description": "Buys when histogram turns positive (zero-line cross up); sells when turns negative.",
            "params": [
                {"name": "fast",   "label": "Fast EMA",     "type": "int", "default": 12, "min": 2, "max": 50},
                {"name": "slow",   "label": "Slow EMA",     "type": "int", "default": 26, "min": 5, "max": 100},
                {"name": "signal", "label": "Signal Period", "type": "int", "default": 9,  "min": 2, "max": 30},
            ],
        },
        "SMA Cross": {
            "func": _sig_sma_cross,
            "description": "Golden/death cross: buys when short SMA crosses above long SMA.",
            "params": [
                {"name": "short_period", "label": "Short SMA Period", "type": "int", "default": 10, "min": 2,  "max": 50},
                {"name": "long_period",  "label": "Long SMA Period",  "type": "int", "default": 50, "min": 10, "max": 200},
            ],
        },
    },
    "Trend & Momentum": {
        "Trend Following": {
            "func": _sig_trend_following,
            "description": "Multi-confirmation trend entry: SMA crossover + RSI below overbought.",
            "params": [
                {"name": "short_period", "label": "Short SMA", "type": "int",   "default": 20,  "min": 5,  "max": 50},
                {"name": "long_period",  "label": "Long SMA",  "type": "int",   "default": 50,  "min": 20, "max": 200},
                {"name": "rsi_max",      "label": "RSI Max",   "type": "float", "default": 65.0,"min": 50, "max": 80},
            ],
        },
        "Momentum Trading": {
            "func": _sig_momentum,
            "description": "Buys explosive price surges above a % trigger; sells when momentum reverses.",
            "params": [
                {"name": "lookback",     "label": "Lookback Periods", "type": "int",   "default": 10,  "min": 3, "max": 50},
                {"name": "trigger_pct",  "label": "Trigger %",        "type": "float", "default": 3.0, "min": 0.5, "max": 20.0},
            ],
        },
        "Volatility Breakout": {
            "func": _sig_volatility_breakout,
            "description": "Enters when price breaks out of recent range by N × ATR.",
            "params": [
                {"name": "atr_period",     "label": "ATR Period",     "type": "int",   "default": 14,  "min": 5, "max": 50},
                {"name": "atr_multiplier", "label": "ATR Multiplier", "type": "float", "default": 1.5, "min": 0.5, "max": 5.0},
                {"name": "lookback",       "label": "Lookback",       "type": "int",   "default": 20,  "min": 5, "max": 60},
            ],
        },
        "ADX Filter": {
            "func": _sig_adx_filter,
            "description": "Only trades when ADX confirms strong trend; uses MACD for direction.",
            "params": [
                {"name": "adx_period",    "label": "ADX Period",    "type": "int",   "default": 14,   "min": 5, "max": 50},
                {"name": "adx_threshold", "label": "ADX Threshold", "type": "float", "default": 25.0, "min": 10, "max": 50},
            ],
        },
        "Step Gain": {
            "func": _sig_step_gain,
            "description": "Buys at short-term dips; sells once a fixed gain target is reached.",
            "params": [
                {"name": "dip_period",    "label": "Dip Lookback", "type": "int",   "default": 10,  "min": 3, "max": 30},
                {"name": "step_gain_pct", "label": "Gain Target %","type": "float", "default": 2.0, "min": 0.5, "max": 20.0},
            ],
        },
    },
    "Reversion & Grid": {
        "Mean Reversion": {
            "func": _sig_mean_reversion,
            "description": "Buys when price falls below lower Bollinger Band; sells at the midline.",
            "params": [
                {"name": "period",  "label": "BB Period",  "type": "int",   "default": 20,  "min": 5, "max": 100},
                {"name": "std_dev", "label": "Std Dev",    "type": "float", "default": 2.0, "min": 0.5, "max": 4.0},
            ],
        },
        "Grid Trading": {
            "func": _sig_grid_trading,
            "description": "Sets automated buy/sell levels across a price grid; profits from range-bound markets.",
            "params": [
                {"name": "grid_pct",    "label": "Grid Spacing %", "type": "float", "default": 2.0, "min": 0.5, "max": 10.0},
                {"name": "grid_levels", "label": "Grid Levels",    "type": "int",   "default": 5,   "min": 2, "max": 20},
            ],
        },
        "Bollinger Bands": {
            "func": _sig_bollinger_bands,
            "description": "Classic Bollinger Band strategy: buy at lower band, sell at upper band.",
            "params": [
                {"name": "period",  "label": "Period",  "type": "int",   "default": 20,  "min": 5, "max": 100},
                {"name": "std_dev", "label": "Std Dev", "type": "float", "default": 2.0, "min": 0.5, "max": 4.0},
            ],
        },
        "DCA": {
            "func": _sig_dca,
            "description": "Buys at fixed intervals regardless of price; sells on reaching a gain target.",
            "params": [
                {"name": "interval_candles", "label": "Buy Every N Candles", "type": "int",   "default": 7,    "min": 1, "max": 30},
                {"name": "sell_target_pct",  "label": "Sell Target %",       "type": "float", "default": 10.0, "min": 1.0, "max": 50.0},
            ],
        },
        "Grid-DCA Hybrid": {
            "func": _sig_grid_dca_hybrid,
            "description": "Combines regular interval DCA buys with extra grid buys on large dips.",
            "params": [
                {"name": "interval_candles", "label": "Regular Interval", "type": "int",   "default": 14,  "min": 3, "max": 60},
                {"name": "grid_pct",         "label": "Extra Dip %",      "type": "float", "default": 3.0, "min": 0.5, "max": 10.0},
                {"name": "sell_pct",         "label": "Sell Target %",    "type": "float", "default": 5.0, "min": 1.0, "max": 30.0},
            ],
        },
    },
    "Quant Portfolio": {
        "Regime Switching": {
            "func": _sig_regime_switching,
            "description": "Auto-switches between mean reversion (high vol) and trend following (low vol).",
            "params": [
                {"name": "vol_period",    "label": "Vol Period",     "type": "int",   "default": 20,  "min": 5, "max": 60},
                {"name": "vol_threshold", "label": "Vol Threshold %","type": "float", "default": 2.0, "min": 0.5, "max": 10.0},
            ],
        },
        "Pair Trading": {
            "func": _sig_pair_trading,
            "description": "Z-score mean reversion on price deviation from rolling mean (relative value strategy).",
            "params": [
                {"name": "period",  "label": "Lookback Period", "type": "int",   "default": 30,  "min": 10, "max": 90},
                {"name": "z_entry", "label": "Z-Score Entry",   "type": "float", "default": 2.0, "min": 0.5, "max": 4.0},
                {"name": "z_exit",  "label": "Z-Score Exit",    "type": "float", "default": 0.5, "min": 0.0, "max": 2.0},
            ],
        },
        "Portfolio Rebalancing": {
            "func": _sig_portfolio_rebalancing,
            "description": "Periodically rebalances position; buys on drift below target, sells above.",
            "params": [
                {"name": "rebalance_period",    "label": "Rebalance Every N Candles", "type": "int",   "default": 30,  "min": 5, "max": 180},
                {"name": "drift_threshold_pct", "label": "Drift Threshold %",         "type": "float", "default": 5.0, "min": 1.0, "max": 20.0},
                {"name": "target_weight_pct",   "label": "Target Weight %",           "type": "float", "default": 50.0,"min": 10, "max": 90},
            ],
        },
        "TSA": {
            "func": _sig_tsa,
            "description": "Linear regression trend channel: buys when price deviates below regression line.",
            "params": [
                {"name": "period",             "label": "Regression Period",  "type": "int",   "default": 20,  "min": 5, "max": 60},
                {"name": "dev_threshold_pct",  "label": "Deviation Threshold %", "type": "float", "default": 2.0, "min": 0.5, "max": 10.0},
            ],
        },
        "TSSL": {
            "func": _sig_tssl,
            "description": "Trailing Stop-Loss Ladder: enters on RSI oversold, trails a stop that ratchets up.",
            "params": [
                {"name": "trail_pct", "label": "Trail %",       "type": "float", "default": 3.0, "min": 0.5, "max": 15.0},
                {"name": "oversold",  "label": "RSI Oversold",  "type": "float", "default": 35.0,"min": 10, "max": 50},
            ],
        },
    },
    "Execution Alpha": {
        "Arbitrage": {
            "func": _sig_arbitrage,
            "description": "Simulates cross-venue arbitrage as spread between price and VWAP approximation.",
            "params": [
                {"name": "period",         "label": "VWAP Period",      "type": "int",   "default": 10,  "min": 3, "max": 30},
                {"name": "min_spread_pct", "label": "Min Spread %",     "type": "float", "default": 0.5, "min": 0.1, "max": 3.0},
            ],
        },
        "Market Making": {
            "func": _sig_market_making,
            "description": "Captures the bid-ask spread by buying at the micro-bid and selling at the micro-ask.",
            "params": [
                {"name": "spread_pct", "label": "Spread %",   "type": "float", "default": 0.3, "min": 0.05, "max": 2.0},
                {"name": "period",     "label": "Mid Period", "type": "int",   "default": 5,   "min": 2, "max": 20},
            ],
        },
        "Scalping": {
            "func": _sig_scalping,
            "description": "High-frequency small-gain strategy: enters on RSI dip, exits at a tight profit target.",
            "params": [
                {"name": "rsi_period", "label": "RSI Period",    "type": "int",   "default": 7,   "min": 2, "max": 20},
                {"name": "oversold",   "label": "Oversold",      "type": "float", "default": 40.0,"min": 20, "max": 55},
                {"name": "target_pct", "label": "Profit Target %","type": "float", "default": 0.5, "min": 0.1, "max": 5.0},
            ],
        },
        "Gain Strategy": {
            "func": _sig_gain,
            "description": "Buys on RSI oversold; sells only when a fixed gain percentage is achieved.",
            "params": [
                {"name": "gain_pct",  "label": "Gain Target %", "type": "float", "default": 3.0, "min": 0.5, "max": 30.0},
                {"name": "oversold",  "label": "RSI Oversold",  "type": "float", "default": 35.0,"min": 10, "max": 50},
            ],
        },
        "Emotionless": {
            "func": _sig_emotionless,
            "description": "Pure mechanical: requires BOTH RSI oversold AND MACD bullish crossover simultaneously. No discretion.",
            "params": [
                {"name": "rsi_period", "label": "RSI Period",    "type": "int",   "default": 14,  "min": 2, "max": 30},
                {"name": "fast",       "label": "MACD Fast",     "type": "int",   "default": 12,  "min": 2, "max": 50},
                {"name": "slow",       "label": "MACD Slow",     "type": "int",   "default": 26,  "min": 5, "max": 100},
                {"name": "signal",     "label": "MACD Signal",   "type": "int",   "default": 9,   "min": 2, "max": 30},
                {"name": "oversold",   "label": "Oversold",      "type": "float", "default": 30.0,"min": 10, "max": 45},
                {"name": "overbought", "label": "Overbought",    "type": "float", "default": 70.0,"min": 55, "max": 90},
            ],
        },
    },
}


def get_all_strategy_names() -> list[str]:
    names = []
    for pack in STRATEGIES.values():
        names.extend(pack.keys())
    return names


def get_pack_for_strategy(name: str) -> Optional[str]:
    for pack, strats in STRATEGIES.items():
        if name in strats:
            return pack
    return None


def run_backtest(
    ohlcv: OHLCV,
    pack: str,
    strategy_name: str,
    params: dict,
) -> dict:
    """Run a full backtest. params must include 'capital', 'fee_pct', 'trade_size_pct'."""
    if pack not in STRATEGIES or strategy_name not in STRATEGIES[pack]:
        return {"error": f"Strategy '{strategy_name}' not found"}
    if len(ohlcv) < 30:
        return {"error": "Not enough data (need at least 30 candles)"}

    strat = STRATEGIES[pack][strategy_name]
    try:
        signals = strat["func"](ohlcv, params)
    except Exception as exc:
        return {"error": f"Strategy error: {exc}"}

    return _backtest(ohlcv, signals, params)
