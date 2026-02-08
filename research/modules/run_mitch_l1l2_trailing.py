#!/usr/bin/env python3
"""
Mitch L1+L2 — Fixed Stops vs Structure-Based Trailing Stops

A/B comparison:
  A: Fixed stop (best params from sweep: noEMA, stop_buf=1.5, tgt=3.0)
  B: Trailing stop variants (breakeven + trail behind swings)

Trail variants tested:
  - Trail buffer: 0.2, 0.3, 0.5 ATR
  - With/without breakeven
  - Trail + target (hybrid) vs trail-only (no fixed target)
  - Max hold: 30, 60, 90 bars (trail needs room to work)
"""

import sys
import json
import time
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mitch_l1l2_strategy import (
    precompute_indicators, detect_trend_and_entries,
    backtest, backtest_trailing, calculate_statistics, DEFAULT_PARAMS,
)


def fmt_stats(label, stats):
    """One-line summary."""
    return (f"  {label:40s} "
            f"Trades={stats['total_trades']:>5,} "
            f"WR={stats['win_rate']:>5.1f}% "
            f"PF={stats['profit_factor']:>6.4f} "
            f"PnL=${stats['total_pnl']:>10,.0f} "
            f"Sharpe={stats['sharpe']:>7.4f} "
            f"DD=${stats['max_drawdown']:>8,.0f} "
            f"AvgBars={stats['avg_bars_held']:>4.1f}")


def exit_breakdown(stats):
    """Compact exit reason line."""
    parts = []
    total = stats['total_trades']
    for reason in ['TARGET', 'STOP', 'TRAIL_STOP', 'TIME']:
        info = stats['exit_reasons'].get(reason, {'count': 0, 'pnl': 0})
        if info['count'] > 0:
            pct = info['count'] / total * 100
            avg = info['pnl'] / info['count']
            parts.append(f"{reason}={info['count']}({pct:.0f}%) avg${avg:.1f}")
    return "    Exits: " + " | ".join(parts)


def main():
    print("=" * 80)
    print("  MITCH L1+L2 — FIXED vs TRAILING STOPS COMPARISON")
    print("=" * 80)

    data_path = Path.home() / '.openclaw' / 'workspace' / 'data' / 'MNQ_5min.csv'
    df = pd.read_csv(data_path, parse_dates=['time'], index_col='time')
    df.index.name = 'timestamp'
    years = (df.index[-1] - df.index[0]).days / 365.25
    print(f"Loaded {len(df):,} bars, {years:.2f} years\n")

    # Best base params from sweep
    base = dict(DEFAULT_PARAMS)
    base['use_ema_confirmation'] = False
    base['stop_buffer_atr'] = 1.5
    base['target_atr_fallback'] = 3.0
    base['measured_move_cap_atr'] = 8.0

    # Precompute once
    data = precompute_indicators(df, base)
    signals = detect_trend_and_entries(data, base)

    results = []

    # ── BASELINE: Fixed stops ──
    print("=" * 80)
    print("  BASELINE: FIXED STOPS")
    print("=" * 80)

    for max_hold in [30, 60, 90]:
        p = dict(base)
        p['max_hold'] = max_hold
        trades = backtest(data, signals, p)
        stats = calculate_statistics(trades, years)
        label = f"FIXED stop=1.5 tgt=3.0 hold={max_hold}"
        print(fmt_stats(label, stats))
        print(exit_breakdown(stats))
        results.append({'mode': 'fixed', 'max_hold': max_hold,
                        'trail_buf': None, 'breakeven': None,
                        'trail_only': False, **stats})

    # ── TRAILING: Trail + Target (hybrid) ──
    print(f"\n{'='*80}")
    print("  TRAILING + TARGET (hybrid: trail tightens stop, target still active)")
    print("=" * 80)

    for trail_buf in [0.2, 0.3, 0.5, 0.8]:
        for max_hold in [30, 60, 90]:
            for use_be in [True, False]:
                p = dict(base)
                p['max_hold'] = max_hold
                p['trail_buffer_atr'] = trail_buf
                p['use_breakeven'] = use_be
                p['trail_only'] = False
                p['keep_target'] = True

                trades = backtest_trailing(data, signals, p)
                stats = calculate_statistics(trades, years)
                be_str = "BE" if use_be else "noBE"
                label = f"TRAIL buf={trail_buf} {be_str} hold={max_hold}"
                print(fmt_stats(label, stats))
                results.append({'mode': 'trail+target', 'max_hold': max_hold,
                                'trail_buf': trail_buf, 'breakeven': use_be,
                                'trail_only': False, **stats})

    # ── TRAILING: Trail-only (no fixed target, let winners ride) ──
    print(f"\n{'='*80}")
    print("  TRAIL-ONLY (no fixed target — trail stop is the only exit)")
    print("=" * 80)

    for trail_buf in [0.2, 0.3, 0.5, 0.8]:
        for max_hold in [30, 60, 90]:
            p = dict(base)
            p['max_hold'] = max_hold
            p['trail_buffer_atr'] = trail_buf
            p['use_breakeven'] = True
            p['trail_only'] = True

            trades = backtest_trailing(data, signals, p)
            stats = calculate_statistics(trades, years)
            label = f"TRAIL-ONLY buf={trail_buf} hold={max_hold}"
            print(fmt_stats(label, stats))
            results.append({'mode': 'trail_only', 'max_hold': max_hold,
                            'trail_buf': trail_buf, 'breakeven': True,
                            'trail_only': True, **stats})

    # ── SUMMARY: Best configs ──
    rdf = pd.DataFrame(results)

    print(f"\n{'='*80}")
    print("  TOP 10 OVERALL BY PROFIT FACTOR")
    print("=" * 80)
    top = rdf.nlargest(10, 'profit_factor')
    for _, r in top.iterrows():
        label = f"{r['mode']:15s} buf={r['trail_buf']} be={r['breakeven']} hold={r['max_hold']}"
        print(f"  PF={r['profit_factor']:.4f} WR={r['win_rate']:.1f}% "
              f"Trades={r['total_trades']:,} PnL=${r['total_pnl']:,.0f} "
              f"Sharpe={r['sharpe']:.4f} DD=${r['max_drawdown']:,.0f} "
              f"AvgBars={r['avg_bars_held']:.1f}")
        print(f"    {label}")

    # ── Side-by-side: best fixed vs best trail ──
    print(f"\n{'='*80}")
    print("  HEAD-TO-HEAD: BEST FIXED vs BEST TRAILING")
    print("=" * 80)

    best_fixed = rdf[rdf['mode'] == 'fixed'].nlargest(1, 'profit_factor').iloc[0]
    best_trail = rdf[rdf['mode'] != 'fixed'].nlargest(1, 'profit_factor').iloc[0]

    metrics = ['total_trades', 'win_rate', 'profit_factor', 'total_pnl',
               'avg_pnl', 'sharpe', 'max_drawdown', 'avg_bars_held',
               'trades_per_day']

    print(f"  {'Metric':20s} {'FIXED':>12s} {'TRAILING':>12s} {'DELTA':>12s}")
    print(f"  {'-'*56}")
    for m in metrics:
        fv = best_fixed[m]
        tv = best_trail[m]
        delta = tv - fv
        if m in ['total_pnl', 'avg_pnl', 'max_drawdown']:
            print(f"  {m:20s} ${fv:>11,.2f} ${tv:>11,.2f} ${delta:>+11,.2f}")
        elif m in ['win_rate']:
            print(f"  {m:20s} {fv:>11.2f}% {tv:>11.2f}% {delta:>+11.2f}%")
        else:
            print(f"  {m:20s} {fv:>12.4f} {tv:>12.4f} {delta:>+12.4f}")

    print(f"\n  Fixed config:   hold={best_fixed['max_hold']}")
    print(f"  Trail config:   {best_trail['mode']} buf={best_trail['trail_buf']} "
          f"be={best_trail['breakeven']} hold={best_trail['max_hold']}")

    # ── Parameter sensitivity for trailing ──
    print(f"\n{'='*80}")
    print("  TRAILING PARAMETER SENSITIVITY")
    print("=" * 80)

    trail_rows = rdf[rdf['mode'] != 'fixed']
    for param in ['trail_buf', 'max_hold', 'mode', 'breakeven']:
        groups = trail_rows.groupby(param).agg({
            'profit_factor': 'mean',
            'win_rate': 'mean',
            'total_pnl': 'mean',
            'avg_bars_held': 'mean',
        }).round(4)
        spread = groups['profit_factor'].max() - groups['profit_factor'].min()
        print(f"\n  {param} (PF spread: {spread:.4f})")
        for val, row in groups.iterrows():
            print(f"    {str(val):10s} → PF={row['profit_factor']:.4f} "
                  f"WR={row['win_rate']:.1f}% "
                  f"PnL=${row['total_pnl']:,.0f} "
                  f"AvgBars={row['avg_bars_held']:.1f}")

    # ── Save ──
    out_dir = Path.home() / '.openclaw' / 'workspace' / 'research' / 'analysis'
    out_file = out_dir / 'mitch_l1l2_trailing.json'
    save = {
        'best_fixed': best_fixed.to_dict(),
        'best_trailing': best_trail.to_dict(),
        'total_configs': len(rdf),
    }
    with open(out_file, 'w') as f:
        json.dump(save, f, indent=2, default=str)
    print(f"\nSaved to {out_file.relative_to(Path.home() / '.openclaw' / 'workspace' / 'research')}")
    print("=" * 80)


if __name__ == '__main__':
    main()
