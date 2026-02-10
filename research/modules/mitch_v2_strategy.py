#!/usr/bin/env python3
"""
Mitch V2 Strategy — Support/Resistance Price Action System

Key differences from V1:
  - Trades at S/R levels identified from swing point clusters
  - Signal bar quality filter (bar must confirm direction)
  - Stop order entry (buy stop above signal bar high, sell stop below low)
  - Signal bar-based stops (tight, from bar range)
  - Trades in RANGE markets (buy support, sell resistance)
  - Multiple patterns: pullback (two legs), triple test, failure
  - No grid filter — core price action rules only

Goal: ~1 trade per day average on MNQ 5-min
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional

from mitch_l1l2_strategy import (
    detect_swings, compute_swing_prices, compute_atr, compute_ema,
    calculate_statistics,
    TREND_UP, TREND_DOWN, TREND_RANGE, TREND_UNKNOWN,
)

# MNQ minimum tick
MNQ_TICK = 0.25

DEFAULT_V2_PARAMS = {
    # Indicators
    'swing_strength': 2,
    'atr_period': 14,
    'ema_period': 21,

    # S/R detection
    'sr_tolerance_atr': 1.0,     # how close price must be to a level (in ATR)
    'sr_max_levels': 30,         # max recent swing points to track per side
    'sr_cluster_atr': 0.5,       # swings within this distance merge into a zone
    'sr_max_age': 200,           # expire levels older than this many bars

    # Signal bar filter
    'signal_bar_close_pct': 0.40,  # close must be in this % of bar (from favorable end)
    'signal_bar_body_pct': 0.15,   # body must be at least this % of bar range
    'signal_bar_min_atr': 0.15,    # bar range must be >= this * ATR
    'signal_bar_max_atr': 3.0,     # bar range must be <= this * ATR

    # Entry (stop order)
    'order_timeout': 3,          # bars before stop order expires
    'slippage': 1.0,             # slippage per side on stop fills
    'commission': 2.0,           # round-trip commission

    # Stop
    'min_stop_atr': 0.3,        # minimum stop distance (ATR)
    'max_stop_atr': 2.0,        # maximum stop distance (ATR)

    # Exit (trail-only, same as V1)
    'trail_buffer_atr': 0.8,
    'use_breakeven': True,
    'max_hold': 90,

    # Risk
    'max_daily_loss': -200,
    'max_consec_losses': 3,

    # Session
    'rth_start': 8.5,
    'rth_end': 15.0,
    'point_value': 1.0,

    # Pattern minimums
    'min_touches_pullback': 2,   # touches needed for pullback pattern
    'min_touches_triple': 3,     # touches needed for triple test
    'failure_lookback': 10,      # bars to look back for failed breakout

    # Trend trading rules
    'trade_with_trend': True,    # UP=longs only, DOWN=shorts only, RANGE=both
}


# ──────────────────────────────────────────────
# Indicator precomputation
# ──────────────────────────────────────────────

def precompute_indicators(df, params):
    """Compute all indicators from raw OHLCV dataframe."""
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


# ──────────────────────────────────────────────
# S/R Zone tracking
# ──────────────────────────────────────────────

class SRZone:
    """A support or resistance zone defined by clustered swing points."""
    __slots__ = ['price', 'zone_type', 'touches', 'last_bar']

    def __init__(self, price, bar_idx, zone_type):
        self.price = price
        self.zone_type = zone_type  # 'support' or 'resistance'
        self.touches = [(bar_idx, price)]
        self.last_bar = bar_idx

    def add_touch(self, bar_idx, price):
        self.touches.append((bar_idx, price))
        self.price = np.mean([t[1] for t in self.touches])
        self.last_bar = bar_idx

    @property
    def touch_count(self):
        return len(self.touches)


def update_sr_zones(zones, new_price, bar_idx, zone_type, cluster_tol, max_age, max_levels):
    """Add a new swing point to the zone list, merging if close to existing."""
    # Try to merge with existing zone
    for z in zones:
        if z.zone_type == zone_type and abs(z.price - new_price) <= cluster_tol:
            z.add_touch(bar_idx, new_price)
            return zones

    # Create new zone
    zones.append(SRZone(new_price, bar_idx, zone_type))

    # Expire old zones
    zones = [z for z in zones if bar_idx - z.last_bar <= max_age]

    # Cap total zones
    if len(zones) > max_levels:
        zones.sort(key=lambda z: z.last_bar)
        zones = zones[-max_levels:]

    return zones


def find_nearby_zone(zones, price, tolerance, zone_type):
    """Find the closest zone of given type within tolerance. Returns zone or None."""
    best = None
    best_dist = tolerance + 1
    for z in zones:
        if z.zone_type != zone_type:
            continue
        dist = abs(z.price - price)
        if dist <= tolerance and dist < best_dist:
            best = z
            best_dist = dist
    return best


# ──────────────────────────────────────────────
# Signal bar quality
# ──────────────────────────────────────────────

def check_signal_bar(open_p, high, low, close, atr, direction, params):
    """Check if a bar qualifies as a good signal bar.

    Returns True if the bar passes quality filters.
    direction: 1 = looking for bullish bar, -1 = looking for bearish bar
    """
    bar_range = high - low
    if bar_range <= 0:
        return False

    # Range must be meaningful but not extreme
    if np.isnan(atr) or atr <= 0:
        return False
    if bar_range < params['signal_bar_min_atr'] * atr:
        return False
    if bar_range > params['signal_bar_max_atr'] * atr:
        return False

    # Body size check
    body = abs(close - open_p)
    if body / bar_range < params['signal_bar_body_pct']:
        return False

    # Close position + direction check
    close_pct = params['signal_bar_close_pct']
    if direction == 1:  # Bullish: close in upper portion, close > open
        if close <= open_p:
            return False
        if (close - low) / bar_range < (1.0 - close_pct):
            return False
    else:  # Bearish: close in lower portion, close < open
        if close >= open_p:
            return False
        if (high - close) / bar_range < (1.0 - close_pct):
            return False

    return True


# ──────────────────────────────────────────────
# Pattern detection at S/R levels
# ──────────────────────────────────────────────

def detect_pattern_at_support(bar_idx, zone, recent_lows_below, params):
    """Detect what pattern is forming at a support zone.

    Args:
        bar_idx: current bar index
        zone: the SRZone being tested
        recent_lows_below: list of (bar, price) of recent bars that went below this zone
        params: strategy parameters

    Returns:
        pattern string or None: 'PULLBACK', 'TRIPLE_TEST', 'FAILURE'
    """
    tc = zone.touch_count

    # Triple test: 3+ touches of this support zone
    if tc >= params['min_touches_triple']:
        return 'TRIPLE_TEST'

    # Two legs / pullback: 2+ touches
    if tc >= params['min_touches_pullback']:
        return 'PULLBACK'

    # Failure: price recently broke below this zone then came back
    if recent_lows_below:
        for (brk_bar, brk_price) in recent_lows_below:
            if bar_idx - brk_bar <= params['failure_lookback']:
                return 'FAILURE'

    return None


def detect_pattern_at_resistance(bar_idx, zone, recent_highs_above, params):
    """Detect what pattern is forming at a resistance zone. Mirror of support."""
    tc = zone.touch_count

    if tc >= params['min_touches_triple']:
        return 'TRIPLE_TEST'

    if tc >= params['min_touches_pullback']:
        return 'PULLBACK'

    if recent_highs_above:
        for (brk_bar, brk_price) in recent_highs_above:
            if bar_idx - brk_bar <= params['failure_lookback']:
                return 'FAILURE'

    return None


# ──────────────────────────────────────────────
# Main signal generation
# ──────────────────────────────────────────────

def detect_signals_v2(data, params):
    """Generate V2 signals: S/R + pattern + signal bar quality.

    Returns dict with per-bar arrays:
        signal: 1=long, -1=short, 0=none
        signal_type: pattern name string
        entry_price: stop order price
        stop_price: initial stop level
        trend: trend state at each bar
    """
    n = data['n']
    high = data['high']
    low = data['low']
    close = data['close']
    open_p = data['open']
    atr = data['atr']
    ema = data['ema']
    swing_high = data['swing_high']
    swing_low = data['swing_low']
    sh_price = data['swing_high_price']
    sl_price = data['swing_low_price']

    # Output arrays
    signal = np.zeros(n, dtype=np.int8)
    signal_type = [''] * n
    entry_price = np.full(n, np.nan)
    stop_price = np.full(n, np.nan)
    trend = np.full(n, TREND_UNKNOWN, dtype=np.int8)

    # Trend state (HH/HL/LH/LL)
    prev_sh = [np.nan, np.nan]
    prev_sl = [np.nan, np.nan]
    current_trend = TREND_UNKNOWN

    # S/R zones
    sr_zones = []
    cluster_tol_base = params['sr_cluster_atr']
    sr_tol_base = params['sr_tolerance_atr']
    max_age = params['sr_max_age']
    max_levels = params['sr_max_levels']

    # Track recent breakouts for failure detection
    recent_support_breaks = []   # (bar, price) where price broke below support
    recent_resist_breaks = []    # (bar, price) where price broke above resistance

    # Cooldown: after signaling at a zone, require price to leave before re-signaling
    last_signal_zone_price = np.nan
    last_signal_bar = -999

    trade_with_trend = params['trade_with_trend']

    for i in range(1, n):
        a = atr[i]
        if np.isnan(a) or a <= 0:
            trend[i] = current_trend
            continue

        cluster_tol = cluster_tol_base * a
        sr_tol = sr_tol_base * a

        # ── Update swing history + trend ──
        new_sh = swing_high[i] and not np.isnan(sh_price[i])
        new_sl = swing_low[i] and not np.isnan(sl_price[i])

        if new_sh:
            prev_sh[1] = prev_sh[0]
            prev_sh[0] = sh_price[i]
            sr_zones = update_sr_zones(
                sr_zones, sh_price[i], i, 'resistance',
                cluster_tol, max_age, max_levels)

        if new_sl:
            prev_sl[1] = prev_sl[0]
            prev_sl[0] = sl_price[i]
            sr_zones = update_sr_zones(
                sr_zones, sl_price[i], i, 'support',
                cluster_tol, max_age, max_levels)

        # Classify trend
        if np.isnan(prev_sh[1]) or np.isnan(prev_sl[1]):
            current_trend = TREND_UNKNOWN
        else:
            hh = prev_sh[0] > prev_sh[1]
            hl = prev_sl[0] > prev_sl[1]
            lh = prev_sh[0] < prev_sh[1]
            ll = prev_sl[0] < prev_sl[1]

            if hh and hl:
                current_trend = TREND_UP
            elif lh and ll:
                current_trend = TREND_DOWN
            else:
                current_trend = TREND_RANGE

        trend[i] = current_trend

        # ── Track breakouts for failure detection ──
        # Check if current bar breaks through any known support/resistance
        for z in sr_zones:
            if z.zone_type == 'support' and low[i] < z.price - sr_tol:
                recent_support_breaks.append((i, z.price))
            elif z.zone_type == 'resistance' and high[i] > z.price + sr_tol:
                recent_resist_breaks.append((i, z.price))

        # Trim old breakouts
        lookback = params['failure_lookback']
        recent_support_breaks = [(b, p) for b, p in recent_support_breaks
                                  if i - b <= lookback]
        recent_resist_breaks = [(b, p) for b, p in recent_resist_breaks
                                 if i - b <= lookback]

        # ── Signal cooldown check ──
        # Don't re-signal at same zone within 5 bars
        if i - last_signal_bar < 5:
            continue

        # ── Check for LONG signal (price near support) ──
        can_long = (not trade_with_trend or
                    current_trend in (TREND_UP, TREND_RANGE))
        if can_long:
            support_zone = find_nearby_zone(sr_zones, low[i], sr_tol, 'support')
            if support_zone is not None:
                pattern = detect_pattern_at_support(
                    i, support_zone, recent_support_breaks, params)
                if pattern is not None:
                    if check_signal_bar(open_p[i], high[i], low[i], close[i],
                                        a, 1, params):
                        # Compute entry and stop
                        entry_p = high[i] + MNQ_TICK
                        stop_p = low[i] - MNQ_TICK

                        # Enforce stop distance limits
                        stop_dist = entry_p - stop_p
                        if stop_dist < params['min_stop_atr'] * a:
                            stop_p = entry_p - params['min_stop_atr'] * a
                        if stop_dist > params['max_stop_atr'] * a:
                            pass  # skip — too wide
                        else:
                            signal[i] = 1
                            signal_type[i] = pattern
                            entry_price[i] = entry_p
                            stop_price[i] = stop_p
                            last_signal_zone_price = support_zone.price
                            last_signal_bar = i
                            continue  # don't check short on same bar

        # ── Check for SHORT signal (price near resistance) ──
        can_short = (not trade_with_trend or
                     current_trend in (TREND_DOWN, TREND_RANGE))
        if can_short and signal[i] == 0:
            resist_zone = find_nearby_zone(sr_zones, high[i], sr_tol, 'resistance')
            if resist_zone is not None:
                pattern = detect_pattern_at_resistance(
                    i, resist_zone, recent_resist_breaks, params)
                if pattern is not None:
                    if check_signal_bar(open_p[i], high[i], low[i], close[i],
                                        a, -1, params):
                        entry_p = low[i] - MNQ_TICK
                        stop_p = high[i] + MNQ_TICK

                        stop_dist = stop_p - entry_p
                        if stop_dist < params['min_stop_atr'] * a:
                            stop_p = entry_p + params['min_stop_atr'] * a
                        if stop_dist > params['max_stop_atr'] * a:
                            pass
                        else:
                            signal[i] = -1
                            signal_type[i] = pattern
                            entry_price[i] = entry_p
                            stop_price[i] = stop_p
                            last_signal_zone_price = resist_zone.price
                            last_signal_bar = i

    return {
        'signal': signal,
        'signal_type': signal_type,
        'entry_price': entry_price,
        'stop_price': stop_price,
        'trend': trend,
    }


# ──────────────────────────────────────────────
# Backtest with stop order entry + trail exit
# ──────────────────────────────────────────────

def backtest_v2(data, signals, params):
    """Backtest V2 signals with stop-order entry and trail-only exit.

    Entry: stop order at signal bar high+tick (long) or low-tick (short).
    Fill: if next bar's wick reaches stop order price.
    Stop: signal bar low-tick (long) or high+tick (short).
    Exit: trail-only with breakeven + time exit.
    """
    n = data['n']
    high = data['high']
    low = data['low']
    close = data['close']
    open_p = data['open']
    atr = data['atr']
    time_f = data['time_f']
    dates = data['date']
    swing_high = data['swing_high']
    swing_low = data['swing_low']
    sh_price = data['swing_high_price']
    sl_price = data['swing_low_price']

    sig = signals['signal']
    sig_type = signals['signal_type']
    sig_entry = signals['entry_price']
    sig_stop = signals['stop_price']
    sig_trend = signals['trend']

    rth_start = params['rth_start']
    rth_end = params['rth_end']
    max_hold = params['max_hold']
    max_daily_loss = params['max_daily_loss']
    max_consec = params['max_consec_losses']
    slippage = params['slippage']
    commission = params['commission']
    point_value = params['point_value']
    trail_buf_atr = params['trail_buffer_atr']
    use_breakeven = params['use_breakeven']
    order_timeout = params['order_timeout']

    # Position state
    in_position = False
    pos_type = 0
    entry_bar = 0
    entry_price = 0.0
    stop_price_pos = 0.0
    initial_stop = 0.0
    be_moved = False
    trail_count = 0
    trade_signal_bar = 0
    trade_pattern = ''
    trade_trend = 0

    # Pending stop order
    has_pending = False
    pending_dir = 0
    pending_entry_price = 0.0
    pending_stop_price = 0.0
    pending_signal_bar = 0
    pending_placed_bar = 0
    pending_pattern = ''
    pending_trend = 0

    # Circuit breaker
    daily_pnl = 0.0
    consec_losses = 0
    current_date = None

    trades = []
    total_signals = 0
    total_fills = 0

    for i in range(1, n):
        d = dates[i]
        if d != current_date:
            current_date = d
            daily_pnl = 0.0
            consec_losses = 0

        t = time_f[i]

        # ── TRAILING STOP UPDATE ──
        if in_position:
            a_now = atr[i] if not np.isnan(atr[i]) else atr[i - 1]
            buf = trail_buf_atr * a_now if not np.isnan(a_now) else 0

            if pos_type == 1:  # LONG
                if swing_low[i] and not np.isnan(sl_price[i]):
                    sw_low = sl_price[i]
                    new_stop = sw_low - buf
                    if use_breakeven and not be_moved and sw_low > entry_price:
                        stop_price_pos = max(stop_price_pos, entry_price)
                        be_moved = True
                        trail_count += 1
                    if new_stop > stop_price_pos:
                        stop_price_pos = new_stop
                        trail_count += 1
            else:  # SHORT
                if swing_high[i] and not np.isnan(sh_price[i]):
                    sw_high = sh_price[i]
                    new_stop = sw_high + buf
                    if use_breakeven and not be_moved and sw_high < entry_price:
                        stop_price_pos = min(stop_price_pos, entry_price)
                        be_moved = True
                        trail_count += 1
                    if new_stop < stop_price_pos:
                        stop_price_pos = new_stop
                        trail_count += 1

        # ── EXIT LOGIC ──
        if in_position:
            bars_held = i - entry_bar
            exit_price_val = 0.0
            exit_reason = None

            if pos_type == 1:
                if low[i] <= stop_price_pos:
                    exit_price_val = stop_price_pos
                    exit_reason = 'TRAIL_STOP' if trail_count > 0 else 'STOP'
            else:
                if high[i] >= stop_price_pos:
                    exit_price_val = stop_price_pos
                    exit_reason = 'TRAIL_STOP' if trail_count > 0 else 'STOP'

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
                    'entry_type': 0,
                    'pattern': trade_pattern,
                    'trend_state': trade_trend,
                    'entry_price': round(entry_price, 2),
                    'exit_price': round(exit_price_val, 2),
                    'stop': round(initial_stop, 2),
                    'final_stop': round(stop_price_pos, 2),
                    'pnl': round(pnl, 2),
                    'bars_held': bars_held,
                    'exit_reason': exit_reason,
                    'trail_count': trail_count,
                    'date': str(d),
                })

                in_position = False
                continue

        # ── CHECK PENDING STOP ORDER FILL ──
        if has_pending and not in_position:
            if i - pending_placed_bar > order_timeout:
                has_pending = False
            else:
                filled = False
                if pending_dir == 1:  # BUY stop: price must go above entry
                    if high[i] >= pending_entry_price:
                        filled = True
                else:  # SELL stop: price must go below entry
                    if low[i] <= pending_entry_price:
                        filled = True

                if filled:
                    total_fills += 1
                    fill_price = pending_entry_price + (slippage if pending_dir == 1 else -slippage)

                    in_position = True
                    pos_type = pending_dir
                    entry_bar = i
                    entry_price = fill_price
                    stop_price_pos = pending_stop_price
                    initial_stop = pending_stop_price
                    trade_signal_bar = pending_signal_bar
                    trade_pattern = pending_pattern
                    trade_trend = pending_trend
                    has_pending = False
                    be_moved = False
                    trail_count = 0

                    # Same-bar stop check
                    exited_same_bar = False
                    exit_price_val = 0.0
                    exit_reason = None

                    if pos_type == 1:
                        if low[i] <= stop_price_pos:
                            exit_price_val = stop_price_pos
                            exit_reason = 'STOP'
                            exited_same_bar = True
                    else:
                        if high[i] >= stop_price_pos:
                            exit_price_val = stop_price_pos
                            exit_reason = 'STOP'
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
                            'entry_type': 0,
                            'pattern': trade_pattern,
                            'trend_state': trade_trend,
                            'entry_price': round(entry_price, 2),
                            'exit_price': round(exit_price_val, 2),
                            'stop': round(initial_stop, 2),
                            'final_stop': round(stop_price_pos, 2),
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

        # ── CHECK FOR SIGNAL ──
        # Use current bar as potential signal bar (entry order placed for next bars)
        if sig[i] == 0:
            continue

        if np.isnan(sig_entry[i]) or np.isnan(sig_stop[i]):
            continue

        total_signals += 1

        # Place stop order (replaces any existing pending)
        has_pending = True
        pending_dir = int(sig[i])
        pending_entry_price = sig_entry[i]
        pending_stop_price = sig_stop[i]
        pending_signal_bar = i
        pending_placed_bar = i  # order active starting next bar
        pending_pattern = sig_type[i]
        pending_trend = int(sig_trend[i])

    return trades, total_signals, total_fills


# ──────────────────────────────────────────────
# Extended statistics for V2
# ──────────────────────────────────────────────

def calculate_v2_statistics(trades, years, total_signals, total_fills):
    """Calculate V2-specific statistics beyond standard metrics."""
    base = calculate_statistics(trades, years)

    # Pattern breakdown
    patterns = {}
    for t in trades:
        p = t.get('pattern', 'UNKNOWN')
        if p not in patterns:
            patterns[p] = {'count': 0, 'pnl': 0, 'wins': 0}
        patterns[p]['count'] += 1
        patterns[p]['pnl'] += t['pnl']
        if t['pnl'] > 0:
            patterns[p]['wins'] += 1

    for p in patterns:
        c = patterns[p]['count']
        patterns[p]['win_rate'] = round(patterns[p]['wins'] / c * 100, 2) if c > 0 else 0
        patterns[p]['avg_pnl'] = round(patterns[p]['pnl'] / c, 2) if c > 0 else 0
        patterns[p]['pnl'] = round(patterns[p]['pnl'], 2)

    # Trend state breakdown
    trend_names = {TREND_UP: 'TREND_UP', TREND_DOWN: 'TREND_DOWN',
                   TREND_RANGE: 'RANGE', TREND_UNKNOWN: 'UNKNOWN'}
    trend_stats = {}
    for t in trades:
        ts = trend_names.get(t.get('trend_state', 0), 'UNKNOWN')
        if ts not in trend_stats:
            trend_stats[ts] = {'count': 0, 'pnl': 0, 'wins': 0}
        trend_stats[ts]['count'] += 1
        trend_stats[ts]['pnl'] += t['pnl']
        if t['pnl'] > 0:
            trend_stats[ts]['wins'] += 1

    for ts in trend_stats:
        c = trend_stats[ts]['count']
        trend_stats[ts]['win_rate'] = round(trend_stats[ts]['wins'] / c * 100, 2) if c > 0 else 0
        trend_stats[ts]['avg_pnl'] = round(trend_stats[ts]['pnl'] / c, 2) if c > 0 else 0
        trend_stats[ts]['pnl'] = round(trend_stats[ts]['pnl'], 2)

    base['pattern_breakdown'] = patterns
    base['trend_breakdown'] = trend_stats
    base['total_signals'] = total_signals
    base['total_fills'] = total_fills
    base['fill_rate'] = round(total_fills / total_signals * 100, 2) if total_signals > 0 else 0

    return base


# ──────────────────────────────────────────────
# Top-level API
# ──────────────────────────────────────────────

def run_strategy(df, params=None):
    """Full V2 pipeline: indicators → signals → backtest → stats."""
    if params is None:
        params = dict(DEFAULT_V2_PARAMS)

    data = precompute_indicators(df, params)
    signals = detect_signals_v2(data, params)
    trades, total_signals, total_fills = backtest_v2(data, signals, params)

    years = (df.index[-1] - df.index[0]).days / 365.25
    stats = calculate_v2_statistics(trades, years, total_signals, total_fills)

    return {
        'stats': stats,
        'trades': trades,
        'params': {k: v for k, v in params.items()},
    }
