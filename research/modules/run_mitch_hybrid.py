#!/usr/bin/env python3
"""
Mitch Hybrid Strategy — V1 Engine + Signal Bar Quality Filter

Takes V1's proven pipeline (trend pullbacks + limit orders + grid filter
+ trail-only exit) and adds V2's signal bar quality check as an extra gate.

Hypothesis: the signal bar filter should reject low-quality setups where
the bar at signal confirmation doesn't show directional conviction,
improving PF without killing trade count.

Tests:
  - V1 baseline (no signal bar filter)
  - V1 + moderate signal bar filter
  - V1 + strict signal bar filter
  - Each tested with: no grid, Ultra(8), and no grid + range trading
"""

import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).parent))
from mitch_l1l2_strategy import (
    detect_swings, compute_swing_prices, compute_atr, compute_ema,
    precompute_indicators, detect_trend_and_entries, calculate_statistics,
    TREND_UP, TREND_DOWN, TREND_RANGE, TREND_UNKNOWN,
)
from mitch_grid_strategy import (
    GRID_PARAMS, STABLE_ULTRA_CELLS, STABLE_FINE_CELLS,
    ALL_PROFITABLE_FINE_CELLS,
    classify_ema_bucket, classify_tod, classify_vol,
    make_fine_key, make_ultra_key,
)


# ──────────────────────────────────────────────
# Signal bar quality check (from V2)
# ──────────────────────────────────────────────

def check_signal_bar(open_p, high, low, close, atr, direction,
                     close_pct=0.40, body_pct=0.15, min_atr=0.15, max_atr=3.0):
    """Check if a bar qualifies as a good signal bar.

    direction: 1 = bullish (for long signal), -1 = bearish (for short signal)
    Returns True if bar passes quality filter.
    """
    bar_range = high - low
    if bar_range <= 0:
        return False
    if np.isnan(atr) or atr <= 0:
        return False
    if bar_range < min_atr * atr:
        return False
    if bar_range > max_atr * atr:
        return False

    body = abs(close - open_p)
    if body / bar_range < body_pct:
        return False

    if direction == 1:  # Bullish bar for long signal
        if close <= open_p:
            return False
        if (close - low) / bar_range < (1.0 - close_pct):
            return False
    else:  # Bearish bar for short signal
        if close >= open_p:
            return False
        if (high - close) / bar_range < (1.0 - close_pct):
            return False

    return True


# ──────────────────────────────────────────────
# Hybrid backtest: V1 grid+limit + signal bar filter
# ──────────────────────────────────────────────

def backtest_hybrid(data, signals, params, grid_mode='none',
                    allowed_cells=None, signal_bar_filter=None,
                    enable_range_trading=False):
    """V1 grid+limit backtest with optional signal bar quality filter.

    Args:
        signal_bar_filter: None (disabled) or dict with keys:
            close_pct, body_pct, min_atr, max_atr
        enable_range_trading: if True, also generate signals in RANGE state
            (requires extending V1's signal logic inline)
    """
    n = data['n']
    high = data['high']
    low = data['low']
    close = data['close']
    open_p = data['open']
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
    trend_arr = signals['trend']

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

    use_grid = grid_mode != 'none' and allowed_cells is not None
    use_ultra = grid_mode == 'ultra'

    # Precompute vol rolling if needed
    atr_roll50 = np.full(n, np.nan)
    if use_ultra:
        for i in range(50, n):
            atr_roll50[i] = np.nanmean(atr[i-50:i])

    # For range trading: also look for signals in RANGE
    # V1 only signals in TREND_UP/DOWN. We extend by also counting pullbacks in RANGE.
    # Implementation: if enable_range_trading, treat any confirmed swing near
    # a recent swing level as a signal in RANGE state.
    # Simplified: in RANGE, a swing low = potential long, swing high = potential short

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
    signals_seen = 0
    signals_passed_bar = 0
    signals_passed_grid = 0

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

            if pos_type == 1:
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
            else:
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
            if i - pending_placed_bar > order_timeout:
                has_pending = False
            else:
                filled = False
                if pending_dir == 1:
                    if low[i] <= pending_limit_price:
                        filled = True
                else:
                    if high[i] >= pending_limit_price:
                        filled = True

                if filled:
                    in_position = True
                    pos_type = pending_dir
                    entry_bar = i
                    entry_price = pending_limit_price
                    stop_price = pending_stop
                    initial_stop = pending_stop
                    trade_entry_type = pending_entry_type
                    trade_signal_bar = pending_signal_bar
                    trade_cell = pending_cell
                    has_pending = False
                    be_moved = False
                    trail_count = 0

                    # Same-bar stop check
                    exited = False
                    exit_pv = 0.0
                    exit_r = None

                    if pos_type == 1:
                        if low[i] <= stop_price:
                            exit_pv = stop_price
                            exit_r = 'STOP'
                            exited = True
                    else:
                        if high[i] >= stop_price:
                            exit_pv = stop_price
                            exit_r = 'STOP'
                            exited = True

                    if exited:
                        if pos_type == 1:
                            raw_pnl = (exit_pv - entry_price) * point_value
                        else:
                            raw_pnl = (entry_price - exit_pv) * point_value

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
                            'exit_price': round(exit_pv, 2),
                            'stop': round(initial_stop, 2),
                            'final_stop': round(stop_price, 2),
                            'pnl': round(pnl, 2),
                            'bars_held': 0,
                            'exit_reason': exit_r,
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
        has_signal = sig[prev] != 0

        # Range trading extension: in RANGE, treat new swing as signal
        range_signal_dir = 0
        if not has_signal and enable_range_trading and trend_arr[prev] == TREND_RANGE:
            if swing_low[prev] and not np.isnan(sl_price[prev]):
                range_signal_dir = 1  # swing low in range = long
                has_signal = True
            elif swing_high[prev] and not np.isnan(sh_price[prev]):
                range_signal_dir = -1  # swing high in range = short
                has_signal = True

        if not has_signal:
            continue

        # Determine signal direction
        if range_signal_dir != 0:
            sig_dir = range_signal_dir
        else:
            sig_dir = int(sig[prev])

        a = atr[prev]
        if np.isnan(a) or a == 0:
            continue

        # Get limit price (swing price at signal bar)
        if sig_dir == 1:
            limit_price = sl_price[prev]
        else:
            limit_price = sh_price[prev]

        if np.isnan(limit_price):
            continue

        # Get stop level
        if range_signal_dir != 0:
            # For range signals, compute stop from swing + buffer
            buf = params.get('stop_buffer_atr', 1.5)
            max_stop = params.get('max_stop_atr', 2.0)
            if sig_dir == 1:
                raw_stop = limit_price - buf * a
                if limit_price - raw_stop > max_stop * a:
                    raw_stop = limit_price - max_stop * a
                sig_stop = raw_stop
            else:
                raw_stop = limit_price + buf * a
                if raw_stop - limit_price > max_stop * a:
                    raw_stop = limit_price + max_stop * a
                sig_stop = raw_stop
        else:
            sig_stop = stop_lvl[prev]
            if np.isnan(sig_stop):
                continue

        signals_seen += 1

        # ── SIGNAL BAR QUALITY FILTER ──
        if signal_bar_filter is not None:
            passed = check_signal_bar(
                open_p[prev], high[prev], low[prev], close[prev], a, sig_dir,
                close_pct=signal_bar_filter.get('close_pct', 0.40),
                body_pct=signal_bar_filter.get('body_pct', 0.15),
                min_atr=signal_bar_filter.get('min_atr', 0.15),
                max_atr=signal_bar_filter.get('max_atr', 3.0),
            )
            if not passed:
                continue

        signals_passed_bar += 1

        # ── GRID FILTER ──
        if use_grid:
            direction = 'LONG' if sig_dir == 1 else 'SHORT'
            ema_dist = (close[prev] - ema[prev]) / a if not np.isnan(ema[prev]) else np.nan
            ema_bkt = classify_ema_bucket(ema_dist)
            if ema_bkt is None:
                continue
            tod = classify_tod(time_f[prev])
            if tod is None:
                continue

            if use_ultra:
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
        else:
            cell_key = ''

        signals_passed_grid += 1

        # ── PLACE LIMIT ORDER ──
        has_pending = True
        pending_dir = sig_dir
        pending_limit_price = limit_price
        pending_stop = sig_stop
        pending_entry_type = int(etype[prev]) if range_signal_dir == 0 else 0
        pending_signal_bar = prev
        pending_placed_bar = i
        pending_cell = cell_key

    return trades, signals_seen, signals_passed_bar, signals_passed_grid


# ──────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────

def load_data():
    data_dir = Path.home() / '.openclaw' / 'workspace' / 'data'
    path = data_dir / 'MNQ_5min.csv'
    df = pd.read_csv(path, parse_dates=['time'], index_col='time')
    df.columns = [c.lower() for c in df.columns]
    return df


def run_config(df, data, signals, params, label, grid_mode='none',
               allowed_cells=None, signal_bar_filter=None,
               enable_range_trading=False):
    trades, sig_seen, sig_bar, sig_grid = backtest_hybrid(
        data, signals, params,
        grid_mode=grid_mode, allowed_cells=allowed_cells,
        signal_bar_filter=signal_bar_filter,
        enable_range_trading=enable_range_trading,
    )
    years = (df.index[-1] - df.index[0]).days / 365.25
    stats = calculate_statistics(trades, years)

    # Long/short PF
    longs = [t for t in trades if t['direction'] == 'LONG']
    shorts = [t for t in trades if t['direction'] == 'SHORT']
    def pf(tlist):
        if not tlist:
            return 0
        p = np.array([t['pnl'] for t in tlist])
        gp = p[p > 0].sum()
        gl = abs(p[p < 0].sum())
        return round(gp / gl, 4) if gl > 0 else 999.0

    return {
        'label': label,
        'trades': stats['total_trades'],
        'signals_seen': sig_seen,
        'passed_bar': sig_bar,
        'passed_grid': sig_grid,
        'trades_per_day': stats.get('trades_per_day', 0),
        'trades_per_year': stats.get('trades_per_year', 0),
        'win_rate': stats['win_rate'],
        'profit_factor': stats['profit_factor'],
        'total_pnl': stats['total_pnl'],
        'pnl_per_year': stats.get('annual_pnl', 0),
        'sharpe': stats['sharpe'],
        'max_drawdown': stats['max_drawdown'],
        'avg_bars': stats.get('avg_bars_held', 0),
        'long_n': len(longs),
        'short_n': len(shorts),
        'long_pf': pf(longs),
        'short_pf': pf(shorts),
    }


# Signal bar filter presets
MODERATE_FILTER = {'close_pct': 0.40, 'body_pct': 0.15, 'min_atr': 0.15, 'max_atr': 3.0}
STRICT_FILTER = {'close_pct': 0.30, 'body_pct': 0.25, 'min_atr': 0.20, 'max_atr': 2.5}


def main():
    print("Loading data...")
    df = load_data()
    print(f"  {len(df):,} bars, {df.index[0].date()} to {df.index[-1].date()}\n")

    params = dict(GRID_PARAMS)

    print("Precomputing indicators...")
    data = precompute_indicators(df, params)
    signals = detect_trend_and_entries(data, params)

    configs = []

    # ── GROUP 1: No grid filter (unfiltered) ──
    print("\n--- NO GRID FILTER ---")

    print("  1. V1 baseline (no grid, no sigbar)...")
    configs.append(run_config(df, data, signals, params,
                              "NO GRID: baseline",
                              grid_mode='none'))

    print("  2. V1 + moderate sigbar filter...")
    configs.append(run_config(df, data, signals, params,
                              "NO GRID: +moderate sigbar",
                              grid_mode='none',
                              signal_bar_filter=MODERATE_FILTER))

    print("  3. V1 + strict sigbar filter...")
    configs.append(run_config(df, data, signals, params,
                              "NO GRID: +strict sigbar",
                              grid_mode='none',
                              signal_bar_filter=STRICT_FILTER))

    # ── GROUP 2: Ultra(8) grid ──
    print("\n--- ULTRA(8) GRID ---")

    print("  4. V1 Ultra(8) baseline...")
    configs.append(run_config(df, data, signals, params,
                              "ULTRA(8): baseline",
                              grid_mode='ultra',
                              allowed_cells=STABLE_ULTRA_CELLS))

    print("  5. Ultra(8) + moderate sigbar...")
    configs.append(run_config(df, data, signals, params,
                              "ULTRA(8): +moderate sigbar",
                              grid_mode='ultra',
                              allowed_cells=STABLE_ULTRA_CELLS,
                              signal_bar_filter=MODERATE_FILTER))

    print("  6. Ultra(8) + strict sigbar...")
    configs.append(run_config(df, data, signals, params,
                              "ULTRA(8): +strict sigbar",
                              grid_mode='ultra',
                              allowed_cells=STABLE_ULTRA_CELLS,
                              signal_bar_filter=STRICT_FILTER))

    # ── GROUP 3: Fine(10) grid ──
    print("\n--- FINE(10) GRID ---")

    print("  7. V1 Fine(10) baseline...")
    configs.append(run_config(df, data, signals, params,
                              "FINE(10): baseline",
                              grid_mode='fine',
                              allowed_cells=ALL_PROFITABLE_FINE_CELLS))

    print("  8. Fine(10) + moderate sigbar...")
    configs.append(run_config(df, data, signals, params,
                              "FINE(10): +moderate sigbar",
                              grid_mode='fine',
                              allowed_cells=ALL_PROFITABLE_FINE_CELLS,
                              signal_bar_filter=MODERATE_FILTER))

    print("  9. Fine(10) + strict sigbar...")
    configs.append(run_config(df, data, signals, params,
                              "FINE(10): +strict sigbar",
                              grid_mode='fine',
                              allowed_cells=ALL_PROFITABLE_FINE_CELLS,
                              signal_bar_filter=STRICT_FILTER))

    # ── GROUP 4: Range trading extension ──
    print("\n--- RANGE TRADING EXTENSION ---")

    print("  10. No grid + range trading...")
    configs.append(run_config(df, data, signals, params,
                              "NO GRID: +range trading",
                              grid_mode='none',
                              enable_range_trading=True))

    print("  11. No grid + range + moderate sigbar...")
    configs.append(run_config(df, data, signals, params,
                              "NO GRID: +range +mod sigbar",
                              grid_mode='none',
                              enable_range_trading=True,
                              signal_bar_filter=MODERATE_FILTER))

    print("  12. No grid + range + strict sigbar...")
    configs.append(run_config(df, data, signals, params,
                              "NO GRID: +range +strict sigbar",
                              grid_mode='none',
                              enable_range_trading=True,
                              signal_bar_filter=STRICT_FILTER))

    # ── Print results ──
    print(f"\n{'='*120}")
    print(f"  HYBRID V1 + SIGNAL BAR FILTER RESULTS")
    print(f"{'='*120}")

    print(f"\n{'Label':35s} {'N':>5s} {'SigSeen':>7s} {'PassBar':>7s} {'PassGrd':>7s} "
          f"{'T/Day':>6s} {'T/Yr':>6s} {'WR':>6s} {'PF':>7s} "
          f"{'P&L':>10s} {'$/Yr':>9s} {'Sharpe':>7s} {'MaxDD':>8s}")
    print(f"{'-'*35} {'-'*5} {'-'*7} {'-'*7} {'-'*7} "
          f"{'-'*6} {'-'*6} {'-'*6} {'-'*7} "
          f"{'-'*10} {'-'*9} {'-'*7} {'-'*8}")

    for c in configs:
        print(f"{c['label']:35s} {c['trades']:5d} {c['signals_seen']:7d} "
              f"{c['passed_bar']:7d} {c['passed_grid']:7d} "
              f"{c['trades_per_day']:5.2f} {c['trades_per_year']:5.0f} "
              f"{c['win_rate']:5.1f}% {c['profit_factor']:7.4f} "
              f"${c['total_pnl']:9,.0f} ${c['pnl_per_year']:8,.0f} "
              f"{c['sharpe']:7.4f} ${c['max_drawdown']:7,.0f}")

    print(f"\n{'Label':35s} {'LongN':>6s} {'LongPF':>7s} {'ShortN':>7s} {'ShortPF':>8s} {'AvgBars':>7s}")
    print(f"{'-'*35} {'-'*6} {'-'*7} {'-'*7} {'-'*8} {'-'*7}")

    for c in configs:
        print(f"{c['label']:35s} {c['long_n']:6d} {c['long_pf']:7.4f} "
              f"{c['short_n']:7d} {c['short_pf']:8.4f} {c['avg_bars']:6.1f}")

    print(f"\n{'='*120}")

    # Save
    out_path = Path(__file__).parent.parent / 'analysis' / 'mitch_hybrid_results.json'
    with open(out_path, 'w') as f:
        json.dump({'configs': configs}, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == '__main__':
    main()
