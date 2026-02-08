#!/usr/bin/env python3
"""
Runner: Mitch Grid Strategy — Production Backtest

Runs the grid-filtered trail-only strategy on MNQ 5-min data.
Reports both fine (6-cell) and ultra (8-cell) stable grid results.
"""

import sys
import json
import time
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from mitch_grid_strategy import (
    run_grid_strategy, GRID_PARAMS,
    STABLE_FINE_CELLS, STABLE_ULTRA_CELLS, ALL_PROFITABLE_FINE_CELLS,
)


def section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def print_stats(stats):
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
    if stats['max_drawdown'] > 0:
        print(f"  Return/DD:        {stats['total_pnl'] / stats['max_drawdown']:.2f}x")


def print_direction_split(stats):
    print(f"  {'':15s} {'LONG':>10s} {'SHORT':>10s}")
    print(f"  {'Trades':15s} {stats['long_trades']:>10,} {stats['short_trades']:>10,}")
    print(f"  {'Win Rate':15s} {stats['long_win_rate']:>9.2f}% {stats['short_win_rate']:>9.2f}%")
    print(f"  {'Total P&L':15s} ${stats['long_pnl']:>9,.2f} ${stats['short_pnl']:>9,.2f}")


def print_exits(stats):
    total = stats['total_trades']
    for reason in ['TRAIL_STOP', 'STOP', 'TIME']:
        info = stats['exit_reasons'].get(reason, {'count': 0, 'pnl': 0})
        if info['count'] > 0:
            pct = info['count'] / total * 100
            avg = info['pnl'] / info['count']
            print(f"  {reason:12s}  {info['count']:>5,} ({pct:5.1f}%)  "
                  f"Total: ${info['pnl']:>10,.2f}  Avg: ${avg:>8.2f}")


def print_yearly(stats):
    print(f"  {'Year':6s} {'Trades':>8s} {'Win Rate':>10s} {'P&L':>12s}")
    for yr in sorted(stats['yearly'].keys()):
        y = stats['yearly'][yr]
        print(f"  {yr:6s} {y['count']:>8,} {y['win_rate']:>9.2f}% ${y['pnl']:>11,.2f}")


def print_cell_breakdown(trades):
    cells = defaultdict(list)
    for t in trades:
        cells[t['cell']].append(t['pnl'])

    items = []
    for cell, pnls in cells.items():
        p = np.array(pnls)
        wins = p[p > 0]
        losses = p[p < 0]
        gp = wins.sum() if len(wins) > 0 else 0
        gl = abs(losses.sum()) if len(losses) > 0 else 0
        pf = gp / gl if gl > 0 else (999.0 if gp > 0 else 0)
        items.append((cell, len(p), len(wins) / len(p) * 100, pf, p.sum()))

    items.sort(key=lambda x: x[3], reverse=True)
    print(f"  {'Cell':40s} {'N':>6s} {'WR':>7s} {'PF':>8s} {'PnL':>11s}")
    print(f"  {'-'*72}")
    for cell, n, wr, pf, pnl in items:
        print(f"  {cell:40s} {n:>6,} {wr:>6.1f}% {pf:>8.4f} ${pnl:>10,.2f}")


def main():
    print("=" * 70)
    print("  MITCH GRID STRATEGY — Production Backtest")
    print("=" * 70)

    data_path = Path.home() / '.openclaw' / 'workspace' / 'data' / 'MNQ_5min.csv'
    df = pd.read_csv(data_path, parse_dates=['time'], index_col='time')
    df.index.name = 'timestamp'
    years = (df.index[-1] - df.index[0]).days / 365.25
    print(f"  Data: {len(df):,} bars ({df.index[0].date()} to {df.index[-1].date()})")
    print(f"  Span: {years:.2f} years")

    # ── Run all three grid modes ──
    configs = [
        ('STABLE FINE (6 cells, split-validated)', 'fine', STABLE_FINE_CELLS),
        ('STABLE ULTRA (8 cells, split-validated)', 'ultra', STABLE_ULTRA_CELLS),
        ('ALL PROFITABLE FINE (10 cells, in-sample)', 'fine', ALL_PROFITABLE_FINE_CELLS),
    ]

    all_results = {}

    for label, mode, cells in configs:
        section(label)
        print(f"  Grid mode: {mode}")
        print(f"  Cells: {sorted(cells)}")

        t0 = time.time()
        result = run_grid_strategy(df, grid_mode=mode, allowed_cells=cells)
        elapsed = time.time() - t0
        print(f"  Runtime: {elapsed:.1f}s\n")

        stats = result['stats']
        all_results[label] = result

        print_stats(stats)

        section(f"{label} — DIRECTION SPLIT")
        print_direction_split(stats)

        section(f"{label} — EXIT REASONS")
        print_exits(stats)

        section(f"{label} — CELL BREAKDOWN")
        print_cell_breakdown(result['trades'])

        section(f"{label} — YEARLY P&L")
        print_yearly(stats)

    # ── Head-to-head comparison ──
    section("HEAD-TO-HEAD COMPARISON")
    labels = list(all_results.keys())
    metrics = [
        ('Trades', 'total_trades', '{:>10,}'),
        ('Win Rate', 'win_rate', '{:>9.2f}%'),
        ('Profit Factor', 'profit_factor', '{:>10.4f}'),
        ('Total PnL', 'total_pnl', '${:>9,.0f}'),
        ('Annual PnL', 'annual_pnl', '${:>9,.0f}'),
        ('Avg PnL', 'avg_pnl', '${:>9.2f}'),
        ('Sharpe', 'sharpe', '{:>10.4f}'),
        ('Max DD', 'max_drawdown', '${:>9,.0f}'),
        ('Trades/Day', 'trades_per_day', '{:>10.2f}'),
        ('Avg Bars', 'avg_bars_held', '{:>10.1f}'),
    ]

    col_w = 16
    header = f"  {'Metric':16s}"
    for lbl in labels:
        short = lbl.split('(')[0].strip()
        header += f" {short:>{col_w}s}"
    print(header)
    print(f"  {'-' * (16 + col_w * len(labels) + len(labels))}")

    for name, key, fmt in metrics:
        line = f"  {name:16s}"
        for lbl in labels:
            val = all_results[lbl]['stats'][key]
            line += f" {fmt.format(val):>{col_w}s}"
        print(line)

    # ── Save best result ──
    section("SAVING RESULTS")
    best_label = max(all_results.keys(),
                     key=lambda k: all_results[k]['stats']['profit_factor'])
    best = all_results[best_label]

    out_dir = Path.home() / '.openclaw' / 'workspace' / 'research' / 'analysis'
    out_dir.mkdir(parents=True, exist_ok=True)

    # Full results
    out_file = out_dir / 'mitch_grid_results.json'
    save_data = {
        'best_config': best_label,
        'grid_mode': best['grid_mode'],
        'cells_used': best['cells_used'],
        'params': best['params'],
        'stats': best['stats'],
        'sample_trades': best['trades'][:30],
        'all_configs': {
            lbl: {
                'grid_mode': r['grid_mode'],
                'cells_used': r['cells_used'],
                'stats': r['stats'],
            }
            for lbl, r in all_results.items()
        },
    }
    with open(out_file, 'w') as f:
        json.dump(save_data, f, indent=2, default=str)
    print(f"  Results saved to {out_file.relative_to(Path.home() / '.openclaw' / 'workspace' / 'research')}")

    # Trade log
    trade_file = out_dir / 'mitch_grid_trades.json'
    with open(trade_file, 'w') as f:
        json.dump(best['trades'], f, indent=1, default=str)
    print(f"  Trade log saved to {trade_file.relative_to(Path.home() / '.openclaw' / 'workspace' / 'research')}")

    print(f"\n  Best config: {best_label}")
    print("=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == '__main__':
    main()
