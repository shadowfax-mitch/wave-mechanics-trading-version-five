#!/usr/bin/env python3
"""
V2 Parameter Sweep — Find viable configurations.

Tests key parameter variations to see if the S/R price action concept
can be made profitable.
"""

import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mitch_v2_strategy import run_strategy, DEFAULT_V2_PARAMS


def load_data():
    data_dir = Path.home() / '.openclaw' / 'workspace' / 'data'
    path = data_dir / 'MNQ_5min.csv'
    df = pd.read_csv(path, parse_dates=['time'], index_col='time')
    df.columns = [c.lower() for c in df.columns]
    return df


def run_config(df, label, overrides):
    params = dict(DEFAULT_V2_PARAMS)
    params.update(overrides)
    result = run_strategy(df, params)
    s = result['stats']
    return {
        'label': label,
        'trades': s['total_trades'],
        'signals': s.get('total_signals', 0),
        'fill_rate': s.get('fill_rate', 0),
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
        'long_pnl': s.get('long_pnl', 0),
        'short_pnl': s.get('short_pnl', 0),
    }


def main():
    print("Loading data...")
    df = load_data()
    print(f"  {len(df):,} bars\n")

    configs = []

    # ── 1. BASELINE (default params) ──
    print("1/10 Baseline...")
    configs.append(run_config(df, "BASELINE (defaults)", {}))

    # ── 2. Wider min stop (0.5 ATR instead of 0.3) ──
    print("2/10 Wider min stop...")
    configs.append(run_config(df, "min_stop=0.5 ATR", {'min_stop_atr': 0.5}))

    # ── 3. Wider min stop (0.8 ATR) ──
    print("3/10 Even wider stop...")
    configs.append(run_config(df, "min_stop=0.8 ATR", {'min_stop_atr': 0.8}))

    # ── 4. Tighter S/R tolerance (0.5 ATR) ──
    print("4/10 Tighter S/R...")
    configs.append(run_config(df, "sr_tol=0.5 ATR", {'sr_tolerance_atr': 0.5}))

    # ── 5. Require 3 touches for pullback ──
    print("5/10 3-touch pullback...")
    configs.append(run_config(df, "min_touch=3", {'min_touches_pullback': 3, 'min_touches_triple': 4}))

    # ── 6. No failure pattern (pullback + triple only) ──
    print("6/10 No failures...")
    configs.append(run_config(df, "no_failure (lookback=0)", {'failure_lookback': 0}))

    # ── 7. Combo: tighter SR + wider stop + 3 touch ──
    print("7/10 Combo tight...")
    configs.append(run_config(df, "COMBO: sr=0.5 + stop=0.8 + touch=3", {
        'sr_tolerance_atr': 0.5,
        'min_stop_atr': 0.8,
        'min_touches_pullback': 3,
        'min_touches_triple': 4,
    }))

    # ── 8. Combo + no range trading ──
    print("8/10 Combo + trend only...")
    configs.append(run_config(df, "COMBO + trend_only (no range)", {
        'sr_tolerance_atr': 0.5,
        'min_stop_atr': 0.8,
        'min_touches_pullback': 3,
        'min_touches_triple': 4,
        'trade_with_trend': True,
    }))

    # ── 9. Stricter signal bar (close in top/bottom 30%) ──
    print("9/10 Strict signal bar...")
    configs.append(run_config(df, "strict_sigbar (close 30%)", {
        'signal_bar_close_pct': 0.30,
        'signal_bar_body_pct': 0.25,
    }))

    # ── 10. Kitchen sink: all quality filters maxed ──
    print("10/10 Kitchen sink...")
    configs.append(run_config(df, "KITCHEN SINK: all filters tight", {
        'sr_tolerance_atr': 0.5,
        'sr_cluster_atr': 0.3,
        'min_stop_atr': 0.8,
        'min_touches_pullback': 3,
        'min_touches_triple': 5,
        'failure_lookback': 0,
        'signal_bar_close_pct': 0.30,
        'signal_bar_body_pct': 0.25,
        'order_timeout': 1,
    }))

    # ── Print results ──
    print(f"\n{'='*100}")
    print(f"  V2 PARAMETER SWEEP RESULTS")
    print(f"{'='*100}")
    print(f"\n{'Label':42s} {'N':>6s} {'Sig':>6s} {'Fill%':>6s} {'T/Day':>6s} {'WR':>6s} "
          f"{'PF':>7s} {'P&L':>10s} {'$/Yr':>9s} {'Sharpe':>7s} {'MaxDD':>9s}")
    print(f"{'-'*42} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6} "
          f"{'-'*7} {'-'*10} {'-'*9} {'-'*7} {'-'*9}")

    for c in configs:
        print(f"{c['label']:42s} {c['trades']:6d} {c['signals']:6d} "
              f"{c['fill_rate']:5.1f}% {c['trades_per_day']:5.2f} "
              f"{c['win_rate']:5.1f}% {c['profit_factor']:7.4f} "
              f"${c['total_pnl']:9,.0f} ${c['pnl_per_year']:8,.0f} "
              f"{c['sharpe']:7.4f} ${c['max_drawdown']:8,.0f}")

    print(f"\n{'Label':42s} {'AvgWin':>8s} {'AvgLoss':>8s} {'W/L':>6s} {'AvgBars':>7s} "
          f"{'LongPnL':>10s} {'ShortPnL':>10s}")
    print(f"{'-'*42} {'-'*8} {'-'*8} {'-'*6} {'-'*7} {'-'*10} {'-'*10}")

    for c in configs:
        wl = abs(c['avg_win'] / c['avg_loss']) if c['avg_loss'] != 0 else 0
        print(f"{c['label']:42s} ${c['avg_win']:6.1f} ${c['avg_loss']:6.1f} "
              f"{wl:6.2f} {c['avg_bars']:6.1f} "
              f"${c['long_pnl']:9,.0f} ${c['short_pnl']:9,.0f}")

    # Save
    out_path = Path(__file__).parent.parent / 'analysis' / 'mitch_v2_sweep_results.json'
    with open(out_path, 'w') as f:
        json.dump({'configs': configs}, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == '__main__':
    main()
