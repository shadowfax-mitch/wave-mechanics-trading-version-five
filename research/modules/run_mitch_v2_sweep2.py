#!/usr/bin/env python3
"""
V2 Sweep Round 2 — Radical parameter changes.

Tests whether the S/R concept can work with:
  - ATR-based stops instead of signal bar stops
  - Higher swing strength (more significant levels)
  - Much higher touch requirements
  - Counter-trend trading
  - Limit order entry instead of stop orders
"""

import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).parent))
from mitch_v2_strategy import (
    precompute_indicators, detect_signals_v2, backtest_v2,
    calculate_v2_statistics, DEFAULT_V2_PARAMS, MNQ_TICK,
)
from mitch_l1l2_strategy import (
    detect_swings, compute_swing_prices, compute_atr, compute_ema,
    calculate_statistics,
)


def load_data():
    data_dir = Path.home() / '.openclaw' / 'workspace' / 'data'
    path = data_dir / 'MNQ_5min.csv'
    df = pd.read_csv(path, parse_dates=['time'], index_col='time')
    df.columns = [c.lower() for c in df.columns]
    return df


def run_v2(df, label, overrides):
    """Standard V2 run."""
    from mitch_v2_strategy import run_strategy
    params = dict(DEFAULT_V2_PARAMS)
    params.update(overrides)
    result = run_strategy(df, params)
    return summarize(label, result['stats'])


def run_v2_atr_stop(df, label, overrides):
    """V2 signals but with ATR-based stops instead of signal bar stops.

    Override the signal's stop price with swing_price - buffer*ATR
    """
    params = dict(DEFAULT_V2_PARAMS)
    params.update(overrides)

    data = precompute_indicators(df, params)
    signals = detect_signals_v2(data, params)

    # Override stop prices: use ATR-based stops from the S/R level
    atr = data['atr']
    sig = signals['signal']
    stop_buf = params.get('atr_stop_buffer', 1.5)
    max_stop = params['max_stop_atr']

    for i in range(data['n']):
        if sig[i] == 0:
            continue
        a = atr[i]
        if np.isnan(a) or a <= 0:
            continue

        if sig[i] == 1:  # LONG: stop below entry
            entry_p = data['high'][i] + MNQ_TICK
            new_stop = entry_p - stop_buf * a
            new_stop = max(new_stop, entry_p - max_stop * a)
            signals['stop_price'][i] = new_stop
        else:  # SHORT: stop above entry
            entry_p = data['low'][i] - MNQ_TICK
            new_stop = entry_p + stop_buf * a
            new_stop = min(new_stop, entry_p + max_stop * a)
            signals['stop_price'][i] = new_stop

    trades, total_signals, total_fills = backtest_v2(data, signals, params)
    years = (df.index[-1] - df.index[0]).days / 365.25
    stats = calculate_v2_statistics(trades, years, total_signals, total_fills)
    return summarize(label, stats)


def summarize(label, s):
    return {
        'label': label,
        'trades': s['total_trades'],
        'trades_per_day': s.get('trades_per_day', 0),
        'win_rate': s['win_rate'],
        'profit_factor': s['profit_factor'],
        'total_pnl': s['total_pnl'],
        'pnl_per_year': s.get('annual_pnl', 0),
        'sharpe': s['sharpe'],
        'max_drawdown': s['max_drawdown'],
        'avg_win': s['avg_win'],
        'avg_loss': s['avg_loss'],
        'avg_bars': s.get('avg_bars_held', 0),
    }


def main():
    print("Loading data...")
    df = load_data()
    print(f"  {len(df):,} bars\n")

    configs = []

    # ── 1. Baseline for reference ──
    print("1/8  Baseline...")
    configs.append(run_v2(df, "BASELINE", {}))

    # ── 2. ATR-based stops (1.5 ATR from entry) ──
    print("2/8  ATR stop 1.5...")
    configs.append(run_v2_atr_stop(df, "ATR stop 1.5", {'atr_stop_buffer': 1.5}))

    # ── 3. ATR stop 1.0 ──
    print("3/8  ATR stop 1.0...")
    configs.append(run_v2_atr_stop(df, "ATR stop 1.0", {'atr_stop_buffer': 1.0}))

    # ── 4. Higher swing strength (4) for more significant levels ──
    print("4/8  Swing strength=4...")
    configs.append(run_v2(df, "swing_strength=4", {'swing_strength': 4}))

    # ── 5. Swing strength=4 + ATR stop ──
    print("5/8  Strength=4 + ATR stop...")
    configs.append(run_v2_atr_stop(df, "str=4 + ATR stop 1.5", {
        'swing_strength': 4,
        'atr_stop_buffer': 1.5,
    }))

    # ── 6. Very high touch req (5+) — major levels only ──
    print("6/8  5+ touches only...")
    configs.append(run_v2(df, "touch>=5 only", {
        'min_touches_pullback': 5,
        'min_touches_triple': 6,
        'failure_lookback': 0,
    }))

    # ── 7. Allow counter-trend ──
    print("7/8  Counter-trend allowed...")
    configs.append(run_v2(df, "counter-trend ON", {'trade_with_trend': False}))

    # ── 8. Best combo: str=4 + ATR stop + tight SR + strict bar ──
    print("8/8  Best combo...")
    configs.append(run_v2_atr_stop(df, "BEST COMBO: str4+ATR+tight", {
        'swing_strength': 4,
        'atr_stop_buffer': 1.5,
        'sr_tolerance_atr': 0.5,
        'signal_bar_close_pct': 0.30,
        'signal_bar_body_pct': 0.25,
        'min_touches_pullback': 3,
        'min_touches_triple': 4,
        'failure_lookback': 0,
    }))

    # ── Print results ──
    print(f"\n{'='*110}")
    print(f"  V2 SWEEP ROUND 2 — RADICAL CHANGES")
    print(f"{'='*110}")
    print(f"\n{'Label':40s} {'N':>6s} {'T/Day':>6s} {'WR':>6s} {'PF':>7s} "
          f"{'P&L':>10s} {'$/Yr':>9s} {'Sharpe':>7s} {'MaxDD':>9s} "
          f"{'AvgWin':>8s} {'AvgLoss':>8s} {'W/L':>5s}")
    print(f"{'-'*40} {'-'*6} {'-'*6} {'-'*6} {'-'*7} "
          f"{'-'*10} {'-'*9} {'-'*7} {'-'*9} "
          f"{'-'*8} {'-'*8} {'-'*5}")

    for c in configs:
        wl = abs(c['avg_win'] / c['avg_loss']) if c['avg_loss'] != 0 else 0
        print(f"{c['label']:40s} {c['trades']:6d} {c['trades_per_day']:5.2f} "
              f"{c['win_rate']:5.1f}% {c['profit_factor']:7.4f} "
              f"${c['total_pnl']:9,.0f} ${c['pnl_per_year']:8,.0f} "
              f"{c['sharpe']:7.4f} ${c['max_drawdown']:8,.0f} "
              f"${c['avg_win']:6.1f} ${c['avg_loss']:6.1f} {wl:5.2f}")

    print(f"\n{'='*110}")

    out_path = Path(__file__).parent.parent / 'analysis' / 'mitch_v2_sweep2_results.json'
    with open(out_path, 'w') as f:
        json.dump({'configs': configs}, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == '__main__':
    main()
