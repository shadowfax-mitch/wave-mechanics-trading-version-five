#!/usr/bin/env python3
"""
Parameter sweep for Mitch L1+L2 — find if structure entries have edge.

Tests:
1. EMA confirmation ON vs OFF
2. Target ATR fallback: 2.0, 3.0, 4.0
3. Stop buffer: 0.5, 1.0, 1.5 ATR
4. Max stop: 2.0, 3.0 ATR
"""

import sys
import json
import time
import numpy as np
import pandas as pd
from pathlib import Path
from itertools import product

sys.path.insert(0, str(Path(__file__).parent))
from mitch_l1l2_strategy import (
    precompute_indicators, detect_trend_and_entries,
    backtest, calculate_statistics, DEFAULT_PARAMS,
)


def main():
    print("=" * 70)
    print("  MITCH L1+L2 — PARAMETER SWEEP")
    print("=" * 70)

    data_path = Path.home() / '.openclaw' / 'workspace' / 'data' / 'MNQ_5min.csv'
    df = pd.read_csv(data_path, parse_dates=['time'], index_col='time')
    df.index.name = 'timestamp'
    years = (df.index[-1] - df.index[0]).days / 365.25
    print(f"Loaded {len(df):,} bars, {years:.2f} years\n")

    # Grid
    ema_options = [True, False]
    target_fallbacks = [2.0, 3.0, 4.0]
    stop_buffers = [0.5, 1.0, 1.5]
    max_stops = [2.0, 3.0]
    measured_caps = [5.0, 8.0]

    combos = list(product(ema_options, target_fallbacks, stop_buffers, max_stops, measured_caps))
    print(f"Testing {len(combos)} combinations...\n")

    # Precompute indicators once (they don't change with these params)
    base_params = dict(DEFAULT_PARAMS)
    data = precompute_indicators(df, base_params)

    results = []
    t0 = time.time()

    for idx, (use_ema, tgt_fb, stop_buf, max_stop, mm_cap) in enumerate(combos):
        params = dict(DEFAULT_PARAMS)
        params['use_ema_confirmation'] = use_ema
        params['target_atr_fallback'] = tgt_fb
        params['stop_buffer_atr'] = stop_buf
        params['max_stop_atr'] = max_stop
        params['measured_move_cap_atr'] = mm_cap

        signals = detect_trend_and_entries(data, params)
        trades = backtest(data, signals, params)
        stats = calculate_statistics(trades, years)

        row = {
            'ema_conf': use_ema,
            'tgt_fb': tgt_fb,
            'stop_buf': stop_buf,
            'max_stop': max_stop,
            'mm_cap': mm_cap,
            **{k: stats[k] for k in [
                'total_trades', 'win_rate', 'profit_factor', 'total_pnl',
                'avg_pnl', 'sharpe', 'max_drawdown', 'trades_per_day',
                'avg_bars_held', 'long_win_rate', 'short_win_rate',
            ]},
            'fe_count': stats['first_entry']['count'],
            'fe_wr': stats['first_entry']['win_rate'],
            'fe_pf': stats['first_entry']['profit_factor'],
            'fe_pnl': stats['first_entry']['total_pnl'],
            'se_count': stats['second_entry']['count'],
            'se_wr': stats['second_entry']['win_rate'],
            'se_pf': stats['second_entry']['profit_factor'],
            'se_pnl': stats['second_entry']['total_pnl'],
        }

        # Exit reason pcts
        total = stats['total_trades']
        for reason in ['TARGET', 'STOP', 'TIME']:
            info = stats['exit_reasons'].get(reason, {'count': 0, 'pnl': 0})
            row[f'{reason.lower()}_pct'] = round(info['count'] / total * 100, 1) if total > 0 else 0
            row[f'{reason.lower()}_avg'] = round(info['pnl'] / info['count'], 2) if info['count'] > 0 else 0

        results.append(row)

        if (idx + 1) % 10 == 0:
            elapsed = time.time() - t0
            print(f"  [{idx+1}/{len(combos)}] {elapsed:.1f}s")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s\n")

    rdf = pd.DataFrame(results)

    # ── EMA ON vs OFF comparison ──
    print("=" * 70)
    print("  EMA CONFIRMATION: ON vs OFF")
    print("=" * 70)
    for ema_val in [True, False]:
        subset = rdf[rdf['ema_conf'] == ema_val]
        label = "EMA ON " if ema_val else "EMA OFF"
        print(f"\n  {label} ({len(subset)} configs)")
        print(f"    Avg WR:    {subset['win_rate'].mean():.2f}%")
        print(f"    Avg PF:    {subset['profit_factor'].mean():.4f}")
        print(f"    Avg PnL:   ${subset['total_pnl'].mean():,.0f}")
        print(f"    Avg Trades:{subset['total_trades'].mean():,.0f}")
        print(f"    2nd Entry: {subset['se_count'].mean():.0f} trades, "
              f"WR {subset['se_wr'].mean():.1f}%, PF {subset['se_pf'].mean():.4f}")

    # ── Top configs by profit factor (min 100 trades) ──
    print("\n" + "=" * 70)
    print("  TOP 15 BY PROFIT FACTOR (min 100 trades)")
    print("=" * 70)
    viable = rdf[rdf['total_trades'] >= 100].copy()
    top = viable.nlargest(15, 'profit_factor')
    for _, r in top.iterrows():
        ema_str = "EMA" if r['ema_conf'] else "noEMA"
        print(f"  PF={r['profit_factor']:.4f} WR={r['win_rate']:.1f}% "
              f"Trades={r['total_trades']:,} PnL=${r['total_pnl']:,.0f} "
              f"Sharpe={r['sharpe']:.3f} DD=${r['max_drawdown']:,.0f}")
        print(f"    {ema_str} tgt={r['tgt_fb']} stop={r['stop_buf']} "
              f"maxS={r['max_stop']} cap={r['mm_cap']} | "
              f"2nd: {r['se_count']} trades WR={r['se_wr']:.1f}% PF={r['se_pf']:.4f}")

    # ── Parameter sensitivity ──
    print("\n" + "=" * 70)
    print("  PARAMETER SENSITIVITY (mean PF across configs)")
    print("=" * 70)
    for param, col in [('ema_conf', 'ema_conf'), ('tgt_fb', 'tgt_fb'),
                        ('stop_buf', 'stop_buf'), ('max_stop', 'max_stop'),
                        ('mm_cap', 'mm_cap')]:
        groups = viable.groupby(col).agg({
            'profit_factor': 'mean',
            'win_rate': 'mean',
            'total_pnl': 'mean',
            'total_trades': 'mean',
            'se_count': 'mean',
            'se_wr': 'mean',
        }).round(3)
        pf_range = groups['profit_factor'].max() - groups['profit_factor'].min()
        print(f"\n  {param} (PF spread: {pf_range:.3f})")
        for val, row in groups.iterrows():
            print(f"    {str(val):8s} → PF={row['profit_factor']:.3f} "
                  f"WR={row['win_rate']:.1f}% "
                  f"PnL=${row['total_pnl']:,.0f} "
                  f"Trades={row['total_trades']:.0f} "
                  f"2nd={row['se_count']:.0f}@{row['se_wr']:.1f}%")

    # ── Best 2nd-entry performance ──
    print("\n" + "=" * 70)
    print("  BEST CONFIGS FOR 2ND ENTRY (min 50 second-entry trades)")
    print("=" * 70)
    se_viable = rdf[rdf['se_count'] >= 50].copy()
    if len(se_viable) == 0:
        se_viable = rdf[rdf['se_count'] >= 20].copy()
        print(f"  (Relaxed to 20+ 2nd-entry trades: {len(se_viable)} configs)")
    else:
        print(f"  {len(se_viable)} configs with 50+ 2nd-entry trades")

    if len(se_viable) > 0:
        se_top = se_viable.nlargest(10, 'se_pf')
        for _, r in se_top.iterrows():
            ema_str = "EMA" if r['ema_conf'] else "noEMA"
            print(f"  2nd PF={r['se_pf']:.4f} WR={r['se_wr']:.1f}% "
                  f"Count={r['se_count']:.0f} PnL=${r['se_pnl']:,.0f} | "
                  f"Overall PF={r['profit_factor']:.4f} Trades={r['total_trades']:,}")
            print(f"    {ema_str} tgt={r['tgt_fb']} stop={r['stop_buf']} "
                  f"maxS={r['max_stop']} cap={r['mm_cap']}")

    # ── Does 2nd entry EVER beat 1st entry? ──
    print("\n" + "=" * 70)
    print("  A/B: CONFIGS WHERE 2ND ENTRY BEATS 1ST ENTRY")
    print("=" * 70)
    rdf['se_beats_fe'] = (rdf['se_pf'] > rdf['fe_pf']) & (rdf['se_count'] >= 20)
    winners = rdf[rdf['se_beats_fe']]
    print(f"  {len(winners)} of {len(rdf)} configs where 2nd entry PF > 1st entry PF (min 20 trades)")
    if len(winners) > 0:
        best = winners.nlargest(5, 'se_pf')
        for _, r in best.iterrows():
            ema_str = "EMA" if r['ema_conf'] else "noEMA"
            print(f"  1st: PF={r['fe_pf']:.4f} WR={r['fe_wr']:.1f}% ({r['fe_count']:.0f} trades) | "
                  f"2nd: PF={r['se_pf']:.4f} WR={r['se_wr']:.1f}% ({r['se_count']:.0f} trades)")
            print(f"    {ema_str} tgt={r['tgt_fb']} stop={r['stop_buf']} "
                  f"maxS={r['max_stop']} cap={r['mm_cap']}")

    # ── Save ──
    out_dir = Path.home() / '.openclaw' / 'workspace' / 'research' / 'analysis'
    out_file = out_dir / 'mitch_l1l2_sweep.json'
    save = {
        'total_combos': len(combos),
        'viable_combos': len(viable),
        'best_overall': top.iloc[0].to_dict() if len(top) > 0 else {},
        'ema_on_avg_pf': round(rdf[rdf['ema_conf']]['profit_factor'].mean(), 4),
        'ema_off_avg_pf': round(rdf[~rdf['ema_conf']]['profit_factor'].mean(), 4),
        'configs_2nd_beats_1st': len(winners),
    }
    with open(out_file, 'w') as f:
        json.dump(save, f, indent=2, default=str)
    print(f"\nSaved to {out_file.relative_to(Path.home() / '.openclaw' / 'workspace' / 'research')}")
    print("=" * 70)


if __name__ == '__main__':
    main()
