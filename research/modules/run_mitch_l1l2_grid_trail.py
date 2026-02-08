#!/usr/bin/env python3
"""
Mitch L1+L2 — Trail-Only + Grid Filter

Combines the best exit mechanic (trail-only, buf=0.8, BE, hold=90)
with grid cell filtering to find where PF > 1.0.

Also runs a split-half validation: train cells on first 50% of data,
test on second 50%, to check if profitable cells are stable or overfit.
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
    backtest_trailing, calculate_statistics, DEFAULT_PARAMS,
)


# ── Grid bucketing functions ──

def ema_bucket(dist):
    if np.isnan(dist):
        return None
    if dist < -2:
        return 'ema<-2'
    elif dist < -1:
        return 'ema-2..-1'
    elif dist < 0:
        return 'ema-1..0'
    elif dist < 1:
        return 'ema0..1'
    elif dist < 2:
        return 'ema1..2'
    else:
        return 'ema>2'


def tod_bucket(tf):
    if 8.5 <= tf < 9.5:
        return 'open'
    elif 9.5 <= tf < 12.0:
        return 'morning'
    elif 12.0 <= tf < 15.0:
        return 'afternoon'
    return None


def vol_bucket(ratio):
    if ratio < 0.9:
        return 'low_vol'
    elif ratio < 1.2:
        return 'norm_vol'
    else:
        return 'high_vol'


def bucket_stats(pnls):
    """Stats from a pnl array."""
    if len(pnls) == 0:
        return None
    n = len(pnls)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gp = wins.sum() if len(wins) > 0 else 0.0
    gl = abs(losses.sum()) if len(losses) > 0 else 0.0
    pf = gp / gl if gl > 0 else (999.0 if gp > 0 else 0.0)
    return {
        'count': n,
        'win_rate': round(len(wins) / n * 100, 1),
        'profit_factor': round(pf, 4),
        'total_pnl': round(pnls.sum(), 2),
        'avg_pnl': round(pnls.mean(), 2),
    }


def tag_trades(trades, data):
    """Add grid cell tags to each trade."""
    atr = data['atr']
    ema = data['ema']
    close = data['close']
    time_f = data['time_f']

    for t in trades:
        bar = t['entry_bar']
        a = atr[bar]

        # EMA distance
        if a > 0 and not np.isnan(a) and not np.isnan(ema[bar]):
            t['ema_dist'] = (close[bar] - ema[bar]) / a
        else:
            t['ema_dist'] = np.nan

        # TOD
        t['tod'] = tod_bucket(time_f[bar])

        # Vol regime
        if bar >= 50:
            atr_mean = np.nanmean(atr[bar-50:bar])
            t['vol_ratio'] = a / atr_mean if atr_mean > 0 else 1.0
        else:
            t['vol_ratio'] = 1.0

        # Cell keys
        t['ema_cell'] = ema_bucket(t['ema_dist'])
        t['vol_cell'] = vol_bucket(t['vol_ratio'])
        t['cell_fine'] = f"{t['ema_cell']}|{t['tod']}|{t['direction']}"
        t['cell_ultra'] = f"{t['ema_cell']}|{t['tod']}|{t['direction']}|{t['vol_cell']}"


def grid_analysis(trades, label, min_trades=20):
    """Analyze grid cells, return profitable cell keys."""
    from collections import defaultdict

    # Fine grid
    fine_cells = defaultdict(list)
    ultra_cells = defaultdict(list)

    for t in trades:
        if t['ema_cell'] is None or t['tod'] is None:
            continue
        fine_cells[t['cell_fine']].append(t['pnl'])
        ultra_cells[t['cell_ultra']].append(t['pnl'])

    print(f"\n{'='*80}")
    print(f"  {label} — FINE GRID (EMA × TOD × Direction)")
    print(f"{'='*80}")

    fine_stats = {}
    for key in sorted(fine_cells.keys()):
        pnls = np.array(fine_cells[key])
        s = bucket_stats(pnls)
        if s and s['count'] >= min_trades:
            fine_stats[key] = s

    # Sort by PF
    items = sorted(fine_stats.items(), key=lambda x: x[1]['profit_factor'], reverse=True)
    print(f"  {'Cell':35s} {'N':>6s} {'WR':>7s} {'PF':>8s} {'AvgPnL':>9s} {'TotalPnL':>11s}")
    print(f"  {'-'*76}")
    for key, s in items:
        marker = " ***" if s['profit_factor'] >= 1.3 and s['count'] >= 30 else \
                 " <<<"  if s['profit_factor'] >= 1.0 else ""
        print(f"  {key:35s} {s['count']:>6,} {s['win_rate']:>6.1f}% {s['profit_factor']:>8.4f} "
              f"${s['avg_pnl']:>8.2f} ${s['total_pnl']:>10,.2f}{marker}")

    print(f"\n{'='*80}")
    print(f"  {label} — ULTRA GRID (EMA × TOD × Direction × Vol)")
    print(f"{'='*80}")

    ultra_stats = {}
    for key in sorted(ultra_cells.keys()):
        pnls = np.array(ultra_cells[key])
        s = bucket_stats(pnls)
        if s and s['count'] >= min_trades:
            ultra_stats[key] = s

    items = sorted(ultra_stats.items(), key=lambda x: x[1]['profit_factor'], reverse=True)
    print(f"  {'Cell':48s} {'N':>6s} {'WR':>7s} {'PF':>8s} {'AvgPnL':>9s} {'TotalPnL':>11s}")
    print(f"  {'-'*89}")
    for key, s in items:
        marker = " ***" if s['profit_factor'] >= 1.3 and s['count'] >= 30 else \
                 " <<<"  if s['profit_factor'] >= 1.0 else ""
        print(f"  {key:48s} {s['count']:>6,} {s['win_rate']:>6.1f}% {s['profit_factor']:>8.4f} "
              f"${s['avg_pnl']:>8.2f} ${s['total_pnl']:>10,.2f}{marker}")

    # Profitable cells
    fine_profitable = {k for k, v in fine_stats.items() if v['profit_factor'] >= 1.0}
    ultra_profitable = {k for k, v in ultra_stats.items() if v['profit_factor'] >= 1.0}

    return fine_profitable, ultra_profitable, fine_stats, ultra_stats


def filtered_stats(trades, cell_keys, cell_field, label):
    """Stats for trades whose cell is in the given set."""
    filtered = [t for t in trades if t.get(cell_field) in cell_keys]
    if not filtered:
        print(f"\n  {label}: NO trades in filtered cells")
        return None

    pnls = np.array([t['pnl'] for t in filtered])
    s = bucket_stats(pnls)

    # Yearly breakdown
    from collections import defaultdict
    yearly = defaultdict(list)
    for t in filtered:
        yr = t['date'][:4]
        yearly[yr].append(t['pnl'])

    print(f"\n  {label}:")
    print(f"    Trades:  {s['count']:,}")
    print(f"    WR:      {s['win_rate']:.1f}%")
    print(f"    PF:      {s['profit_factor']:.4f}")
    print(f"    Avg PnL: ${s['avg_pnl']:.2f}")
    print(f"    Total:   ${s['total_pnl']:,.2f}")

    # Drawdown
    cum = np.cumsum(pnls)
    running_max = np.maximum.accumulate(cum)
    dd = running_max - cum
    max_dd = dd.max()
    print(f"    Max DD:  ${max_dd:,.2f}")

    trading_days = len(set(t['date'] for t in filtered))
    years = trading_days / 252.0
    print(f"    Days:    {trading_days:,} ({s['count']/trading_days:.2f} trades/day)")

    # Sharpe
    std = pnls.std()
    sharpe = pnls.mean() / std if std > 0 else 0
    print(f"    Sharpe:  {sharpe:.4f}")

    print(f"\n    {'Year':6s} {'N':>6s} {'WR':>7s} {'PF':>8s} {'PnL':>10s}")
    for yr in sorted(yearly.keys()):
        yp = np.array(yearly[yr])
        ys = bucket_stats(yp)
        if ys:
            print(f"    {yr:6s} {ys['count']:>6,} {ys['win_rate']:>6.1f}% "
                  f"{ys['profit_factor']:>8.4f} ${ys['total_pnl']:>9,.2f}")

    return s


def main():
    print("=" * 80)
    print("  MITCH L1+L2 — TRAIL-ONLY + GRID FILTER")
    print("=" * 80)

    data_path = Path.home() / '.openclaw' / 'workspace' / 'data' / 'MNQ_5min.csv'
    df = pd.read_csv(data_path, parse_dates=['time'], index_col='time')
    df.index.name = 'timestamp'
    years = (df.index[-1] - df.index[0]).days / 365.25
    print(f"Loaded {len(df):,} bars, {years:.2f} years\n")

    # Best trail-only params
    params = dict(DEFAULT_PARAMS)
    params['use_ema_confirmation'] = False
    params['stop_buffer_atr'] = 1.5
    params['target_atr_fallback'] = 3.0
    params['measured_move_cap_atr'] = 8.0
    params['trail_buffer_atr'] = 0.8
    params['use_breakeven'] = True
    params['trail_only'] = True
    params['max_hold'] = 90

    # ── FULL SAMPLE ──
    print("Running trail-only backtest (full sample)...")
    t0 = time.time()
    data = precompute_indicators(df, params)
    signals = detect_trend_and_entries(data, params)
    trades_all = backtest_trailing(data, signals, params)
    tag_trades(trades_all, data)
    elapsed = time.time() - t0
    print(f"Done in {elapsed:.1f}s — {len(trades_all):,} trades\n")

    # Full-sample grid
    fine_profit, ultra_profit, fine_stats, ultra_stats = grid_analysis(
        trades_all, "FULL SAMPLE (trail-only)", min_trades=20)

    print(f"\n{'='*80}")
    print(f"  FILTERED PERFORMANCE — FULL SAMPLE")
    print(f"{'='*80}")

    filtered_stats(trades_all, fine_profit, 'cell_fine',
                   f"FINE GRID filter ({len(fine_profit)} profitable cells)")
    filtered_stats(trades_all, ultra_profit, 'cell_ultra',
                   f"ULTRA GRID filter ({len(ultra_profit)} profitable cells)")

    # ── SPLIT-HALF VALIDATION ──
    print(f"\n\n{'#'*80}")
    print(f"  SPLIT-HALF VALIDATION")
    print(f"  Train on first 50% of data, test on second 50%")
    print(f"{'#'*80}")

    mid = len(df) // 2
    df_train = df.iloc[:mid]
    df_test = df.iloc[mid:]
    print(f"\n  Train: {len(df_train):,} bars ({df_train.index[0]} to {df_train.index[-1]})")
    print(f"  Test:  {len(df_test):,} bars ({df_test.index[0]} to {df_test.index[-1]})")

    # Train
    data_train = precompute_indicators(df_train, params)
    sig_train = detect_trend_and_entries(data_train, params)
    trades_train = backtest_trailing(data_train, sig_train, params)
    tag_trades(trades_train, data_train)
    print(f"\n  Train trades: {len(trades_train):,}")

    fine_train, ultra_train, _, _ = grid_analysis(
        trades_train, "TRAIN HALF", min_trades=15)

    # Test
    data_test = precompute_indicators(df_test, params)
    sig_test = detect_trend_and_entries(data_test, params)
    trades_test = backtest_trailing(data_test, sig_test, params)
    tag_trades(trades_test, data_test)
    print(f"\n  Test trades: {len(trades_test):,}")

    # Apply train cells to test data
    print(f"\n{'='*80}")
    print(f"  OUT-OF-SAMPLE: Train cells applied to test data")
    print(f"{'='*80}")

    s_all_test = bucket_stats(np.array([t['pnl'] for t in trades_test]))
    print(f"\n  TEST UNFILTERED: {s_all_test['count']:,} trades, "
          f"PF={s_all_test['profit_factor']:.4f}, WR={s_all_test['win_rate']:.1f}%, "
          f"PnL=${s_all_test['total_pnl']:,.2f}")

    s_fine_oos = filtered_stats(trades_test, fine_train, 'cell_fine',
                                f"FINE GRID (train cells → test data, {len(fine_train)} cells)")
    s_ultra_oos = filtered_stats(trades_test, ultra_train, 'cell_ultra',
                                 f"ULTRA GRID (train cells → test data, {len(ultra_train)} cells)")

    # ── Also test: test cells on train data (reverse validation) ──
    fine_test_cells, ultra_test_cells, _, _ = grid_analysis(
        trades_test, "TEST HALF", min_trades=15)

    # How many cells overlap?
    fine_overlap = fine_train & fine_test_cells
    ultra_overlap = ultra_train & ultra_test_cells

    print(f"\n{'='*80}")
    print(f"  CELL STABILITY ACROSS HALVES")
    print(f"{'='*80}")
    print(f"  FINE GRID:")
    print(f"    Train profitable cells: {len(fine_train)}")
    print(f"    Test profitable cells:  {len(fine_test_cells)}")
    print(f"    Overlap (both halves):  {len(fine_overlap)}")
    if fine_overlap:
        print(f"    Stable cells: {sorted(fine_overlap)}")
    print(f"\n  ULTRA GRID:")
    print(f"    Train profitable cells: {len(ultra_train)}")
    print(f"    Test profitable cells:  {len(ultra_test_cells)}")
    print(f"    Overlap (both halves):  {len(ultra_overlap)}")
    if ultra_overlap:
        print(f"    Stable cells: {sorted(ultra_overlap)}")

    # Performance of stable cells on FULL data
    if fine_overlap:
        print(f"\n{'='*80}")
        print(f"  STABLE CELLS PERFORMANCE (full data)")
        print(f"{'='*80}")
        filtered_stats(trades_all, fine_overlap, 'cell_fine',
                        f"STABLE FINE cells ({len(fine_overlap)} cells)")

    if ultra_overlap:
        filtered_stats(trades_all, ultra_overlap, 'cell_ultra',
                        f"STABLE ULTRA cells ({len(ultra_overlap)} cells)")

    # ── Save ──
    out_dir = Path.home() / '.openclaw' / 'workspace' / 'research' / 'analysis'
    out_file = out_dir / 'mitch_l1l2_grid_trail.json'
    save = {
        'params': params,
        'full_sample_trades': len(trades_all),
        'fine_profitable_cells': sorted(fine_profit),
        'ultra_profitable_cells': sorted(ultra_profit),
        'fine_stable_cells': sorted(fine_overlap),
        'ultra_stable_cells': sorted(ultra_overlap),
        'full_fine_stats': {k: v for k, v in fine_stats.items()},
        'full_ultra_stats': {k: v for k, v in ultra_stats.items()},
    }
    with open(out_file, 'w') as f:
        json.dump(save, f, indent=2, default=str)
    print(f"\nSaved to {out_file.relative_to(Path.home() / '.openclaw' / 'workspace' / 'research')}")
    print("=" * 80)


if __name__ == '__main__':
    main()
