#!/usr/bin/env python3
"""
Mitch Grid Strategy — Market Orders vs Limit Orders at Structure Levels

A/B comparison:
  A: Market order at next bar's open (current approach)
  B: Limit order at swing price level (fill on wick penetration)

Limit order advantages:
  - Better fill price (at the pullback, not chasing)
  - No entry slippage
  - Natural filter: signals where price runs away don't fill

Tests multiple order_timeout values (3, 5, 10, 20 bars).
Runs both fine and ultra grid modes.
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
    GRID_PARAMS, STABLE_FINE_CELLS, STABLE_ULTRA_CELLS,
    precompute_indicators, detect_trend_and_entries,
    backtest_grid, backtest_grid_limit,
)
from mitch_l1l2_strategy import calculate_statistics


def section(title):
    print(f"\n{'='*75}")
    print(f"  {title}")
    print(f"{'='*75}")


def fmt(label, stats):
    return (f"  {label:45s} "
            f"N={stats['total_trades']:>5,} "
            f"WR={stats['win_rate']:>5.1f}% "
            f"PF={stats['profit_factor']:>6.4f} "
            f"PnL=${stats['total_pnl']:>9,.0f} "
            f"Sharpe={stats['sharpe']:>7.4f} "
            f"DD=${stats['max_drawdown']:>7,.0f} "
            f"Bars={stats['avg_bars_held']:>4.1f}")


def exit_line(stats):
    parts = []
    total = stats['total_trades']
    for reason in ['TRAIL_STOP', 'STOP', 'TIME']:
        info = stats['exit_reasons'].get(reason, {'count': 0, 'pnl': 0})
        if info['count'] > 0:
            pct = info['count'] / total * 100
            avg = info['pnl'] / info['count']
            parts.append(f"{reason}={info['count']}({pct:.0f}%) ${avg:.1f}")
    return "    " + " | ".join(parts)


def cell_breakdown(trades, label):
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
    print(f"\n  {label} — Cell Breakdown:")
    print(f"  {'Cell':45s} {'N':>5s} {'WR':>6s} {'PF':>8s} {'PnL':>10s}")
    for cell, n, wr, pf, pnl in items:
        marker = " *" if pf >= 1.0 else ""
        print(f"  {cell:45s} {n:>5,} {wr:>5.1f}% {pf:>8.4f} ${pnl:>9,.2f}{marker}")


def yearly_table(stats, label):
    print(f"\n  {label} — Yearly:")
    print(f"  {'Year':6s} {'N':>6s} {'WR':>8s} {'PnL':>10s}")
    for yr in sorted(stats['yearly'].keys()):
        y = stats['yearly'][yr]
        print(f"  {yr:6s} {y['count']:>6,} {y['win_rate']:>7.2f}% ${y['pnl']:>9,.2f}")


def main():
    print("=" * 75)
    print("  MITCH GRID — MARKET vs LIMIT ORDER ENTRIES")
    print("=" * 75)

    data_path = Path.home() / '.openclaw' / 'workspace' / 'data' / 'MNQ_5min.csv'
    df = pd.read_csv(data_path, parse_dates=['time'], index_col='time')
    df.index.name = 'timestamp'
    years = (df.index[-1] - df.index[0]).days / 365.25
    print(f"  Data: {len(df):,} bars, {years:.2f} years\n")

    # Precompute once
    params = dict(GRID_PARAMS)
    data = precompute_indicators(df, params)
    signals = detect_trend_and_entries(data, params)

    all_results = []

    for grid_mode, cells, cell_label in [
        ('fine', STABLE_FINE_CELLS, 'Fine(6)'),
        ('ultra', STABLE_ULTRA_CELLS, 'Ultra(8)'),
    ]:
        section(f"{cell_label} — MARKET ORDER BASELINE")

        # Market order baseline
        t0 = time.time()
        trades_mkt = backtest_grid(data, signals, params,
                                   grid_mode=grid_mode, allowed_cells=cells)
        stats_mkt = calculate_statistics(trades_mkt, years)
        elapsed = time.time() - t0

        label = f"{cell_label} MARKET"
        print(fmt(label, stats_mkt))
        print(exit_line(stats_mkt))
        all_results.append({
            'mode': 'market', 'grid': cell_label,
            'timeout': 0, **stats_mkt})

        # Limit order variants
        section(f"{cell_label} — LIMIT ORDERS (by timeout)")
        for timeout in [3, 5, 10, 20]:
            p = dict(params)
            p['order_timeout'] = timeout

            t0 = time.time()
            trades_lim = backtest_grid_limit(data, signals, p,
                                             grid_mode=grid_mode,
                                             allowed_cells=cells)
            stats_lim = calculate_statistics(trades_lim, years)
            elapsed = time.time() - t0

            label = f"{cell_label} LIMIT timeout={timeout}"
            print(fmt(label, stats_lim))
            print(exit_line(stats_lim))

            if stats_lim['total_trades'] > 0:
                fill_rate = stats_lim['total_trades'] / max(stats_mkt['total_trades'], 1) * 100
                print(f"    Fill rate vs market: {fill_rate:.1f}%")

            all_results.append({
                'mode': 'limit', 'grid': cell_label,
                'timeout': timeout, **stats_lim})

    # ── Head-to-head: best market vs best limit ──
    rdf = pd.DataFrame(all_results)

    section("BEST MARKET vs BEST LIMIT — HEAD TO HEAD")

    for grid_label in ['Fine(6)', 'Ultra(8)']:
        subset = rdf[rdf['grid'] == grid_label]
        mkt = subset[subset['mode'] == 'market'].iloc[0]
        lim_rows = subset[subset['mode'] == 'limit']
        if len(lim_rows) == 0:
            continue
        best_lim = lim_rows.loc[lim_rows['profit_factor'].idxmax()]

        print(f"\n  {grid_label}:")
        metrics = [
            ('Trades', 'total_trades', '{}'),
            ('Win Rate', 'win_rate', '{:.2f}%'),
            ('Profit Factor', 'profit_factor', '{:.4f}'),
            ('Total PnL', 'total_pnl', '${:,.0f}'),
            ('Avg PnL', 'avg_pnl', '${:.2f}'),
            ('Sharpe', 'sharpe', '{:.4f}'),
            ('Max DD', 'max_drawdown', '${:,.0f}'),
            ('Trades/Day', 'trades_per_day', '{:.2f}'),
            ('Avg Bars', 'avg_bars_held', '{:.1f}'),
        ]
        print(f"  {'Metric':16s} {'MARKET':>12s} {'LIMIT':>12s} {'DELTA':>12s}")
        print(f"  {'-'*52}")
        for name, key, f in metrics:
            mv = mkt[key]
            lv = best_lim[key]
            delta = lv - mv
            ms = f.format(mv)
            ls = f.format(lv)
            ds = f.format(delta) if 'pnl' not in key.lower() else f'${delta:+,.0f}'
            if key in ['total_pnl', 'avg_pnl', 'max_drawdown']:
                ds = f'${delta:+,.2f}'
            elif key == 'win_rate':
                ds = f'{delta:+.2f}%'
            elif key in ['profit_factor', 'sharpe', 'trades_per_day', 'avg_bars_held']:
                ds = f'{delta:+.4f}'
            else:
                ds = f'{delta:+.0f}'
            print(f"  {name:16s} {ms:>12s} {ls:>12s} {ds:>12s}")
        print(f"  Best limit timeout: {int(best_lim['timeout'])}")

    # ── Detailed breakdown for best limit config ──
    # Re-run to get trade objects for the best config
    for grid_mode, cells, cell_label in [
        ('fine', STABLE_FINE_CELLS, 'Fine(6)'),
        ('ultra', STABLE_ULTRA_CELLS, 'Ultra(8)'),
    ]:
        subset = rdf[rdf['grid'] == cell_label]
        lim_rows = subset[subset['mode'] == 'limit']
        if len(lim_rows) == 0:
            continue
        best_timeout = int(lim_rows.loc[lim_rows['profit_factor'].idxmax()]['timeout'])

        p = dict(params)
        p['order_timeout'] = best_timeout
        trades_best = backtest_grid_limit(data, signals, p,
                                          grid_mode=grid_mode,
                                          allowed_cells=cells)
        stats_best = calculate_statistics(trades_best, years)

        section(f"BEST LIMIT — {cell_label} timeout={best_timeout}")
        print(fmt(f"{cell_label} LIMIT t={best_timeout}", stats_best))

        # Direction split
        print(f"\n  {'':15s} {'LONG':>10s} {'SHORT':>10s}")
        print(f"  {'Trades':15s} {stats_best['long_trades']:>10,} {stats_best['short_trades']:>10,}")
        print(f"  {'Win Rate':15s} {stats_best['long_win_rate']:>9.2f}% {stats_best['short_win_rate']:>9.2f}%")
        print(f"  {'Total P&L':15s} ${stats_best['long_pnl']:>9,.2f} ${stats_best['short_pnl']:>9,.2f}")

        cell_breakdown(trades_best, f"{cell_label} LIMIT t={best_timeout}")
        yearly_table(stats_best, f"{cell_label} LIMIT t={best_timeout}")

    # ── Save ──
    out_dir = Path.home() / '.openclaw' / 'workspace' / 'research' / 'analysis'
    out_file = out_dir / 'mitch_grid_limit_results.json'
    save = {
        'results': all_results,
        'best_per_grid': {},
    }
    for grid_label in ['Fine(6)', 'Ultra(8)']:
        subset = rdf[rdf['grid'] == grid_label]
        best_overall = subset.loc[subset['profit_factor'].idxmax()]
        save['best_per_grid'][grid_label] = best_overall.to_dict()

    with open(out_file, 'w') as f:
        json.dump(save, f, indent=2, default=str)
    print(f"\nSaved to {out_file.relative_to(Path.home() / '.openclaw' / 'workspace' / 'research')}")
    print("=" * 75)


if __name__ == '__main__':
    main()
