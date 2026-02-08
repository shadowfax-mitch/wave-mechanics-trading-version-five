#!/usr/bin/env python3
"""
Runner: Mitch Price Action System — Layer 1+2 Backtest

Loads MNQ 5-min data, runs the L1+2 backtest, prints a detailed report
with the critical A/B comparison: first entry vs second entry.
"""

import sys
import json
import time
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mitch_l1l2_strategy import run_strategy, DEFAULT_PARAMS


def print_section(title):
    print(f"\n{'='*65}")
    print(f"  {title}")
    print(f"{'='*65}")


def main():
    print("=" * 65)
    print("  MITCH PRICE ACTION — Layer 1+2: Structure + Second Entries")
    print("=" * 65)
    print("  Al Brooks: do second entries at trend structure levels have edge?")
    print()

    # ── Load data ──
    data_path = Path.home() / '.openclaw' / 'workspace' / 'data' / 'MNQ_5min.csv'
    print(f"Loading data from {data_path}...")
    df = pd.read_csv(data_path, parse_dates=['time'], index_col='time')
    df.index.name = 'timestamp'
    print(f"Loaded {len(df):,} bars ({df.index[0]} to {df.index[-1]})")

    years = (df.index[-1] - df.index[0]).days / 365.25
    print(f"Span: {years:.2f} years")

    # ── Run backtest ──
    print("\nRunning Layer 1+2 backtest...")
    t0 = time.time()
    results = run_strategy(df)
    elapsed = time.time() - t0
    print(f"Done in {elapsed:.1f}s")

    stats = results['stats']

    # ── Overall Metrics ──
    print_section("OVERALL METRICS")
    print(f"  Total Trades:     {stats['total_trades']:,}")
    print(f"  Win Rate:         {stats['win_rate']:.2f}%")
    print(f"  Profit Factor:    {stats['profit_factor']:.4f}")
    print(f"  Total P&L:        ${stats['total_pnl']:,.2f}")
    print(f"  Annual P&L:       ${stats['annual_pnl']:,.2f}")
    print(f"  Avg P&L/trade:    ${stats['avg_pnl']:.2f}")
    print(f"  Avg Win:          ${stats['avg_win']:.2f}")
    print(f"  Avg Loss:         ${stats['avg_loss']:.2f}")
    print(f"  Sharpe:           {stats['sharpe']:.4f}")
    print(f"  Max Drawdown:     ${stats['max_drawdown']:,.2f}")
    print(f"  Avg Bars Held:    {stats['avg_bars_held']:.1f}")
    print(f"  Trades/Day:       {stats['trades_per_day']:.2f}")
    print(f"  Trades/Year:      {stats['trades_per_year']:.1f}")

    # ── Long vs Short ──
    print_section("LONG vs SHORT BREAKDOWN")
    print(f"  {'':15s} {'LONG':>10s} {'SHORT':>10s}")
    print(f"  {'Trades':15s} {stats['long_trades']:>10,} {stats['short_trades']:>10,}")
    print(f"  {'Win Rate':15s} {stats['long_win_rate']:>9.2f}% {stats['short_win_rate']:>9.2f}%")
    print(f"  {'Total P&L':15s} ${stats['long_pnl']:>9,.2f} ${stats['short_pnl']:>9,.2f}")

    # ── A/B: First Entry vs Second Entry ──
    print_section("A/B TEST: FIRST ENTRY vs SECOND ENTRY")
    fe = stats['first_entry']
    se = stats['second_entry']
    print(f"  {'':15s} {'1st ENTRY':>12s} {'2nd ENTRY':>12s} {'DELTA':>10s}")
    print(f"  {'Trades':15s} {fe['count']:>12,} {se['count']:>12,}")
    print(f"  {'Win Rate':15s} {fe['win_rate']:>11.2f}% {se['win_rate']:>11.2f}% {se['win_rate']-fe['win_rate']:>+9.2f}%")
    print(f"  {'Profit Factor':15s} {fe['profit_factor']:>12.4f} {se['profit_factor']:>12.4f}")
    print(f"  {'Avg P&L':15s} ${fe['avg_pnl']:>11.2f} ${se['avg_pnl']:>11.2f} ${se['avg_pnl']-fe['avg_pnl']:>+9.2f}")
    print(f"  {'Total P&L':15s} ${fe['total_pnl']:>11.2f} ${se['total_pnl']:>11.2f}")
    print()
    if se['count'] > 0 and fe['count'] > 0:
        if se['win_rate'] > fe['win_rate'] and se['profit_factor'] > fe['profit_factor']:
            print("  >> VERDICT: Second entries OUTPERFORM first entries")
        elif se['win_rate'] < fe['win_rate'] and se['profit_factor'] < fe['profit_factor']:
            print("  >> VERDICT: First entries outperform — second entry filter NOT justified")
        else:
            print("  >> VERDICT: Mixed results — further analysis needed")

    # ── Exit Reason Breakdown ──
    print_section("EXIT REASON BREAKDOWN")
    for reason, info in sorted(stats['exit_reasons'].items()):
        pct = info['count'] / stats['total_trades'] * 100
        avg = info['pnl'] / info['count'] if info['count'] > 0 else 0
        print(f"  {reason:8s}  {info['count']:>5,} trades ({pct:5.1f}%)  "
              f"Total: ${info['pnl']:>10,.2f}  Avg: ${avg:>8.2f}")

    # ── Yearly P&L ──
    print_section("YEARLY P&L")
    print(f"  {'Year':6s} {'Trades':>8s} {'Win Rate':>10s} {'P&L':>12s}")
    for yr in sorted(stats['yearly'].keys()):
        y = stats['yearly'][yr]
        print(f"  {yr:6s} {y['count']:>8,} {y['win_rate']:>9.2f}% ${y['pnl']:>11,.2f}")

    # ── Save results ──
    out_dir = Path.home() / '.openclaw' / 'workspace' / 'research' / 'analysis'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / 'mitch_l1l2_results.json'

    # Make JSON-serializable (no numpy types)
    save_data = {
        'stats': stats,
        'params': results['params'],
        'trade_count': len(results['trades']),
        'sample_trades': results['trades'][:20] if results['trades'] else [],
    }
    with open(out_file, 'w') as f:
        json.dump(save_data, f, indent=2, default=str)

    print(f"\nResults saved to {out_file.relative_to(Path.home() / '.openclaw' / 'workspace' / 'research')}")
    print("=" * 65)
    print("DONE")
    print("=" * 65)


if __name__ == '__main__':
    main()
