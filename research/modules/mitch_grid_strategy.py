#!/usr/bin/env python3
"""
Mitch Grid Strategy — Production Module

Combines:
  - Layer 1: Trend structure detection (HH/HL/LH/LL state machine)
  - Layer 2: First-entry pullback signals at structure levels
  - Grid filter: Only trade in historically validated cells
  - Trail-only exits: Structure-based trailing stop, no fixed target

Grid cells are defined by:
  Fine:  (EMA distance bucket, time-of-day, direction)
  Ultra: (EMA distance bucket, time-of-day, direction, volatility regime)

Stable cells were identified via split-half validation on MNQ 5-min
2019-2026 data. Both halves independently showed PF > 1.0 in these cells.

Production backtest (stable fine cells):
  1,081 trades, PF=0.93, WR=34.9%, MaxDD=$3,832
Production backtest (stable ultra cells):
  1,184 trades, PF=1.04, WR=38.2%, PnL=+$1,402, MaxDD=$3,405

Note: Diagnostic retroactive tagging showed higher PF because it
analyzed trades already taken in an unfiltered backtest. Production
filtering changes position timing, freeing capacity in good cells
but letting in weaker signals that were previously blocked.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Set

from mitch_l1l2_strategy import (
    detect_swings, compute_swing_prices, compute_atr, compute_ema,
    precompute_indicators, detect_trend_and_entries, backtest_trailing,
    calculate_statistics, DEFAULT_PARAMS,
)


# ──────────────────────────────────────────────
# Grid cell definitions
# ──────────────────────────────────────────────

# Split-half validated: profitable in both 2019-2022 and 2022-2026
STABLE_FINE_CELLS = frozenset({
    'ema<-2|open|SHORT',
    'ema<-2|afternoon|SHORT',
    'ema<-2|morning|SHORT',
    'ema-2..-1|afternoon|SHORT',
    'ema>2|open|LONG',
    'ema>2|morning|LONG',
})

STABLE_ULTRA_CELLS = frozenset({
    'ema<-2|open|SHORT|high_vol',
    'ema<-2|morning|SHORT|high_vol',
    'ema-2..-1|afternoon|SHORT|norm_vol',
    'ema-1..0|morning|SHORT|norm_vol',
    'ema0..1|morning|LONG|norm_vol',
    'ema0..1|afternoon|LONG|norm_vol',
    'ema>2|open|LONG|high_vol',
    'ema>2|afternoon|LONG|low_vol',
})

# Full-sample profitable (not split-validated — use with caution)
ALL_PROFITABLE_FINE_CELLS = frozenset({
    'ema<-2|open|SHORT',
    'ema<-2|afternoon|SHORT',
    'ema<-2|morning|SHORT',
    'ema-2..-1|afternoon|SHORT',
    'ema-2..-1|morning|SHORT',
    'ema0..1|morning|SHORT',
    'ema1..2|afternoon|LONG',
    'ema>2|open|LONG',
    'ema>2|afternoon|LONG',
    'ema>2|morning|LONG',
})

GRID_PARAMS = {
    'swing_strength': 2,
    'atr_period': 14,
    'ema_period': 21,
    'use_ema_confirmation': False,
    'track_first_entries': True,
    'slippage': 2.0,
    'commission': 2.0,
    'stop_buffer_atr': 1.5,
    'max_stop_atr': 2.0,
    'target_atr_fallback': 3.0,
    'measured_move_cap_atr': 8.0,
    'max_hold': 90,
    'max_daily_loss': -200,
    'max_consec_losses': 3,
    'rth_start': 8.5,
    'rth_end': 15.0,
    'point_value': 1.0,
    'trail_buffer_atr': 0.8,
    'use_breakeven': True,
    'trail_only': True,
}


# ──────────────────────────────────────────────
# Grid cell classification
# ──────────────────────────────────────────────

def classify_ema_bucket(ema_dist_atr: float) -> Optional[str]:
    """Classify EMA distance (in ATR units) into a grid bucket."""
    if np.isnan(ema_dist_atr):
        return None
    if ema_dist_atr < -2:
        return 'ema<-2'
    elif ema_dist_atr < -1:
        return 'ema-2..-1'
    elif ema_dist_atr < 0:
        return 'ema-1..0'
    elif ema_dist_atr < 1:
        return 'ema0..1'
    elif ema_dist_atr < 2:
        return 'ema1..2'
    else:
        return 'ema>2'


def classify_tod(time_f: float) -> Optional[str]:
    """Classify time-of-day into a grid bucket."""
    if 8.5 <= time_f < 9.5:
        return 'open'
    elif 9.5 <= time_f < 12.0:
        return 'morning'
    elif 12.0 <= time_f < 15.0:
        return 'afternoon'
    return None


def classify_vol(atr_ratio: float) -> str:
    """Classify volatility regime: current ATR / 50-bar rolling mean."""
    if atr_ratio < 0.9:
        return 'low_vol'
    elif atr_ratio < 1.2:
        return 'norm_vol'
    else:
        return 'high_vol'


def make_fine_key(ema_bucket: str, tod: str, direction: str) -> str:
    return f"{ema_bucket}|{tod}|{direction}"


def make_ultra_key(ema_bucket: str, tod: str, direction: str, vol: str) -> str:
    return f"{ema_bucket}|{tod}|{direction}|{vol}"


# ──────────────────────────────────────────────
# Grid-filtered backtest
# ──────────────────────────────────────────────

def backtest_grid(data, signals, params=None, grid_mode='fine',
                  allowed_cells=None):
    """Run trail-only backtest, filtering entries by grid cell.

    Args:
        data: precomputed indicator arrays
        signals: output of detect_trend_and_entries
        params: strategy parameters (defaults to GRID_PARAMS)
        grid_mode: 'fine' or 'ultra'
        allowed_cells: set of cell keys to allow (defaults to stable cells)

    Returns:
        list of trade dicts, each tagged with grid cell info
    """
    if params is None:
        params = GRID_PARAMS
    if allowed_cells is None:
        if grid_mode == 'ultra':
            allowed_cells = STABLE_ULTRA_CELLS
        else:
            allowed_cells = STABLE_FINE_CELLS

    n = data['n']
    opn = data['open']
    high = data['high']
    low = data['low']
    close = data['close']
    atr = data['atr']
    ema = data['ema']
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
    trail_buf_atr = params.get('trail_buffer_atr', 0.8)
    use_breakeven = params.get('use_breakeven', True)

    # Precompute 50-bar rolling ATR mean for vol classification
    atr_roll50 = np.full(n, np.nan)
    for i in range(50, n):
        atr_roll50[i] = np.nanmean(atr[i-50:i])

    # Position state
    in_position = False
    pos_type = 0
    entry_bar = 0
    entry_price = 0.0
    stop_price = 0.0
    initial_stop = 0.0
    trade_entry_type = 0
    trade_signal_bar = 0
    be_moved = False
    trail_count = 0
    trade_cell = ''

    # Pending entry
    has_pending = False
    pending_dir = 0
    pending_stop = 0.0
    pending_entry_type = 0
    pending_signal_bar = 0
    pending_cell = ''

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

        # ── TRAILING STOP UPDATE ──
        if in_position:
            a_now = atr[i] if not np.isnan(atr[i]) else atr[i - 1]
            buf = trail_buf_atr * a_now if not np.isnan(a_now) else 0

            if pos_type == 1:  # LONG
                if swing_low[i] and not np.isnan(sl_price[i]):
                    sw_low = sl_price[i]
                    new_stop = sw_low - buf
                    if use_breakeven and not be_moved and sw_low > entry_price:
                        stop_price = max(stop_price, entry_price)
                        be_moved = True
                        trail_count += 1
                    if new_stop > stop_price:
                        stop_price = new_stop
                        trail_count += 1
            else:  # SHORT
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

            if pos_type == 1:
                if low[i] <= stop_price:
                    exit_price_val = stop_price
                    exit_reason = 'TRAIL_STOP' if trail_count > 0 else 'STOP'
            else:
                if high[i] >= stop_price:
                    exit_price_val = stop_price
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
                    'entry_type': trade_entry_type,
                    'entry_price': round(entry_price, 2),
                    'exit_price': round(exit_price_val, 2),
                    'stop': round(initial_stop, 2),
                    'final_stop': round(stop_price, 2),
                    'pnl': round(pnl, 2),
                    'bars_held': bars_held,
                    'exit_reason': exit_reason,
                    'trail_count': trail_count,
                    'cell': trade_cell,
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
            trade_entry_type = pending_entry_type
            trade_signal_bar = pending_signal_bar
            trade_cell = pending_cell
            has_pending = False
            be_moved = False
            trail_count = 0

            # Same-bar stop check
            exited_same_bar = False
            exit_price_val = 0.0
            exit_reason = None

            if pos_type == 1:
                if low[i] <= stop_price:
                    exit_price_val = stop_price
                    exit_reason = 'STOP'
                    exited_same_bar = True
            else:
                if high[i] >= stop_price:
                    exit_price_val = stop_price
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
                    'entry_type': trade_entry_type,
                    'entry_price': round(entry_price, 2),
                    'exit_price': round(exit_price_val, 2),
                    'stop': round(initial_stop, 2),
                    'final_stop': round(stop_price, 2),
                    'pnl': round(pnl, 2),
                    'bars_held': 0,
                    'exit_reason': exit_reason,
                    'trail_count': 0,
                    'cell': trade_cell,
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

        # ── GRID FILTER ──
        direction = 'LONG' if sig[prev] == 1 else 'SHORT'

        # EMA distance
        ema_dist = (close[prev] - ema[prev]) / a if not np.isnan(ema[prev]) else np.nan
        ema_bkt = classify_ema_bucket(ema_dist)
        if ema_bkt is None:
            continue

        # Time of day
        tod = classify_tod(time_f[prev])
        if tod is None:
            continue

        if grid_mode == 'ultra':
            # Vol regime
            roll50 = atr_roll50[prev]
            if np.isnan(roll50) or roll50 == 0:
                continue
            vol_ratio = a / roll50
            vol_bkt = classify_vol(vol_ratio)
            cell_key = make_ultra_key(ema_bkt, tod, direction, vol_bkt)
        else:
            cell_key = make_fine_key(ema_bkt, tod, direction)

        if cell_key not in allowed_cells:
            continue

        # ── QUEUE ENTRY ──
        has_pending = True
        pending_dir = int(sig[prev])
        pending_stop = stop_lvl[prev]
        pending_entry_type = int(etype[prev])
        pending_signal_bar = prev
        pending_cell = cell_key

    return trades


def backtest_grid_limit(data, signals, params=None, grid_mode='fine',
                        allowed_cells=None):
    """Grid-filtered backtest with LIMIT ORDER entries at swing prices.

    Instead of market-ordering at next bar's open, places a limit order
    at the swing price level. Fills only when the wick reaches that price.

    Advantages over market orders:
    - Better entry price (at the structure level, not chasing)
    - No entry slippage (filled at limit or better)
    - Natural filter: signals where price runs away don't fill

    New params (with defaults):
        'order_timeout': 5      — bars before limit order expires
    """
    if params is None:
        params = GRID_PARAMS
    if allowed_cells is None:
        if grid_mode == 'ultra':
            allowed_cells = STABLE_ULTRA_CELLS
        else:
            allowed_cells = STABLE_FINE_CELLS

    n = data['n']
    high = data['high']
    low = data['low']
    close = data['close']
    atr = data['atr']
    ema = data['ema']
    time_f = data['time_f']
    dates = data['date']
    swing_high = data['swing_high']
    swing_low = data['swing_low']
    sh_price = data['swing_high_price']
    sl_price = data['swing_low_price']

    sig = signals['signal']
    etype = signals['entry_type']
    stop_lvl = signals['stop_level']

    rth_start = params['rth_start']
    rth_end = params['rth_end']
    max_hold = params['max_hold']
    max_daily_loss = params['max_daily_loss']
    max_consec = params['max_consec_losses']
    commission = params['commission']
    point_value = params['point_value']
    trail_buf_atr = params.get('trail_buffer_atr', 0.8)
    use_breakeven = params.get('use_breakeven', True)
    order_timeout = params.get('order_timeout', 5)

    # Precompute 50-bar rolling ATR mean for vol classification
    atr_roll50 = np.full(n, np.nan)
    for i in range(50, n):
        atr_roll50[i] = np.nanmean(atr[i-50:i])

    # Position state
    in_position = False
    pos_type = 0
    entry_bar = 0
    entry_price = 0.0
    stop_price = 0.0
    initial_stop = 0.0
    trade_entry_type = 0
    trade_signal_bar = 0
    be_moved = False
    trail_count = 0
    trade_cell = ''

    # Pending limit order
    has_pending = False
    pending_dir = 0
    pending_limit_price = 0.0
    pending_stop = 0.0
    pending_entry_type = 0
    pending_signal_bar = 0
    pending_placed_bar = 0
    pending_cell = ''

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

        # ── TRAILING STOP UPDATE ──
        if in_position:
            a_now = atr[i] if not np.isnan(atr[i]) else atr[i - 1]
            buf = trail_buf_atr * a_now if not np.isnan(a_now) else 0

            if pos_type == 1:  # LONG
                if swing_low[i] and not np.isnan(sl_price[i]):
                    sw_low = sl_price[i]
                    new_stop = sw_low - buf
                    if use_breakeven and not be_moved and sw_low > entry_price:
                        stop_price = max(stop_price, entry_price)
                        be_moved = True
                        trail_count += 1
                    if new_stop > stop_price:
                        stop_price = new_stop
                        trail_count += 1
            else:  # SHORT
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

            if pos_type == 1:
                if low[i] <= stop_price:
                    exit_price_val = stop_price
                    exit_reason = 'TRAIL_STOP' if trail_count > 0 else 'STOP'
            else:
                if high[i] >= stop_price:
                    exit_price_val = stop_price
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
                    'entry_type': trade_entry_type,
                    'entry_price': round(entry_price, 2),
                    'exit_price': round(exit_price_val, 2),
                    'stop': round(initial_stop, 2),
                    'final_stop': round(stop_price, 2),
                    'pnl': round(pnl, 2),
                    'bars_held': bars_held,
                    'exit_reason': exit_reason,
                    'trail_count': trail_count,
                    'cell': trade_cell,
                    'date': str(d),
                })

                in_position = False
                continue

        # ── CHECK PENDING LIMIT ORDER FILL ──
        if has_pending and not in_position:
            # Expire if timed out
            if i - pending_placed_bar > order_timeout:
                has_pending = False
            else:
                filled = False
                if pending_dir == 1:  # BUY limit: wick dips to limit price
                    if low[i] <= pending_limit_price:
                        filled = True
                else:  # SELL limit: wick reaches limit price
                    if high[i] >= pending_limit_price:
                        filled = True

                if filled:
                    in_position = True
                    pos_type = pending_dir
                    entry_bar = i
                    entry_price = pending_limit_price  # filled at limit
                    stop_price = pending_stop
                    initial_stop = pending_stop
                    trade_entry_type = pending_entry_type
                    trade_signal_bar = pending_signal_bar
                    trade_cell = pending_cell
                    has_pending = False
                    be_moved = False
                    trail_count = 0

                    # Same-bar stop check (conservative: assume stop hit)
                    exited_same_bar = False
                    exit_price_val = 0.0
                    exit_reason = None

                    if pos_type == 1:
                        if low[i] <= stop_price:
                            exit_price_val = stop_price
                            exit_reason = 'STOP'
                            exited_same_bar = True
                    else:
                        if high[i] >= stop_price:
                            exit_price_val = stop_price
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
                            'entry_type': trade_entry_type,
                            'entry_price': round(entry_price, 2),
                            'exit_price': round(exit_price_val, 2),
                            'stop': round(initial_stop, 2),
                            'final_stop': round(stop_price, 2),
                            'pnl': round(pnl, 2),
                            'bars_held': 0,
                            'exit_reason': exit_reason,
                            'trail_count': 0,
                            'cell': trade_cell,
                            'date': str(d),
                        })
                        in_position = False

                    continue  # don't place new order on fill bar

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
        if np.isnan(stop_lvl[prev]):
            continue

        # ── GET LIMIT PRICE (swing price at signal bar) ──
        if sig[prev] == 1:  # LONG signal from confirmed swing low
            limit_price = sl_price[prev]
        else:  # SHORT signal from confirmed swing high
            limit_price = sh_price[prev]

        if np.isnan(limit_price):
            continue

        # ── GRID FILTER ──
        direction = 'LONG' if sig[prev] == 1 else 'SHORT'

        ema_dist = (close[prev] - ema[prev]) / a if not np.isnan(ema[prev]) else np.nan
        ema_bkt = classify_ema_bucket(ema_dist)
        if ema_bkt is None:
            continue

        tod = classify_tod(time_f[prev])
        if tod is None:
            continue

        if grid_mode == 'ultra':
            roll50 = atr_roll50[prev]
            if np.isnan(roll50) or roll50 == 0:
                continue
            vol_ratio = a / roll50
            vol_bkt = classify_vol(vol_ratio)
            cell_key = make_ultra_key(ema_bkt, tod, direction, vol_bkt)
        else:
            cell_key = make_fine_key(ema_bkt, tod, direction)

        if cell_key not in allowed_cells:
            continue

        # ── PLACE LIMIT ORDER (replaces any existing) ──
        has_pending = True
        pending_dir = int(sig[prev])
        pending_limit_price = limit_price
        pending_stop = stop_lvl[prev]
        pending_entry_type = int(etype[prev])
        pending_signal_bar = prev
        pending_placed_bar = i  # placed on bar after signal
        pending_cell = cell_key

    return trades


# ──────────────────────────────────────────────
# Top-level API
# ──────────────────────────────────────────────

def run_grid_strategy(df, params=None, grid_mode='fine', allowed_cells=None):
    """Full pipeline: precompute → signals → grid-filtered backtest → stats.

    Args:
        df: OHLCV DataFrame with DatetimeIndex
        params: strategy parameters (defaults to GRID_PARAMS)
        grid_mode: 'fine' (6 stable cells) or 'ultra' (8 stable cells)
        allowed_cells: override cell set (None = use stable defaults)

    Returns:
        dict with 'stats', 'trades', 'params', 'grid_mode', 'cells_used'
    """
    if params is None:
        params = dict(GRID_PARAMS)

    if allowed_cells is None:
        if grid_mode == 'ultra':
            allowed_cells = STABLE_ULTRA_CELLS
        else:
            allowed_cells = STABLE_FINE_CELLS

    data = precompute_indicators(df, params)
    signals = detect_trend_and_entries(data, params)
    trades = backtest_grid(data, signals, params,
                           grid_mode=grid_mode, allowed_cells=allowed_cells)

    years = (df.index[-1] - df.index[0]).days / 365.25
    stats = calculate_statistics(trades, years)

    return {
        'stats': stats,
        'trades': trades,
        'params': params,
        'grid_mode': grid_mode,
        'cells_used': sorted(allowed_cells),
    }


def run_grid_strategy_limit(df, params=None, grid_mode='fine',
                            allowed_cells=None):
    """Full pipeline with limit-order entries at swing prices."""
    if params is None:
        params = dict(GRID_PARAMS)

    if allowed_cells is None:
        if grid_mode == 'ultra':
            allowed_cells = STABLE_ULTRA_CELLS
        else:
            allowed_cells = STABLE_FINE_CELLS

    data = precompute_indicators(df, params)
    signals = detect_trend_and_entries(data, params)
    trades = backtest_grid_limit(data, signals, params,
                                 grid_mode=grid_mode, allowed_cells=allowed_cells)

    years = (df.index[-1] - df.index[0]).days / 365.25
    stats = calculate_statistics(trades, years)

    return {
        'stats': stats,
        'trades': trades,
        'params': params,
        'grid_mode': grid_mode,
        'cells_used': sorted(allowed_cells),
    }
