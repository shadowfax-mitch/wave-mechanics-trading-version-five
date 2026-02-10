#!/usr/bin/env python3
"""
Run Mitch V2 Strategy — S/R Price Action Backtest

Tests the V2 strategy on MNQ 5-min data:
  - S/R levels from swing point clusters
  - Signal bar quality filter
  - Stop order entry (buy stop above signal bar, sell stop below)
  - Trail-only exit with breakeven
  - Trades in trends AND ranges
  - Patterns: pullback (two legs), triple test, failure
"""

import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mitch_v2_strategy import run_strategy, DEFAULT_V2_PARAMS


def load_data(instrument='MNQ'):
    """Load 5-min bar data."""
    data_dir = Path.home() / '.openclaw' / 'workspace' / 'data'
    path = data_dir / f'{instrument}_5min.csv'
    print(f"Loading {path}...")
    df = pd.read_csv(path, parse_dates=['time'], index_col='time')
    df.columns = [c.lower() for c in df.columns]
    print(f"  {len(df):,} bars, {df.index[0].date()} to {df.index[-1].date()}")
    return df


def print_report(stats, label="V2 S/R PRICE ACTION"):
    """Print comprehensive backtest report."""
    print(f"\n{'='*65}")
    print(f"  {label}")
    print(f"{'='*65}")

    print(f"\n  OVERALL:")
    print(f"    Trades:         {stats['total_trades']}")
    print(f"    Signals:        {stats.get('total_signals', 'N/A')}")
    print(f"    Fills:          {stats.get('total_fills', 'N/A')}")
    print(f"    Fill Rate:      {stats.get('fill_rate', 'N/A')}%")
    print(f"    Win Rate:       {stats['win_rate']:.1f}%")
    print(f"    Profit Factor:  {stats['profit_factor']:.4f}")
    print(f"    Total P&L:      ${stats['total_pnl']:,.2f}")
    print(f"    Annual P&L:     ${stats.get('annual_pnl', 0):,.2f}")
    print(f"    Sharpe:         {stats['sharpe']:.4f}")
    print(f"    Max Drawdown:   ${stats['max_drawdown']:,.2f}")
    print(f"    Avg Win:        ${stats['avg_win']:,.2f}")
    print(f"    Avg Loss:       ${stats['avg_loss']:,.2f}")
    print(f"    Avg Bars Held:  {stats.get('avg_bars_held', 0):.1f}")
    print(f"    Trades/Year:    {stats.get('trades_per_year', 0):.1f}")
    print(f"    Trades/Day:     {stats.get('trades_per_day', 0):.2f}")

    print(f"\n  LONG vs SHORT:")
    print(f"    {'':15s} {'Long':>10s} {'Short':>10s}")
    print(f"    {'Trades':15s} {stats.get('long_trades', 0):10d} {stats.get('short_trades', 0):10d}")
    print(f"    {'Win Rate':15s} {stats.get('long_win_rate', 0):9.1f}% {stats.get('short_win_rate', 0):9.1f}%")
    print(f"    {'P&L':15s} ${stats.get('long_pnl', 0):9,.2f} ${stats.get('short_pnl', 0):9,.2f}")

    # Pattern breakdown
    patterns = stats.get('pattern_breakdown', {})
    if patterns:
        print(f"\n  PATTERN BREAKDOWN:")
        print(f"    {'Pattern':15s} {'N':>6s} {'WR':>7s} {'Avg P&L':>10s} {'Total P&L':>11s}")
        for p in sorted(patterns.keys(), key=lambda k: patterns[k]['count'], reverse=True):
            d = patterns[p]
            print(f"    {p:15s} {d['count']:6d} {d['win_rate']:6.1f}% ${d['avg_pnl']:9.2f} ${d['pnl']:10,.2f}")

    # Trend breakdown
    trend_stats = stats.get('trend_breakdown', {})
    if trend_stats:
        print(f"\n  TREND STATE BREAKDOWN:")
        print(f"    {'State':15s} {'N':>6s} {'WR':>7s} {'Avg P&L':>10s} {'Total P&L':>11s}")
        for ts in sorted(trend_stats.keys(), key=lambda k: trend_stats[k]['count'], reverse=True):
            d = trend_stats[ts]
            print(f"    {ts:15s} {d['count']:6d} {d['win_rate']:6.1f}% ${d['avg_pnl']:9.2f} ${d['pnl']:10,.2f}")

    # Exit reasons
    exits = stats.get('exit_reasons', {})
    if exits:
        print(f"\n  EXIT BREAKDOWN:")
        print(f"    {'Reason':15s} {'N':>6s} {'Total P&L':>11s} {'Avg P&L':>10s}")
        for r in sorted(exits.keys()):
            d = exits[r]
            avg = d['pnl'] / d['count'] if d['count'] > 0 else 0
            print(f"    {r:15s} {d['count']:6d} ${d['pnl']:10,.2f} ${avg:9.2f}")

    # Yearly
    yearly = stats.get('yearly', {})
    if yearly:
        print(f"\n  YEARLY P&L:")
        print(f"    {'Year':>6s} {'Trades':>7s} {'WR':>7s} {'P&L':>11s}")
        for yr in sorted(yearly.keys()):
            d = yearly[yr]
            print(f"    {yr:>6s} {d['count']:7d} {d['win_rate']:6.1f}% ${d['pnl']:10,.2f}")

    print(f"\n{'='*65}")


def main():
    df = load_data('MNQ')

    params = dict(DEFAULT_V2_PARAMS)

    print("\nRunning V2 S/R Price Action backtest...")
    result = run_strategy(df, params)
    stats = result['stats']

    print_report(stats)

    # Save results
    out_dir = Path(__file__).parent.parent / 'analysis'
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / 'mitch_v2_results.json'

    save_stats = {k: v for k, v in stats.items()}
    with open(out_path, 'w') as f:
        json.dump(save_stats, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


if __name__ == '__main__':
    main()
