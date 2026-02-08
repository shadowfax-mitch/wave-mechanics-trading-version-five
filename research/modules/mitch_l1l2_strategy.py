#!/usr/bin/env python3
"""
Mitch Price Action System — Layer 1+2 Standalone Backtest

Layer 1: Structure Detection (trend state from swing HH/HL/LH/LL)
Layer 2: Pattern Recognition (second-entry signals + measured moves)

Al Brooks methodology: second entries at trend structure levels.
Key test: does waiting for the 2nd entry actually beat the 1st entry?

Procedural numpy approach (not class-based) — same pattern as matrix_test_wick.py.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional


# ──────────────────────────────────────────────
# Reused indicator functions (from matrix_test_wick.py)
# ──────────────────────────────────────────────

def detect_swings(highs: np.ndarray, lows: np.ndarray, strength: int):
    """Detect swing highs/lows with confirmation delay (no look-ahead bias)."""
    n = len(highs)
    is_swing_high = np.ones(n, dtype=bool)
    is_swing_low = np.ones(n, dtype=bool)

    for s in range(1, strength + 1):
        is_swing_high[s:] &= highs[s:] > highs[:-s]
        is_swing_low[s:] &= lows[s:] < lows[:-s]
        is_swing_high[:-s] &= highs[:-s] > highs[s:]
        is_swing_low[:-s] &= lows[:-s] < lows[s:]

    is_swing_high[:strength] = False
    is_swing_high[-strength:] = False
    is_swing_low[:strength] = False
    is_swing_low[-strength:] = False

    # Shift forward by strength to simulate confirmation delay
    sh = np.zeros(n, dtype=bool)
    sl = np.zeros(n, dtype=bool)
    sh[strength:] = is_swing_high[:-strength]
    sl[strength:] = is_swing_low[:-strength]

    return sh, sl


def compute_swing_prices(highs, lows, swing_high, swing_low, strength):
    """Get the ACTUAL swing price for each confirmed swing."""
    n = len(highs)
    sh_price = np.full(n, np.nan)
    sl_price = np.full(n, np.nan)
    for i in range(strength, n):
        if swing_high[i]:
            sh_price[i] = highs[i - strength]
        if swing_low[i]:
            sl_price[i] = lows[i - strength]
    return sh_price, sl_price


def compute_atr(highs, lows, closes, period=14):
    """ATR via simple rolling mean of true range."""
    n = len(highs)
    tr = np.empty(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i],
                     abs(highs[i] - closes[i - 1]),
                     abs(lows[i] - closes[i - 1]))
    atr = np.full(n, np.nan)
    cumtr = np.cumsum(tr)
    atr[period - 1:] = (cumtr[period - 1:] - np.concatenate([[0], cumtr[:-period]])) / period
    return atr


def compute_ema(closes, period):
    """EMA using standard exponential smoothing."""
    alpha = 2.0 / (period + 1)
    ema = np.empty(len(closes))
    ema[0] = closes[0]
    for i in range(1, len(closes)):
        ema[i] = alpha * closes[i] + (1 - alpha) * ema[i - 1]
    return ema


# ──────────────────────────────────────────────
# Layer 1+2 new functions
# ──────────────────────────────────────────────

DEFAULT_PARAMS = {
    'swing_strength': 2,
    'atr_period': 14,
    'ema_period': 21,
    'use_ema_confirmation': True,
    'track_first_entries': True,
    'slippage': 2.0,
    'commission': 2.0,
    'stop_buffer_atr': 0.5,
    'max_stop_atr': 2.0,
    'target_atr_fallback': 2.0,
    'measured_move_cap_atr': 5.0,
    'max_hold': 30,
    'max_daily_loss': -200,
    'max_consec_losses': 3,
    'rth_start': 8.5,
    'rth_end': 15.0,
    'point_value': 1.0,
}


def precompute_indicators(df, params=None):
    """Precompute all indicators from raw OHLCV dataframe.

    Returns dict of numpy arrays keyed by name.
    """
    if params is None:
        params = DEFAULT_PARAMS

    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    opens = df['open'].values
    n = len(df)

    data = {
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'n': n,
    }

    # Time metadata
    ts = df.index
    data['hour'] = np.array([t.hour for t in ts])
    data['minute'] = np.array([t.minute for t in ts])
    data['date'] = np.array([t.date() for t in ts])
    data['time_f'] = data['hour'] + data['minute'] / 60.0

    # Swings
    strength = params['swing_strength']
    sh, sl = detect_swings(highs, lows, strength)
    data['swing_high'] = sh
    data['swing_low'] = sl

    sh_price, sl_price = compute_swing_prices(highs, lows, sh, sl, strength)
    data['swing_high_price'] = sh_price
    data['swing_low_price'] = sl_price

    # ATR
    data['atr'] = compute_atr(highs, lows, closes, params['atr_period'])

    # EMA
    data['ema'] = compute_ema(closes, params['ema_period'])

    return data


# Trend states
TREND_UNKNOWN = 0
TREND_UP = 1
TREND_DOWN = -1
TREND_RANGE = 2


def detect_trend_and_entries(data, params=None):
    """Core state machine: detect trend from swing structure + entry signals.

    Single forward pass maintaining:
    - Last 2 swing high prices + last 2 swing low prices → HH/HL/LH/LL
    - Trend state: UP (HH+HL), DOWN (LH+LL), RANGE (mixed), UNKNOWN
    - Pullback counters → 1st and 2nd entry signals
    - Measured move targets

    Returns dict of per-bar arrays:
      trend, signal, entry_type, stop_level, target_level
    """
    if params is None:
        params = DEFAULT_PARAMS

    n = data['n']
    swing_high = data['swing_high']
    swing_low = data['swing_low']
    sh_price = data['swing_high_price']
    sl_price = data['swing_low_price']
    close = data['close']
    ema = data['ema']

    use_ema = params['use_ema_confirmation']
    track_first = params['track_first_entries']

    # Output arrays
    trend = np.full(n, TREND_UNKNOWN, dtype=np.int8)
    signal = np.zeros(n, dtype=np.int8)       # 1=LONG, -1=SHORT
    entry_type = np.zeros(n, dtype=np.int8)   # 1=first entry, 2=second entry
    stop_level = np.full(n, np.nan)
    target_level = np.full(n, np.nan)

    # State: last 2 swing highs and lows (price, newest first)
    prev_sh = [np.nan, np.nan]  # [most recent, prior]
    prev_sl = [np.nan, np.nan]

    # Pullback counters
    # After a new HH in uptrend, count subsequent swing lows → pullbacks
    # After a new LL in downtrend, count subsequent swing highs → pullbacks
    long_pullback_count = 0
    short_pullback_count = 0

    # Reference prices for measured move
    long_trigger_high = np.nan   # the HH that started the long count
    long_ref_low = np.nan        # the HL before the HH (leg1 start)
    short_trigger_low = np.nan   # the LL that started the short count
    short_ref_high = np.nan      # the LH before the LL (leg1 start)

    current_trend = TREND_UNKNOWN

    for i in range(n):
        # ── Update swing history ──
        new_sh = swing_high[i] and not np.isnan(sh_price[i])
        new_sl = swing_low[i] and not np.isnan(sl_price[i])

        if new_sh:
            prev_sh[1] = prev_sh[0]
            prev_sh[0] = sh_price[i]

        if new_sl:
            prev_sl[1] = prev_sl[0]
            prev_sl[0] = sl_price[i]

        # ── Classify trend ──
        # Need at least 2 of each to classify
        if np.isnan(prev_sh[1]) or np.isnan(prev_sl[1]):
            current_trend = TREND_UNKNOWN
        else:
            hh = prev_sh[0] > prev_sh[1]   # higher high
            hl = prev_sl[0] > prev_sl[1]   # higher low
            lh = prev_sh[0] < prev_sh[1]   # lower high
            ll = prev_sl[0] < prev_sl[1]   # lower low

            if hh and hl:
                current_trend = TREND_UP
            elif lh and ll:
                current_trend = TREND_DOWN
            else:
                current_trend = TREND_RANGE

        # Optional EMA confirmation: demote trend to RANGE if close is against EMA
        if use_ema and current_trend != TREND_UNKNOWN and not np.isnan(ema[i]):
            if current_trend == TREND_UP and close[i] < ema[i]:
                current_trend = TREND_RANGE
            elif current_trend == TREND_DOWN and close[i] > ema[i]:
                current_trend = TREND_RANGE

        trend[i] = current_trend

        # ── Pullback counting + signal generation ──

        # LONG side: in uptrend, after a new HH, count swing lows as pullbacks
        if current_trend == TREND_UP:
            if new_sh and prev_sh[0] > prev_sh[1]:
                # New higher high → reset long pullback counter
                long_pullback_count = 0
                long_trigger_high = prev_sh[0]
                long_ref_low = prev_sl[0] if not np.isnan(prev_sl[0]) else np.nan

            if new_sl and long_pullback_count >= 0:
                long_pullback_count += 1

                if long_pullback_count == 1 and track_first:
                    # First entry long
                    signal[i] = 1
                    entry_type[i] = 1
                    _set_levels(i, 1, sl_price[i], long_trigger_high, long_ref_low,
                                data, params, stop_level, target_level)

                elif long_pullback_count == 2:
                    # Second entry long (the key signal)
                    signal[i] = 1
                    entry_type[i] = 2
                    _set_levels(i, 1, sl_price[i], long_trigger_high, long_ref_low,
                                data, params, stop_level, target_level)
                    long_pullback_count = -1  # consumed, wait for next HH
        else:
            # Not in uptrend → reset long counter
            long_pullback_count = 0

        # SHORT side: in downtrend, after a new LL, count swing highs as pullbacks
        if current_trend == TREND_DOWN:
            if new_sl and prev_sl[0] < prev_sl[1]:
                # New lower low → reset short pullback counter
                short_pullback_count = 0
                short_trigger_low = prev_sl[0]
                short_ref_high = prev_sh[0] if not np.isnan(prev_sh[0]) else np.nan

            if new_sh and short_pullback_count >= 0:
                short_pullback_count += 1

                if short_pullback_count == 1 and track_first:
                    # First entry short
                    signal[i] = -1
                    entry_type[i] = 1
                    _set_levels(i, -1, sh_price[i], short_trigger_low, short_ref_high,
                                data, params, stop_level, target_level)

                elif short_pullback_count == 2:
                    # Second entry short
                    signal[i] = -1
                    entry_type[i] = 2
                    _set_levels(i, -1, sh_price[i], short_trigger_low, short_ref_high,
                                data, params, stop_level, target_level)
                    short_pullback_count = -1  # consumed
        else:
            short_pullback_count = 0

    return {
        'trend': trend,
        'signal': signal,
        'entry_type': entry_type,
        'stop_level': stop_level,
        'target_level': target_level,
    }


def _set_levels(i, direction, swing_price, trigger_price, ref_price,
                data, params, stop_level, target_level):
    """Set stop and target levels for a signal bar.

    direction: 1 = LONG, -1 = SHORT
    swing_price: the 2nd-entry swing point (stop reference)
    trigger_price: the extreme that started the count (HH for longs, LL for shorts)
    ref_price: the swing before the extreme (leg1 start)
    """
    atr = data['atr'][i]
    if np.isnan(atr) or atr == 0:
        return

    buf = params['stop_buffer_atr']
    max_stop = params['max_stop_atr']
    fallback = params['target_atr_fallback']
    cap = params['measured_move_cap_atr']

    if direction == 1:  # LONG
        # Stop below the swing low + buffer
        raw_stop = swing_price - buf * atr
        # Cap stop distance at max_stop_atr
        # Entry will be next bar open, but use swing price as proxy for distance check
        if swing_price - raw_stop > max_stop * atr:
            raw_stop = swing_price - max_stop * atr
        stop_level[i] = raw_stop

        # Measured move target
        if not np.isnan(trigger_price) and not np.isnan(ref_price):
            leg1 = abs(trigger_price - ref_price)
            target = swing_price + leg1
            # Validate: must be above swing and within cap
            if target > swing_price and (target - swing_price) <= cap * atr:
                target_level[i] = target
            else:
                target_level[i] = swing_price + fallback * atr
        else:
            target_level[i] = swing_price + fallback * atr

    else:  # SHORT
        raw_stop = swing_price + buf * atr
        if raw_stop - swing_price > max_stop * atr:
            raw_stop = swing_price + max_stop * atr
        stop_level[i] = raw_stop

        if not np.isnan(trigger_price) and not np.isnan(ref_price):
            leg1 = abs(ref_price - trigger_price)
            target = swing_price - leg1
            if target < swing_price and (swing_price - target) <= cap * atr:
                target_level[i] = target
            else:
                target_level[i] = swing_price - fallback * atr
        else:
            target_level[i] = swing_price - fallback * atr


def backtest(data, signals, params=None):
    """Run backtest loop over signals.

    Proven pattern: exit → circuit breaker → entry.
    Entry: market order at OPEN of bar after signal (one-bar delay).
    """
    if params is None:
        params = DEFAULT_PARAMS

    n = data['n']
    opn = data['open']
    high = data['high']
    low = data['low']
    close = data['close']
    atr = data['atr']
    time_f = data['time_f']
    dates = data['date']

    sig = signals['signal']
    etype = signals['entry_type']
    stop_lvl = signals['stop_level']
    target_lvl = signals['target_level']

    rth_start = params['rth_start']
    rth_end = params['rth_end']
    max_hold = params['max_hold']
    max_daily_loss = params['max_daily_loss']
    max_consec = params['max_consec_losses']
    slippage = params['slippage']
    commission = params['commission']
    point_value = params['point_value']

    # Position state
    in_position = False
    pos_type = 0
    entry_bar = 0
    entry_price = 0.0
    stop_price = 0.0
    target_price = 0.0
    trade_entry_type = 0
    trade_signal_bar = 0

    # Pending entry (signal fires on bar i, enter on bar i+1)
    has_pending = False
    pending_dir = 0
    pending_stop = 0.0
    pending_target = 0.0
    pending_entry_type = 0
    pending_signal_bar = 0

    # Circuit breaker state
    daily_pnl = 0.0
    consec_losses = 0
    current_date = None

    trades = []

    for i in range(1, n):
        d = dates[i]
        if d != current_date:
            current_date = d
            daily_pnl = 0.0
            consec_losses = 0

        t = time_f[i]

        # ── EXIT LOGIC ──
        if in_position:
            bars_held = i - entry_bar
            exit_price_val = 0.0
            exit_reason = None

            if pos_type == 1:  # LONG
                if low[i] <= stop_price:
                    exit_price_val = stop_price
                    exit_reason = 'STOP'
                elif high[i] >= target_price:
                    exit_price_val = target_price
                    exit_reason = 'TARGET'
            else:  # SHORT
                if high[i] >= stop_price:
                    exit_price_val = stop_price
                    exit_reason = 'STOP'
                elif low[i] <= target_price:
                    exit_price_val = target_price
                    exit_reason = 'TARGET'

            if not exit_reason and bars_held >= max_hold:
                exit_price_val = close[i]
                exit_reason = 'TIME'

            if exit_reason:
                if pos_type == 1:
                    raw_pnl = (exit_price_val - entry_price) * point_value
                else:
                    raw_pnl = (entry_price - exit_price_val) * point_value

                pnl = raw_pnl - commission
                daily_pnl += pnl

                if pnl > 0:
                    consec_losses = 0
                elif pnl < 0:
                    consec_losses += 1
                else:
                    consec_losses = 0

                trades.append({
                    'signal_bar': trade_signal_bar,
                    'entry_bar': entry_bar,
                    'exit_bar': i,
                    'direction': 'LONG' if pos_type == 1 else 'SHORT',
                    'entry_type': trade_entry_type,
                    'entry_price': round(entry_price, 2),
                    'exit_price': round(exit_price_val, 2),
                    'stop': round(stop_price, 2),
                    'target': round(target_price, 2),
                    'pnl': round(pnl, 2),
                    'bars_held': bars_held,
                    'exit_reason': exit_reason,
                    'date': str(d),
                })

                in_position = False
                continue  # don't enter on same bar as exit

        # ── FILL PENDING ENTRY ──
        if has_pending and not in_position:
            # Apply slippage at entry
            if pending_dir == 1:
                fill_price = opn[i] + slippage
            else:
                fill_price = opn[i] - slippage

            in_position = True
            pos_type = pending_dir
            entry_bar = i
            entry_price = fill_price
            stop_price = pending_stop
            target_price = pending_target
            trade_entry_type = pending_entry_type
            trade_signal_bar = pending_signal_bar
            has_pending = False

            # Check same-bar stop/target hit
            exited_same_bar = False
            exit_price_val = 0.0
            exit_reason = None

            if pos_type == 1:
                if low[i] <= stop_price:
                    exit_price_val = stop_price
                    exit_reason = 'STOP'
                    exited_same_bar = True
                elif high[i] >= target_price:
                    exit_price_val = target_price
                    exit_reason = 'TARGET'
                    exited_same_bar = True
            else:
                if high[i] >= stop_price:
                    exit_price_val = stop_price
                    exit_reason = 'STOP'
                    exited_same_bar = True
                elif low[i] <= target_price:
                    exit_price_val = target_price
                    exit_reason = 'TARGET'
                    exited_same_bar = True

            if exited_same_bar:
                if pos_type == 1:
                    raw_pnl = (exit_price_val - entry_price) * point_value
                else:
                    raw_pnl = (entry_price - exit_price_val) * point_value

                pnl = raw_pnl - commission
                daily_pnl += pnl

                if pnl > 0:
                    consec_losses = 0
                elif pnl < 0:
                    consec_losses += 1

                trades.append({
                    'signal_bar': trade_signal_bar,
                    'entry_bar': entry_bar,
                    'exit_bar': i,
                    'direction': 'LONG' if pos_type == 1 else 'SHORT',
                    'entry_type': trade_entry_type,
                    'entry_price': round(entry_price, 2),
                    'exit_price': round(exit_price_val, 2),
                    'stop': round(stop_price, 2),
                    'target': round(target_price, 2),
                    'pnl': round(pnl, 2),
                    'bars_held': 0,
                    'exit_reason': exit_reason,
                    'date': str(d),
                })
                in_position = False

            continue  # don't place new signal on fill bar

        # ── CIRCUIT BREAKERS ──
        if daily_pnl <= max_daily_loss:
            continue
        if consec_losses >= max_consec:
            continue
        if in_position:
            continue

        # ── RTH FILTER ──
        if not (rth_start <= t < rth_end):
            continue

        # ── CHECK FOR SIGNAL ON PREVIOUS BAR (one-bar delay) ──
        prev = i - 1
        if sig[prev] == 0:
            continue

        # ATR must be valid
        a = atr[prev]
        if np.isnan(a) or a == 0:
            continue

        # Stop/target must be set
        if np.isnan(stop_lvl[prev]) or np.isnan(target_lvl[prev]):
            continue

        # Queue pending entry
        has_pending = True
        pending_dir = int(sig[prev])
        pending_stop = stop_lvl[prev]
        pending_target = target_lvl[prev]
        pending_entry_type = int(etype[prev])
        pending_signal_bar = prev

    return trades


def calculate_statistics(trades, years):
    """Calculate comprehensive statistics from trade list."""
    if not trades:
        return {
            'total_trades': 0, 'win_rate': 0, 'profit_factor': 0,
            'total_pnl': 0, 'avg_pnl': 0, 'avg_win': 0, 'avg_loss': 0,
            'sharpe': 0, 'max_drawdown': 0, 'years': years,
            'annual_pnl': 0, 'trades_per_year': 0,
        }

    pnls = np.array([t['pnl'] for t in trades])
    total_trades = len(trades)
    total_pnl = pnls.sum()

    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    n_wins = len(wins)
    n_losses = len(losses)

    win_rate = n_wins / total_trades * 100
    gross_profit = wins.sum() if n_wins > 0 else 0
    gross_loss = abs(losses.sum()) if n_losses > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (999.0 if gross_profit > 0 else 0)

    avg_pnl = pnls.mean()
    avg_win = wins.mean() if n_wins > 0 else 0
    avg_loss = losses.mean() if n_losses > 0 else 0
    std_pnl = pnls.std()
    sharpe = avg_pnl / std_pnl if std_pnl > 0 else 0

    # Max drawdown
    cum = np.cumsum(pnls)
    running_max = np.maximum.accumulate(cum)
    dd = running_max - cum
    max_dd = dd.max() if len(dd) > 0 else 0

    # Bars held
    bars_held = [t['bars_held'] for t in trades]
    avg_bars = np.mean(bars_held) if bars_held else 0

    # Long/short split
    longs = [t for t in trades if t['direction'] == 'LONG']
    shorts = [t for t in trades if t['direction'] == 'SHORT']
    long_pnl = sum(t['pnl'] for t in longs) if longs else 0
    short_pnl = sum(t['pnl'] for t in shorts) if shorts else 0
    long_wr = sum(1 for t in longs if t['pnl'] > 0) / len(longs) * 100 if longs else 0
    short_wr = sum(1 for t in shorts if t['pnl'] > 0) / len(shorts) * 100 if shorts else 0

    # Exit reason breakdown
    exit_reasons = {}
    for t in trades:
        r = t['exit_reason']
        if r not in exit_reasons:
            exit_reasons[r] = {'count': 0, 'pnl': 0}
        exit_reasons[r]['count'] += 1
        exit_reasons[r]['pnl'] += t['pnl']

    # 1st vs 2nd entry split
    first_entries = [t for t in trades if t['entry_type'] == 1]
    second_entries = [t for t in trades if t['entry_type'] == 2]

    def _entry_stats(tlist):
        if not tlist:
            return {'count': 0, 'win_rate': 0, 'avg_pnl': 0, 'total_pnl': 0, 'profit_factor': 0}
        p = np.array([t['pnl'] for t in tlist])
        w = p[p > 0]
        l = p[p < 0]
        gp = w.sum() if len(w) > 0 else 0
        gl = abs(l.sum()) if len(l) > 0 else 0
        return {
            'count': len(tlist),
            'win_rate': round(len(w) / len(tlist) * 100, 2),
            'avg_pnl': round(p.mean(), 2),
            'total_pnl': round(p.sum(), 2),
            'profit_factor': round(gp / gl, 4) if gl > 0 else (999.0 if gp > 0 else 0),
        }

    # Yearly breakdown
    yearly = {}
    for t in trades:
        yr = t['date'][:4]
        if yr not in yearly:
            yearly[yr] = {'count': 0, 'pnl': 0, 'wins': 0}
        yearly[yr]['count'] += 1
        yearly[yr]['pnl'] += t['pnl']
        if t['pnl'] > 0:
            yearly[yr]['wins'] += 1

    for yr in yearly:
        c = yearly[yr]['count']
        yearly[yr]['win_rate'] = round(yearly[yr]['wins'] / c * 100, 2) if c > 0 else 0
        yearly[yr]['pnl'] = round(yearly[yr]['pnl'], 2)

    trading_days = len(set(t['date'] for t in trades))
    trades_per_day = total_trades / trading_days if trading_days > 0 else 0

    return {
        'total_trades': total_trades,
        'win_rate': round(win_rate, 2),
        'profit_factor': round(profit_factor, 4),
        'total_pnl': round(total_pnl, 2),
        'avg_pnl': round(avg_pnl, 2),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'sharpe': round(sharpe, 4),
        'max_drawdown': round(max_dd, 2),
        'years': round(years, 2),
        'annual_pnl': round(total_pnl / years, 2) if years > 0 else 0,
        'trades_per_year': round(total_trades / years, 1) if years > 0 else 0,
        'trades_per_day': round(trades_per_day, 2),
        'avg_bars_held': round(avg_bars, 1),
        'long_trades': len(longs),
        'short_trades': len(shorts),
        'long_pnl': round(long_pnl, 2),
        'short_pnl': round(short_pnl, 2),
        'long_win_rate': round(long_wr, 2),
        'short_win_rate': round(short_wr, 2),
        'exit_reasons': exit_reasons,
        'first_entry': _entry_stats(first_entries),
        'second_entry': _entry_stats(second_entries),
        'yearly': yearly,
        'trading_days': trading_days,
    }


def backtest_trailing(data, signals, params=None):
    """Backtest with structure-based trailing stops.

    Key differences from fixed-stop backtest:
    - Stop trails behind favorable swing points as they form
    - Breakeven move after first favorable swing
    - Optional: keep fixed target, or let trail ride (trail_only mode)
    - Ratchet: stop only moves in favorable direction, never widens

    New params (with defaults):
        'trail_buffer_atr': 0.3    — buffer below/above trailing swing
        'use_breakeven': True      — move stop to entry after first favorable swing
        'trail_only': False        — if True, disable fixed target (let trail exit)
        'keep_target': True        — if True, keep measured move target alongside trail
    """
    if params is None:
        params = DEFAULT_PARAMS

    n = data['n']
    opn = data['open']
    high = data['high']
    low = data['low']
    close = data['close']
    atr = data['atr']
    time_f = data['time_f']
    dates = data['date']
    swing_high = data['swing_high']
    swing_low = data['swing_low']
    sh_price = data['swing_high_price']
    sl_price = data['swing_low_price']

    sig = signals['signal']
    etype = signals['entry_type']
    stop_lvl = signals['stop_level']
    target_lvl = signals['target_level']

    rth_start = params['rth_start']
    rth_end = params['rth_end']
    max_hold = params['max_hold']
    max_daily_loss = params['max_daily_loss']
    max_consec = params['max_consec_losses']
    slippage = params['slippage']
    commission = params['commission']
    point_value = params['point_value']

    trail_buf_atr = params.get('trail_buffer_atr', 0.3)
    use_breakeven = params.get('use_breakeven', True)
    trail_only = params.get('trail_only', False)
    keep_target = params.get('keep_target', True) and not trail_only

    # Position state
    in_position = False
    pos_type = 0
    entry_bar = 0
    entry_price = 0.0
    stop_price = 0.0
    target_price = 0.0
    trade_entry_type = 0
    trade_signal_bar = 0
    initial_stop = 0.0        # original stop for record-keeping
    be_moved = False           # has stop moved to breakeven?
    trail_count = 0            # how many trail adjustments

    # Pending entry
    has_pending = False
    pending_dir = 0
    pending_stop = 0.0
    pending_target = 0.0
    pending_entry_type = 0
    pending_signal_bar = 0

    # Circuit breaker
    daily_pnl = 0.0
    consec_losses = 0
    current_date = None

    trades = []

    for i in range(1, n):
        d = dates[i]
        if d != current_date:
            current_date = d
            daily_pnl = 0.0
            consec_losses = 0

        t = time_f[i]

        # ── TRAILING STOP UPDATE (before exit check) ──
        if in_position:
            a_now = atr[i] if not np.isnan(atr[i]) else atr[i - 1]
            buf = trail_buf_atr * a_now if not np.isnan(a_now) else 0

            if pos_type == 1:  # LONG — trail behind swing lows
                # Check for new swing low that's favorable
                if swing_low[i] and not np.isnan(sl_price[i]):
                    sw_low = sl_price[i]
                    new_stop = sw_low - buf

                    if use_breakeven and not be_moved and sw_low > entry_price:
                        # First favorable swing: move to breakeven
                        stop_price = max(stop_price, entry_price)
                        be_moved = True
                        trail_count += 1

                    if new_stop > stop_price:
                        # Trail tighter
                        stop_price = new_stop
                        trail_count += 1

            else:  # SHORT — trail behind swing highs
                if swing_high[i] and not np.isnan(sh_price[i]):
                    sw_high = sh_price[i]
                    new_stop = sw_high + buf

                    if use_breakeven and not be_moved and sw_high < entry_price:
                        stop_price = min(stop_price, entry_price)
                        be_moved = True
                        trail_count += 1

                    if new_stop < stop_price:
                        stop_price = new_stop
                        trail_count += 1

        # ── EXIT LOGIC ──
        if in_position:
            bars_held = i - entry_bar
            exit_price_val = 0.0
            exit_reason = None

            if pos_type == 1:  # LONG
                if low[i] <= stop_price:
                    exit_price_val = stop_price
                    exit_reason = 'TRAIL_STOP' if trail_count > 0 else 'STOP'
                elif keep_target and high[i] >= target_price:
                    exit_price_val = target_price
                    exit_reason = 'TARGET'
            else:  # SHORT
                if high[i] >= stop_price:
                    exit_price_val = stop_price
                    exit_reason = 'TRAIL_STOP' if trail_count > 0 else 'STOP'
                elif keep_target and low[i] <= target_price:
                    exit_price_val = target_price
                    exit_reason = 'TARGET'

            if not exit_reason and bars_held >= max_hold:
                exit_price_val = close[i]
                exit_reason = 'TIME'

            if exit_reason:
                if pos_type == 1:
                    raw_pnl = (exit_price_val - entry_price) * point_value
                else:
                    raw_pnl = (entry_price - exit_price_val) * point_value

                pnl = raw_pnl - commission
                daily_pnl += pnl

                if pnl > 0:
                    consec_losses = 0
                elif pnl < 0:
                    consec_losses += 1
                else:
                    consec_losses = 0

                trades.append({
                    'signal_bar': trade_signal_bar,
                    'entry_bar': entry_bar,
                    'exit_bar': i,
                    'direction': 'LONG' if pos_type == 1 else 'SHORT',
                    'entry_type': trade_entry_type,
                    'entry_price': round(entry_price, 2),
                    'exit_price': round(exit_price_val, 2),
                    'stop': round(initial_stop, 2),
                    'final_stop': round(stop_price, 2),
                    'target': round(target_price, 2) if keep_target else 0,
                    'pnl': round(pnl, 2),
                    'bars_held': bars_held,
                    'exit_reason': exit_reason,
                    'trail_count': trail_count,
                    'date': str(d),
                })

                in_position = False
                continue

        # ── FILL PENDING ENTRY ──
        if has_pending and not in_position:
            if pending_dir == 1:
                fill_price = opn[i] + slippage
            else:
                fill_price = opn[i] - slippage

            in_position = True
            pos_type = pending_dir
            entry_bar = i
            entry_price = fill_price
            stop_price = pending_stop
            initial_stop = pending_stop
            target_price = pending_target
            trade_entry_type = pending_entry_type
            trade_signal_bar = pending_signal_bar
            has_pending = False
            be_moved = False
            trail_count = 0

            # Same-bar stop/target check
            exited_same_bar = False
            exit_price_val = 0.0
            exit_reason = None

            if pos_type == 1:
                if low[i] <= stop_price:
                    exit_price_val = stop_price
                    exit_reason = 'STOP'
                    exited_same_bar = True
                elif keep_target and high[i] >= target_price:
                    exit_price_val = target_price
                    exit_reason = 'TARGET'
                    exited_same_bar = True
            else:
                if high[i] >= stop_price:
                    exit_price_val = stop_price
                    exit_reason = 'STOP'
                    exited_same_bar = True
                elif keep_target and low[i] <= target_price:
                    exit_price_val = target_price
                    exit_reason = 'TARGET'
                    exited_same_bar = True

            if exited_same_bar:
                if pos_type == 1:
                    raw_pnl = (exit_price_val - entry_price) * point_value
                else:
                    raw_pnl = (entry_price - exit_price_val) * point_value

                pnl = raw_pnl - commission
                daily_pnl += pnl

                if pnl > 0:
                    consec_losses = 0
                elif pnl < 0:
                    consec_losses += 1

                trades.append({
                    'signal_bar': trade_signal_bar,
                    'entry_bar': entry_bar,
                    'exit_bar': i,
                    'direction': 'LONG' if pos_type == 1 else 'SHORT',
                    'entry_type': trade_entry_type,
                    'entry_price': round(entry_price, 2),
                    'exit_price': round(exit_price_val, 2),
                    'stop': round(initial_stop, 2),
                    'final_stop': round(stop_price, 2),
                    'target': round(target_price, 2) if keep_target else 0,
                    'pnl': round(pnl, 2),
                    'bars_held': 0,
                    'exit_reason': exit_reason,
                    'trail_count': 0,
                    'date': str(d),
                })
                in_position = False

            continue

        # ── CIRCUIT BREAKERS ──
        if daily_pnl <= max_daily_loss:
            continue
        if consec_losses >= max_consec:
            continue
        if in_position:
            continue

        # ── RTH FILTER ──
        if not (rth_start <= t < rth_end):
            continue

        # ── CHECK FOR SIGNAL ON PREVIOUS BAR ──
        prev = i - 1
        if sig[prev] == 0:
            continue

        a = atr[prev]
        if np.isnan(a) or a == 0:
            continue

        if np.isnan(stop_lvl[prev]) or np.isnan(target_lvl[prev]):
            continue

        has_pending = True
        pending_dir = int(sig[prev])
        pending_stop = stop_lvl[prev]
        pending_target = target_lvl[prev]
        pending_entry_type = int(etype[prev])
        pending_signal_bar = prev

    return trades


def run_strategy(df, params=None):
    """Full pipeline: precompute → detect signals → backtest → stats."""
    if params is None:
        params = DEFAULT_PARAMS

    data = precompute_indicators(df, params)
    signals = detect_trend_and_entries(data, params)
    trades = backtest(data, signals, params)

    years = (df.index[-1] - df.index[0]).days / 365.25
    stats = calculate_statistics(trades, years)

    return {
        'stats': stats,
        'trades': trades,
        'params': {k: v for k, v in params.items()},
    }


def run_strategy_trailing(df, params=None):
    """Full pipeline with trailing stops."""
    if params is None:
        params = DEFAULT_PARAMS

    data = precompute_indicators(df, params)
    signals = detect_trend_and_entries(data, params)
    trades = backtest_trailing(data, signals, params)

    years = (df.index[-1] - df.index[0]).days / 365.25
    stats = calculate_statistics(trades, years)

    return {
        'stats': stats,
        'trades': trades,
        'params': {k: v for k, v in params.items()},
    }
