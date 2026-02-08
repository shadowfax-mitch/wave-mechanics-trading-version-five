#!/usr/bin/env python3
"""
Mitch Grid Limit Orders — 4 Approaches to Boost Trade Frequency

Baseline: Ultra(8) LIMIT timeout=5 → 479 trades / 6.69yr = 72/yr

Option 1: ALL_PROFITABLE_FINE (10 cells) with limit orders
Option 2: Relaxed timeouts (10, 20) for Ultra(8) and Fine(6)
Option 3: MES data — same strategy on correlated instrument
Option 4: No grid filter — limit orders as the sole quality gate
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
    GRID_PARAMS, STABLE_FINE_CELLS, STABLE_ULTRA_CELLS, ALL_PROFITABLE_FINE_CELLS,
    precompute_indicators, detect_trend_and_entries,
    backtest_grid, backtest_grid_limit,
)
from mitch_l1l2_strategy import calculate_statistics


def section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")


def fmt_row(label, stats):
    return (f"  {label:50s} "
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
    if total == 0:
        return "    No trades"
    for reason in ['TRAIL_STOP', 'STOP', 'TIME']:
        info = stats['exit_reasons'].get(reason, {'count': 0, 'pnl': 0})
        if info['count'] > 0:
            pct = info['count'] / total * 100
            avg = info['pnl'] / info['count']
            parts.append(f"{reason}={info['count']}({pct:.0f}%) ${avg:.1f}")
    return "    " + " | ".join(parts)


def yearly_table(stats, label):
    print(f"\n  {label} — Yearly:")
    print(f"  {'Year':6s} {'N':>6s} {'WR':>8s} {'PnL':>10s}")
    for yr in sorted(stats['yearly'].keys()):
        y = stats['yearly'][yr]
        print(f"  {yr:6s} {y['count']:>6,} {y['win_rate']:>7.2f}% ${y['pnl']:>9,.2f}")


def cell_breakdown(trades, label):
    if not trades:
        print(f"\n  {label}: No trades")
        return
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
    print(f"  {'Cell':50s} {'N':>5s} {'WR':>6s} {'PF':>8s} {'PnL':>10s}")
    for cell, n, wr, pf, pnl in items:
        marker = " *" if pf >= 1.0 else ""
        print(f"  {cell:50s} {n:>5,} {wr:>5.1f}% {pf:>8.4f} ${pnl:>9,.2f}{marker}")


def run_backtest_limit(data, signals, years, grid_mode, cells, timeout, label):
    """Run a single limit-order backtest and return (trades, stats)."""
    p = dict(GRID_PARAMS)
    p['order_timeout'] = timeout
    trades = backtest_grid_limit(data, signals, p,
                                  grid_mode=grid_mode, allowed_cells=cells)
    stats = calculate_statistics(trades, years)
    return trades, stats


def run_backtest_limit_nofilter(data, signals, years, timeout, label):
    """Run limit-order backtest with ALL cells allowed (no grid filter)."""
    # Build a universal cell set that accepts everything
    # We do this by passing allowed_cells=None and patching the function
    # Actually, easier: generate all possible cell keys
    all_cells = set()
    ema_bkts = ['ema<-2', 'ema-2..-1', 'ema-1..0', 'ema0..1', 'ema1..2', 'ema>2']
    tods = ['open', 'morning', 'afternoon']
    dirs = ['LONG', 'SHORT']
    vols = ['low_vol', 'norm_vol', 'high_vol']

    for e in ema_bkts:
        for tod in tods:
            for d in dirs:
                all_cells.add(f"{e}|{tod}|{d}")
                for v in vols:
                    all_cells.add(f"{e}|{tod}|{d}|{v}")

    p = dict(GRID_PARAMS)
    p['order_timeout'] = timeout

    # Run with fine mode + all cells (covers all possible fine keys)
    trades = backtest_grid_limit(data, signals, p,
                                  grid_mode='fine', allowed_cells=all_cells)
    stats = calculate_statistics(trades, years)
    return trades, stats


def head_to_head(results_list):
    """Print head-to-head comparison table."""
    if not results_list:
        return

    print(f"\n  {'Config':50s} {'N':>6s} {'N/yr':>6s} {'WR':>7s} {'PF':>8s} "
          f"{'PnL':>10s} {'$/yr':>8s} {'Sharpe':>8s} {'DD':>8s} {'Bars':>6s}")
    print(f"  {'-'*118}")

    for label, stats, years in results_list:
        n = stats['total_trades']
        n_yr = n / years if years > 0 else 0
        pnl_yr = stats['total_pnl'] / years if years > 0 else 0
        print(f"  {label:50s} {n:>6,} {n_yr:>5.0f} "
              f"{stats['win_rate']:>6.1f}% {stats['profit_factor']:>8.4f} "
              f"${stats['total_pnl']:>9,.0f} ${pnl_yr:>7,.0f} "
              f"{stats['sharpe']:>8.4f} ${stats['max_drawdown']:>7,.0f} "
              f"{stats['avg_bars_held']:>5.1f}")


def main():
    print("=" * 80)
    print("  MITCH GRID — TRADE FREQUENCY BOOST (4 OPTIONS)")
    print("=" * 80)

    # ── Load MNQ data ──
    data_dir = Path.home() / '.openclaw' / 'workspace' / 'data'
    mnq_path = data_dir / 'MNQ_5min.csv'
    df_mnq = pd.read_csv(mnq_path, parse_dates=['time'], index_col='time')
    df_mnq.index.name = 'timestamp'
    years_mnq = (df_mnq.index[-1] - df_mnq.index[0]).days / 365.25
    print(f"  MNQ: {len(df_mnq):,} bars, {years_mnq:.2f} years")

    # ── Load MES data ──
    mes_path = data_dir / 'MES_5min.csv'
    df_mes = pd.read_csv(mes_path, parse_dates=['time'], index_col='time')
    df_mes.index.name = 'timestamp'
    years_mes = (df_mes.index[-1] - df_mes.index[0]).days / 365.25
    print(f"  MES: {len(df_mes):,} bars, {years_mes:.2f} years")

    # ── Precompute MNQ indicators (shared across all MNQ tests) ──
    print("\n  Precomputing MNQ indicators...")
    params = dict(GRID_PARAMS)
    data_mnq = precompute_indicators(df_mnq, params)
    signals_mnq = detect_trend_and_entries(data_mnq, params)

    # ── Precompute MES indicators ──
    print("  Precomputing MES indicators...")
    data_mes = precompute_indicators(df_mes, params)
    signals_mes = detect_trend_and_entries(data_mes, params)

    all_results = []  # (label, stats, years) for head-to-head

    # ──────────────────────────────────────────────
    # BASELINE: Ultra(8) LIMIT timeout=5 on MNQ
    # ──────────────────────────────────────────────
    section("BASELINE: Ultra(8) LIMIT timeout=5 on MNQ")
    trades_base, stats_base = run_backtest_limit(
        data_mnq, signals_mnq, years_mnq,
        'ultra', STABLE_ULTRA_CELLS, 5, "Baseline")
    print(fmt_row("Ultra(8) LIMIT t=5 [MNQ]", stats_base))
    print(exit_line(stats_base))
    all_results.append(("Ultra(8) LIMIT t=5 [MNQ] BASELINE", stats_base, years_mnq))

    # Also show Fine(6) baseline
    trades_fine_base, stats_fine_base = run_backtest_limit(
        data_mnq, signals_mnq, years_mnq,
        'fine', STABLE_FINE_CELLS, 5, "Fine baseline")
    print(fmt_row("Fine(6) LIMIT t=5 [MNQ]", stats_fine_base))
    all_results.append(("Fine(6) LIMIT t=5 [MNQ] BASELINE", stats_fine_base, years_mnq))

    # ──────────────────────────────────────────────
    # OPTION 1: ALL_PROFITABLE_FINE (10 cells) + limit orders
    # ──────────────────────────────────────────────
    section("OPTION 1: ALL_PROFITABLE_FINE (10 cells) + Limit Orders")
    print(f"  Cells: {sorted(ALL_PROFITABLE_FINE_CELLS)}")
    print(f"  Extra cells vs stable(6): {sorted(ALL_PROFITABLE_FINE_CELLS - STABLE_FINE_CELLS)}")

    for timeout in [3, 5, 10, 20]:
        trades, stats = run_backtest_limit(
            data_mnq, signals_mnq, years_mnq,
            'fine', ALL_PROFITABLE_FINE_CELLS, timeout,
            f"AllFine(10) t={timeout}")
        print(fmt_row(f"AllFine(10) LIMIT t={timeout} [MNQ]", stats))
        print(exit_line(stats))
        if timeout == 5:
            all_results.append((f"AllFine(10) LIMIT t=5 [MNQ]", stats, years_mnq))
            trades_opt1 = trades

    # Best timeout detail
    print()
    cell_breakdown(trades_opt1, "AllFine(10) LIMIT t=5")
    yearly_table(stats, "AllFine(10) LIMIT t=5")

    # ──────────────────────────────────────────────
    # OPTION 2: Relaxed timeouts (10, 20) for existing stable cells
    # ──────────────────────────────────────────────
    section("OPTION 2: Relaxed Timeouts for Stable Cells")

    for grid_mode, cells, cell_label in [
        ('fine', STABLE_FINE_CELLS, 'Fine(6)'),
        ('ultra', STABLE_ULTRA_CELLS, 'Ultra(8)'),
    ]:
        for timeout in [5, 10, 15, 20, 30]:
            trades, stats = run_backtest_limit(
                data_mnq, signals_mnq, years_mnq,
                grid_mode, cells, timeout,
                f"{cell_label} t={timeout}")
            print(fmt_row(f"{cell_label} LIMIT t={timeout} [MNQ]", stats))
            if timeout in [10, 20]:
                all_results.append((f"{cell_label} LIMIT t={timeout} [MNQ]", stats, years_mnq))

    # ──────────────────────────────────────────────
    # OPTION 3: MES data — same strategy
    # ──────────────────────────────────────────────
    section("OPTION 3: MES Data — Same Stable Cells + Limit Orders")
    print(f"  Note: MES uses same point_value=1.0 (each point = $1.25 in real MES)")

    # MES market order baseline first
    trades_mes_mkt = backtest_grid(data_mes, signals_mes, params,
                                    grid_mode='ultra', allowed_cells=STABLE_ULTRA_CELLS)
    stats_mes_mkt = calculate_statistics(trades_mes_mkt, years_mes)
    print(fmt_row("Ultra(8) MARKET [MES]", stats_mes_mkt))
    print(exit_line(stats_mes_mkt))

    for grid_mode, cells, cell_label in [
        ('fine', STABLE_FINE_CELLS, 'Fine(6)'),
        ('ultra', STABLE_ULTRA_CELLS, 'Ultra(8)'),
    ]:
        for timeout in [3, 5, 10, 20]:
            trades, stats = run_backtest_limit(
                data_mes, signals_mes, years_mes,
                grid_mode, cells, timeout,
                f"{cell_label} MES t={timeout}")
            print(fmt_row(f"{cell_label} LIMIT t={timeout} [MES]", stats))
            if timeout == 5:
                all_results.append((f"{cell_label} LIMIT t=5 [MES]", stats, years_mes))
                if cell_label == 'Ultra(8)':
                    trades_mes_best = trades
                    stats_mes_best = stats

    # MES detail for best config
    if 'trades_mes_best' in dir():
        print()
        cell_breakdown(trades_mes_best, "Ultra(8) LIMIT t=5 [MES]")
        yearly_table(stats_mes_best, "Ultra(8) LIMIT t=5 [MES]")

    # ──────────────────────────────────────────────
    # OPTION 4: No grid filter — limit orders only
    # ──────────────────────────────────────────────
    section("OPTION 4: No Grid Filter — Limit Orders as Sole Quality Gate")

    for timeout in [3, 5, 10, 20]:
        # MNQ
        trades, stats = run_backtest_limit_nofilter(
            data_mnq, signals_mnq, years_mnq,
            timeout, f"NoGrid MNQ t={timeout}")
        print(fmt_row(f"NO GRID LIMIT t={timeout} [MNQ]", stats))
        print(exit_line(stats))
        if timeout == 5:
            all_results.append((f"NO GRID LIMIT t=5 [MNQ]", stats, years_mnq))
            trades_nogrid_mnq = trades
            stats_nogrid_mnq = stats

    print()
    for timeout in [3, 5, 10, 20]:
        # MES
        trades, stats = run_backtest_limit_nofilter(
            data_mes, signals_mes, years_mes,
            timeout, f"NoGrid MES t={timeout}")
        print(fmt_row(f"NO GRID LIMIT t={timeout} [MES]", stats))
        print(exit_line(stats))
        if timeout == 5:
            all_results.append((f"NO GRID LIMIT t=5 [MES]", stats, years_mes))

    # NoGrid cell breakdown — which cells are driving the P&L?
    if 'trades_nogrid_mnq' in dir() and trades_nogrid_mnq:
        cell_breakdown(trades_nogrid_mnq, "NO GRID LIMIT t=5 [MNQ]")

    # ──────────────────────────────────────────────
    # COMBINED: MNQ + MES stacked
    # ──────────────────────────────────────────────
    section("COMBINED: MNQ + MES Stacked (Ultra(8) LIMIT t=5)")

    trades_mnq_u5, stats_mnq_u5 = run_backtest_limit(
        data_mnq, signals_mnq, years_mnq,
        'ultra', STABLE_ULTRA_CELLS, 5, "MNQ Ultra t=5")
    trades_mes_u5, stats_mes_u5 = run_backtest_limit(
        data_mes, signals_mes, years_mes,
        'ultra', STABLE_ULTRA_CELLS, 5, "MES Ultra t=5")

    # Combine P&Ls
    combined_pnls = ([t['pnl'] for t in trades_mnq_u5] +
                      [t['pnl'] for t in trades_mes_u5])
    combined_n = len(combined_pnls)
    if combined_n > 0:
        p = np.array(combined_pnls)
        wins = p[p > 0]
        losses = p[p < 0]
        gp = wins.sum() if len(wins) > 0 else 0
        gl = abs(losses.sum()) if len(losses) > 0 else 0
        pf = gp / gl if gl > 0 else (999.0 if gp > 0 else 0)
        wr = len(wins) / len(p) * 100

        # Equity curve for drawdown
        eq = np.cumsum(p)
        running_max = np.maximum.accumulate(eq)
        dd = (running_max - eq).max()

        combined_years = max(years_mnq, years_mes)  # same period
        sharpe = (p.mean() / p.std() * np.sqrt(252)) if p.std() > 0 else 0

        print(f"  MNQ trades:   {len(trades_mnq_u5):>6,}  PnL: ${sum(t['pnl'] for t in trades_mnq_u5):>9,.0f}")
        print(f"  MES trades:   {len(trades_mes_u5):>6,}  PnL: ${sum(t['pnl'] for t in trades_mes_u5):>9,.0f}")
        print(f"  Combined:     {combined_n:>6,}  PnL: ${p.sum():>9,.0f}")
        print(f"  Trades/year:  {combined_n / combined_years:>6.0f}")
        print(f"  Trades/day:   {combined_n / (combined_years * 252):>6.2f}")
        print(f"  Win Rate:     {wr:>6.1f}%")
        print(f"  Profit Factor:{pf:>7.4f}")
        print(f"  Sharpe:       {sharpe:>7.4f}")
        print(f"  Max Drawdown: ${dd:>7,.0f}")

        all_results.append(("MNQ+MES Ultra(8) LIMIT t=5 COMBINED",
                           {'total_trades': combined_n, 'win_rate': wr,
                            'profit_factor': pf, 'total_pnl': p.sum(),
                            'sharpe': sharpe, 'max_drawdown': dd,
                            'avg_bars_held': np.mean([t['bars_held'] for t in trades_mnq_u5 + trades_mes_u5]),
                            'avg_pnl': p.mean(),
                            'exit_reasons': {},
                            'yearly': {},
                           }, combined_years))

    # ──────────────────────────────────────────────
    # HEAD-TO-HEAD SUMMARY
    # ──────────────────────────────────────────────
    section("HEAD-TO-HEAD — ALL OPTIONS")
    head_to_head(all_results)

    # ── Save ──
    out_dir = Path.home() / '.openclaw' / 'workspace' / 'research' / 'analysis'
    out_file = out_dir / 'mitch_freq_boost_results.json'

    save_data = {
        'configs': [],
    }
    for label, stats, years in all_results:
        entry = {
            'label': label,
            'years': round(years, 2),
            'total_trades': stats['total_trades'],
            'trades_per_year': round(stats['total_trades'] / years, 1) if years > 0 else 0,
            'win_rate': round(stats['win_rate'], 2),
            'profit_factor': round(stats['profit_factor'], 4),
            'total_pnl': round(stats['total_pnl'], 2),
            'pnl_per_year': round(stats['total_pnl'] / years, 2) if years > 0 else 0,
            'sharpe': round(stats['sharpe'], 4),
            'max_drawdown': round(stats['max_drawdown'], 2),
            'avg_bars_held': round(stats.get('avg_bars_held', 0), 1),
        }
        save_data['configs'].append(entry)

    with open(out_file, 'w') as f:
        json.dump(save_data, f, indent=2, default=str)
    print(f"\n  Saved to {out_file.relative_to(Path.home() / '.openclaw' / 'workspace' / 'research')}")

    print("\n" + "=" * 80)
    print("  DONE")
    print("=" * 80)


if __name__ == '__main__':
    main()
