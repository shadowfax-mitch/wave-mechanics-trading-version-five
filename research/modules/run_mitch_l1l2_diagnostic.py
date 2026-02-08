#!/usr/bin/env python3
"""
Mitch L1+L2 Diagnostic — Where does the first-entry signal have edge?

Breaks down first-entry trades across multiple dimensions to find
conditional pockets of positive expectancy for grid exploitation.

Dimensions:
1. Trend state accuracy: do longs in uptrends beat longs in range/down?
2. EMA distance at entry: mean-reversion proximity
3. Time of day
4. ATR regime (expanding/contracting volatility)
5. Pullback depth (how far from the swing extreme)
6. Consecutive trend swings (trend "maturity")
"""

import sys
import json
import time
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from mitch_l1l2_strategy import (
    precompute_indicators, detect_trend_and_entries,
    backtest, calculate_statistics, DEFAULT_PARAMS,
    TREND_UP, TREND_DOWN, TREND_RANGE, TREND_UNKNOWN,
)


def bucket_stats(trades_in_bucket):
    """Quick stats for a bucket of trades."""
    if not trades_in_bucket:
        return None
    pnls = np.array([t['pnl'] for t in trades_in_bucket])
    n = len(pnls)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gp = wins.sum() if len(wins) > 0 else 0
    gl = abs(losses.sum()) if len(losses) > 0 else 0
    pf = gp / gl if gl > 0 else (999.0 if gp > 0 else 0)
    wr = len(wins) / n * 100
    return {
        'count': n,
        'win_rate': round(wr, 1),
        'profit_factor': round(pf, 4),
        'total_pnl': round(pnls.sum(), 2),
        'avg_pnl': round(pnls.mean(), 2),
    }


def print_bucket_table(title, buckets):
    """Print a table of bucket stats, sorted by PF descending."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")
    print(f"  {'Bucket':20s} {'Count':>7s} {'WR':>7s} {'PF':>8s} {'AvgPnL':>9s} {'TotalPnL':>11s}")
    print(f"  {'-'*62}")

    items = []
    for name, stats in buckets.items():
        if stats is not None:
            items.append((name, stats))

    # Sort by PF descending
    items.sort(key=lambda x: x[1]['profit_factor'], reverse=True)

    for name, s in items:
        marker = " <<<" if s['profit_factor'] >= 1.0 and s['count'] >= 30 else ""
        marker = " ***" if s['profit_factor'] >= 1.3 and s['count'] >= 30 else marker
        print(f"  {name:20s} {s['count']:>7,} {s['win_rate']:>6.1f}% {s['profit_factor']:>8.4f} "
              f"${s['avg_pnl']:>8.2f} ${s['total_pnl']:>10,.2f}{marker}")


def main():
    print("=" * 70)
    print("  MITCH L1+L2 — FIRST ENTRY DIAGNOSTIC")
    print("  Finding conditional pockets of edge for grid exploitation")
    print("=" * 70)

    data_path = Path.home() / '.openclaw' / 'workspace' / 'data' / 'MNQ_5min.csv'
    df = pd.read_csv(data_path, parse_dates=['time'], index_col='time')
    df.index.name = 'timestamp'
    years = (df.index[-1] - df.index[0]).days / 365.25
    print(f"Loaded {len(df):,} bars, {years:.2f} years\n")

    # Use best params from sweep: noEMA, stop_buf=1.5, tgt=3.0, cap=8.0
    params = dict(DEFAULT_PARAMS)
    params['use_ema_confirmation'] = False
    params['stop_buffer_atr'] = 1.5
    params['target_atr_fallback'] = 3.0
    params['measured_move_cap_atr'] = 8.0
    params['track_first_entries'] = True

    print("Params: noEMA, stop_buf=1.5, tgt=3.0, cap=8.0")
    print("Running backtest...")
    t0 = time.time()

    data = precompute_indicators(df, params)
    signals = detect_trend_and_entries(data, params)
    trades = backtest(data, signals, params)
    stats = calculate_statistics(trades, years)
    elapsed = time.time() - t0

    print(f"Done in {elapsed:.1f}s — {stats['total_trades']:,} trades, "
          f"PF={stats['profit_factor']:.4f}, WR={stats['win_rate']:.1f}%\n")

    # Filter to first entries only for this analysis
    first_trades = [t for t in trades if t['entry_type'] == 1]
    print(f"First-entry trades: {len(first_trades):,}")
    print(f"Second-entry trades: {len(trades) - len(first_trades):,}")
    print(f"\nAnalyzing first entries across multiple dimensions...\n")

    # Precompute per-trade metadata we'll need for bucketing
    atr = data['atr']
    ema = data['ema']
    close = data['close']
    high = data['high']
    low = data['low']
    time_f = data['time_f']
    trend_arr = signals['trend']

    for t in first_trades:
        bar = t['entry_bar']
        sig_bar = t['signal_bar']

        # EMA distance at entry (in ATR units)
        a = atr[bar]
        if a > 0 and not np.isnan(a) and not np.isnan(ema[bar]):
            t['ema_dist_atr'] = (close[bar] - ema[bar]) / a
        else:
            t['ema_dist_atr'] = np.nan

        # Time of day
        t['time_f'] = time_f[bar]

        # ATR regime: current ATR vs 50-bar rolling mean
        if bar >= 50:
            atr_mean = np.nanmean(atr[bar-50:bar])
            t['atr_ratio'] = a / atr_mean if atr_mean > 0 else 1.0
        else:
            t['atr_ratio'] = 1.0

        # Trend state at signal bar
        t['trend_state'] = int(trend_arr[sig_bar])

        # Pullback depth: distance from entry to the triggering extreme
        # (approximated by entry_price vs the recent swing)
        t['atr_at_entry'] = a

    # ──────────────────────────────────────────
    # DIMENSION 1: Trend state at entry
    # ──────────────────────────────────────────
    trend_names = {TREND_UP: 'UPTREND', TREND_DOWN: 'DOWNTREND',
                   TREND_RANGE: 'RANGE', TREND_UNKNOWN: 'UNKNOWN'}

    # Overall by trend state
    trend_buckets = {}
    for tstate, tname in trend_names.items():
        trades_in = [t for t in first_trades if t['trend_state'] == tstate]
        trend_buckets[tname] = bucket_stats(trades_in)
    print_bucket_table("DIMENSION 1: TREND STATE AT ENTRY", trend_buckets)

    # Trend state × direction
    td_buckets = {}
    for tstate, tname in trend_names.items():
        for direction in ['LONG', 'SHORT']:
            trades_in = [t for t in first_trades
                         if t['trend_state'] == tstate and t['direction'] == direction]
            key = f"{tname:10s} {direction}"
            td_buckets[key] = bucket_stats(trades_in)
    print_bucket_table("DIMENSION 1b: TREND STATE × DIRECTION", td_buckets)

    # ──────────────────────────────────────────
    # DIMENSION 2: EMA distance at entry
    # ──────────────────────────────────────────
    ema_buckets = {}
    valid_ema = [t for t in first_trades if not np.isnan(t['ema_dist_atr'])]

    # Bin by EMA distance
    ema_bins = [
        ('far_below (<-2)', lambda d: d < -2),
        ('below (-2 to -1)', lambda d: -2 <= d < -1),
        ('near_below (-1 to 0)', lambda d: -1 <= d < 0),
        ('near_above (0 to 1)', lambda d: 0 <= d < 1),
        ('above (1 to 2)', lambda d: 1 <= d < 2),
        ('far_above (>2)', lambda d: d >= 2),
    ]
    for name, filt in ema_bins:
        trades_in = [t for t in valid_ema if filt(t['ema_dist_atr'])]
        ema_buckets[name] = bucket_stats(trades_in)
    print_bucket_table("DIMENSION 2: EMA DISTANCE (ATR units)", ema_buckets)

    # EMA distance × direction
    ema_dir_buckets = {}
    for name, filt in ema_bins:
        for direction in ['LONG', 'SHORT']:
            trades_in = [t for t in valid_ema
                         if filt(t['ema_dist_atr']) and t['direction'] == direction]
            key = f"{name:22s} {direction}"
            ema_dir_buckets[key] = bucket_stats(trades_in)
    print_bucket_table("DIMENSION 2b: EMA DISTANCE × DIRECTION", ema_dir_buckets)

    # ──────────────────────────────────────────
    # DIMENSION 3: Time of day
    # ──────────────────────────────────────────
    tod_buckets = {}
    tod_bins = [
        ('08:30-09:30 open', lambda t: 8.5 <= t < 9.5),
        ('09:30-10:30 mid_morn', lambda t: 9.5 <= t < 10.5),
        ('10:30-12:00 late_morn', lambda t: 10.5 <= t < 12.0),
        ('12:00-13:30 lunch', lambda t: 12.0 <= t < 13.5),
        ('13:30-15:00 afternoon', lambda t: 13.5 <= t < 15.0),
    ]
    for name, filt in tod_bins:
        trades_in = [t for t in first_trades if filt(t['time_f'])]
        tod_buckets[name] = bucket_stats(trades_in)
    print_bucket_table("DIMENSION 3: TIME OF DAY", tod_buckets)

    # ──────────────────────────────────────────
    # DIMENSION 4: ATR regime (volatility)
    # ──────────────────────────────────────────
    atr_buckets = {}
    atr_bins = [
        ('low_vol (<0.8)', lambda r: r < 0.8),
        ('normal (0.8-1.2)', lambda r: 0.8 <= r < 1.2),
        ('high_vol (1.2-1.6)', lambda r: 1.2 <= r < 1.6),
        ('extreme (>1.6)', lambda r: r >= 1.6),
    ]
    for name, filt in atr_bins:
        trades_in = [t for t in first_trades if filt(t['atr_ratio'])]
        atr_buckets[name] = bucket_stats(trades_in)
    print_bucket_table("DIMENSION 4: ATR REGIME (current/50-bar mean)", atr_buckets)

    # ──────────────────────────────────────────
    # DIMENSION 5: Exit reason deep-dive
    # ──────────────────────────────────────────
    exit_buckets = {}
    for reason in ['TARGET', 'STOP', 'TIME']:
        trades_in = [t for t in first_trades if t['exit_reason'] == reason]
        exit_buckets[reason] = bucket_stats(trades_in)
    print_bucket_table("DIMENSION 5: EXIT REASON BREAKDOWN", exit_buckets)

    # ──────────────────────────────────────────
    # DIMENSION 6: Multi-dimensional "grid cells"
    # Combine the best-looking dimensions
    # ──────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  DIMENSION 6: GRID CELLS (EMA dist × TOD × Direction)")
    print(f"  Looking for PF > 1.0 cells with 30+ trades")
    print(f"{'='*70}")

    ema_groups = [
        ('below_ema', lambda d: d < 0),
        ('above_ema', lambda d: d >= 0),
    ]
    tod_groups = [
        ('open', lambda t: 8.5 <= t < 9.5),
        ('morning', lambda t: 9.5 <= t < 12.0),
        ('afternoon', lambda t: 12.0 <= t < 15.0),
    ]
    directions = ['LONG', 'SHORT']

    grid_cells = {}
    for ema_name, ema_filt in ema_groups:
        for tod_name, tod_filt in tod_groups:
            for direction in directions:
                trades_in = [t for t in valid_ema
                             if ema_filt(t['ema_dist_atr'])
                             and tod_filt(t['time_f'])
                             and t['direction'] == direction]
                key = f"{ema_name:10s}|{tod_name:10s}|{direction}"
                grid_cells[key] = bucket_stats(trades_in)
    print_bucket_table("GRID CELLS (coarse)", grid_cells)

    # ── Finer grid: 3 EMA bins × 3 TOD bins × direction ──
    print(f"\n{'='*70}")
    print(f"  FINE GRID: 4 EMA bins × 3 TOD × Direction (36 cells)")
    print(f"{'='*70}")

    ema_fine = [
        ('ema<-1', lambda d: d < -1),
        ('ema -1..0', lambda d: -1 <= d < 0),
        ('ema 0..1', lambda d: 0 <= d < 1),
        ('ema>1', lambda d: d >= 1),
    ]

    fine_cells = {}
    for ema_name, ema_filt in ema_fine:
        for tod_name, tod_filt in tod_groups:
            for direction in directions:
                trades_in = [t for t in valid_ema
                             if ema_filt(t['ema_dist_atr'])
                             and tod_filt(t['time_f'])
                             and t['direction'] == direction]
                key = f"{ema_name:10s}|{tod_name:10s}|{direction}"
                fine_cells[key] = bucket_stats(trades_in)

    # Print only cells with 20+ trades, sorted by PF
    items = [(k, v) for k, v in fine_cells.items() if v and v['count'] >= 20]
    items.sort(key=lambda x: x[1]['profit_factor'], reverse=True)

    print(f"  {'Cell':35s} {'Count':>7s} {'WR':>7s} {'PF':>8s} {'AvgPnL':>9s} {'TotalPnL':>11s}")
    print(f"  {'-'*77}")
    for name, s in items:
        marker = ""
        if s['profit_factor'] >= 1.3 and s['count'] >= 30:
            marker = " ***"
        elif s['profit_factor'] >= 1.0 and s['count'] >= 20:
            marker = " <<<"
        print(f"  {name:35s} {s['count']:>7,} {s['win_rate']:>6.1f}% {s['profit_factor']:>8.4f} "
              f"${s['avg_pnl']:>8.2f} ${s['total_pnl']:>10,.2f}{marker}")

    # ── Finer grid with ATR regime too ──
    print(f"\n{'='*70}")
    print(f"  ULTRA-FINE GRID: EMA × TOD × Direction × Vol Regime")
    print(f"  (only showing cells with PF >= 0.9 and 20+ trades)")
    print(f"{'='*70}")

    vol_groups = [
        ('low_vol', lambda r: r < 0.9),
        ('norm_vol', lambda r: 0.9 <= r < 1.2),
        ('high_vol', lambda r: r >= 1.2),
    ]

    ultra_cells = {}
    for ema_name, ema_filt in ema_fine:
        for tod_name, tod_filt in tod_groups:
            for direction in directions:
                for vol_name, vol_filt in vol_groups:
                    trades_in = [t for t in valid_ema
                                 if ema_filt(t['ema_dist_atr'])
                                 and tod_filt(t['time_f'])
                                 and t['direction'] == direction
                                 and vol_filt(t['atr_ratio'])]
                    key = f"{ema_name:10s}|{tod_name:10s}|{direction:5s}|{vol_name}"
                    ultra_cells[key] = bucket_stats(trades_in)

    items = [(k, v) for k, v in ultra_cells.items()
             if v and v['count'] >= 20 and v['profit_factor'] >= 0.9]
    items.sort(key=lambda x: x[1]['profit_factor'], reverse=True)

    print(f"  {'Cell':45s} {'Count':>7s} {'WR':>7s} {'PF':>8s} {'AvgPnL':>9s} {'TotalPnL':>11s}")
    print(f"  {'-'*88}")
    for name, s in items:
        marker = ""
        if s['profit_factor'] >= 1.3 and s['count'] >= 30:
            marker = " ***"
        elif s['profit_factor'] >= 1.0 and s['count'] >= 20:
            marker = " <<<"
        print(f"  {name:45s} {s['count']:>7,} {s['win_rate']:>6.1f}% {s['profit_factor']:>8.4f} "
              f"${s['avg_pnl']:>8.2f} ${s['total_pnl']:>10,.2f}{marker}")

    # ── Summary: how many trades in profitable cells? ──
    print(f"\n{'='*70}")
    print(f"  SUMMARY: GRID EXPLOITABILITY")
    print(f"{'='*70}")

    # Check fine grid
    profitable_fine = {k: v for k, v in fine_cells.items()
                       if v and v['count'] >= 30 and v['profit_factor'] >= 1.0}
    total_in_profitable = sum(v['count'] for v in profitable_fine.values())
    total_pnl_profitable = sum(v['total_pnl'] for v in profitable_fine.values())

    print(f"\n  FINE GRID (24 cells, EMA×TOD×Dir):")
    print(f"    Cells with PF >= 1.0 and 30+ trades: {len(profitable_fine)}")
    print(f"    Trades in those cells: {total_in_profitable:,}")
    print(f"    Combined PnL: ${total_pnl_profitable:,.2f}")
    print(f"    As % of all first entries: {total_in_profitable/len(first_trades)*100:.1f}%")

    # Ultra grid
    profitable_ultra = {k: v for k, v in ultra_cells.items()
                        if v and v['count'] >= 20 and v['profit_factor'] >= 1.0}
    total_in_pu = sum(v['count'] for v in profitable_ultra.values())
    total_pnl_pu = sum(v['total_pnl'] for v in profitable_ultra.values())

    print(f"\n  ULTRA GRID (72 cells, EMA×TOD×Dir×Vol):")
    print(f"    Cells with PF >= 1.0 and 20+ trades: {len(profitable_ultra)}")
    print(f"    Trades in those cells: {total_in_pu:,}")
    print(f"    Combined PnL: ${total_pnl_pu:,.2f}")
    print(f"    As % of all first entries: {total_in_pu/len(first_trades)*100:.1f}%")

    # What if we traded ONLY profitable cells?
    if total_in_profitable > 0:
        avg_pnl_p = total_pnl_profitable / total_in_profitable
        print(f"\n  If we traded ONLY fine-grid profitable cells:")
        print(f"    {total_in_profitable:,} trades over {years:.1f} years "
              f"= {total_in_profitable/years:.0f}/year = {total_in_profitable/years/252:.1f}/day")
        print(f"    Total PnL: ${total_pnl_profitable:,.2f}")
        print(f"    Avg PnL/trade: ${avg_pnl_p:.2f}")

    # Save
    out_dir = Path.home() / '.openclaw' / 'workspace' / 'research' / 'analysis'
    out_file = out_dir / 'mitch_l1l2_diagnostic.json'
    save_data = {
        'params_used': params,
        'total_first_entries': len(first_trades),
        'fine_grid_profitable_cells': len(profitable_fine),
        'fine_grid_profitable_trades': total_in_profitable,
        'fine_grid_profitable_pnl': round(total_pnl_profitable, 2),
        'ultra_grid_profitable_cells': len(profitable_ultra),
        'ultra_grid_profitable_trades': total_in_pu,
        'ultra_grid_profitable_pnl': round(total_pnl_pu, 2),
        'fine_grid_detail': {k: v for k, v in fine_cells.items() if v},
        'trend_breakdown': {k: v for k, v in trend_buckets.items() if v},
        'tod_breakdown': {k: v for k, v in tod_buckets.items() if v},
    }
    with open(out_file, 'w') as f:
        json.dump(save_data, f, indent=2, default=str)
    print(f"\nSaved to {out_file.relative_to(Path.home() / '.openclaw' / 'workspace' / 'research')}")
    print("=" * 70)


if __name__ == '__main__':
    main()
