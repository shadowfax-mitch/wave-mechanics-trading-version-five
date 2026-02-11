"""
V3 Refined: Focus on H2+UP core edge with targeted filters
Based on deep analysis of Config F trades
"""
import pandas as pd
import numpy as np
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from al_brooks_v2_strategy import AlBrooksV2Strategy


def calc(trades_df):
    if len(trades_df) == 0:
        return None
    t = len(trades_df)
    w = trades_df[trades_df['pnl_dollars'] > 0]
    l = trades_df[trades_df['pnl_dollars'] <= 0]
    gp = w['pnl_dollars'].sum() if len(w) > 0 else 0
    gl = abs(l['pnl_dollars'].sum()) if len(l) > 0 else 0
    pf = gp / gl if gl > 0 else 99
    cum = trades_df['pnl_dollars'].cumsum()
    dd = (cum - cum.expanding().max()).min()
    days = pd.to_datetime(trades_df['entry_time']).dt.date.nunique()
    return {
        'trades': t, 'wr': round(len(w)/t*100, 1), 'pf': round(pf, 2),
        'pnl': round(trades_df['pnl_dollars'].sum(), 0),
        'avg_w': round(w['pnl_dollars'].mean(), 2) if len(w) > 0 else 0,
        'avg_l': round(l['pnl_dollars'].mean(), 2) if len(l) > 0 else 0,
        'dd': round(dd, 0), 'days': days,
        'tpd': round(t/days, 2) if days > 0 else 0,
    }


def yearly(trades_df):
    trades_df = trades_df.copy()
    trades_df['year'] = pd.to_datetime(trades_df['entry_time']).dt.year
    results = {}
    for y in sorted(trades_df['year'].unique()):
        yt = trades_df[trades_df['year'] == y]
        r = calc(yt)
        if r:
            results[y] = r
    return results


def run_config(df, name, params):
    strategy = AlBrooksV2Strategy(params)
    trades = strategy.run_backtest(df, verbose=False)
    if len(trades) == 0:
        print(f"  {name}: NO TRADES")
        return None
    m = calc(trades)
    yr = yearly(trades)
    prof = sum(1 for y, r in yr.items() if r['pnl'] > 0)
    tot = len(yr)
    print(f"  {name}: {m['trades']} tr | {m['tpd']}/d | WR={m['wr']}% | PF={m['pf']} | "
          f"P&L=${m['pnl']:.0f} | W=${m['avg_w']:.1f} L=${m['avg_l']:.1f} | DD=${m['dd']:.0f} | {prof}/{tot}yr")
    for y, r in yr.items():
        flag = "+" if r['pnl'] > 0 else "-"
        print(f"    {y}: {r['trades']} tr {r['tpd']}/d WR={r['wr']}% PF={r['pf']} P&L=${r['pnl']:.0f} {flag}")
    return {'name': name, 'overall': m, 'yearly': yr, 'params': params, 'trades': trades}


def main():
    workspace = Path("/home/shado/.openclaw/workspace")
    df = pd.read_csv(workspace / "data" / "MNQ_5min.csv")
    df['time'] = pd.to_datetime(df['time'])
    print(f"Loaded {len(df):,} bars\n")

    # Common base
    base = {
        'tick_size': 0.25, 'tick_value': 0.50,
        'rth_only': True,
        'trend_ema_period': 20, 'trend_slope_lookback': 10,
        'sr_lookback': 100, 'sr_proximity_ticks': 8, 'sr_min_touches': 2,
        'pullback_min_size': 0.3, 'pattern_timeout': 30, 'pattern_validity': 3,
        'stop_offset_ticks': 1, 'max_hold_bars': 40,
        'daily_loss_limit': -200, 'max_consecutive_losses': 4,
        'ema_pullback_enabled': False,
        'counter_trend_allowed': False,
        'use_breakeven_trail': False,
        'min_signal_quality': 60,
        'min_body_ratio': 0.3,
        'max_stop_atr': 1.5,
        'reward_risk_ratio': 1.5,
        'min_target_ticks': 6,
    }

    results = []

    # === Config F baseline (for comparison) ===
    print("--- BASELINE (Config F) ---")
    p = {**base, 'rth_start': '08:30', 'rth_end': '15:00',
         'trend_slope_threshold': 0.03,
         'sideways_entries_allowed': True, 'allow_shorts': True, 'min_stop_ticks': 0}
    r = run_config(df, "F_baseline", p)
    if r: results.append(r)

    # === V3a: H2+UP only (longs only, no sideways) ===
    print("\n--- V3a: H2+UP ONLY ---")
    p = {**base, 'rth_start': '08:30', 'rth_end': '15:00',
         'trend_slope_threshold': 0.03,
         'sideways_entries_allowed': False, 'allow_shorts': False, 'min_stop_ticks': 0}
    r = run_config(df, "V3a_h2up", p)
    if r: results.append(r)

    # === V3b: H2+UP, skip first 30 min ===
    print("\n--- V3b: H2+UP, 09:00-15:00 ---")
    p = {**base, 'rth_start': '09:00', 'rth_end': '15:00',
         'trend_slope_threshold': 0.03,
         'sideways_entries_allowed': False, 'allow_shorts': False, 'min_stop_ticks': 0}
    r = run_config(df, "V3b_h2up_9am", p)
    if r: results.append(r)

    # === V3c: H2+UP, min stop 10 ticks ===
    print("\n--- V3c: H2+UP, min stop 10t ---")
    p = {**base, 'rth_start': '09:00', 'rth_end': '15:00',
         'trend_slope_threshold': 0.03,
         'sideways_entries_allowed': False, 'allow_shorts': False, 'min_stop_ticks': 10}
    r = run_config(df, "V3c_minstop10", p)
    if r: results.append(r)

    # === V3d: H2+UP, both directions (include L2+DOWN) ===
    print("\n--- V3d: With-trend both dirs, no sideways ---")
    p = {**base, 'rth_start': '09:00', 'rth_end': '15:00',
         'trend_slope_threshold': 0.03,
         'sideways_entries_allowed': False, 'allow_shorts': True, 'min_stop_ticks': 0}
    r = run_config(df, "V3d_both_dirs", p)
    if r: results.append(r)

    # === V3e: V3a + stronger trend threshold ===
    print("\n--- V3e: H2+UP, stronger trend (0.05) ---")
    p = {**base, 'rth_start': '09:00', 'rth_end': '15:00',
         'trend_slope_threshold': 0.05,
         'sideways_entries_allowed': False, 'allow_shorts': False, 'min_stop_ticks': 0}
    r = run_config(df, "V3e_strong_trend", p)
    if r: results.append(r)

    # === V3f: V3a + higher R:R ===
    print("\n--- V3f: H2+UP, R:R=2.0 ---")
    p = {**base, 'rth_start': '09:00', 'rth_end': '15:00',
         'trend_slope_threshold': 0.03, 'reward_risk_ratio': 2.0,
         'sideways_entries_allowed': False, 'allow_shorts': False, 'min_stop_ticks': 0}
    r = run_config(df, "V3f_rr20", p)
    if r: results.append(r)

    # === V3g: V3a + lower R:R (higher WR) ===
    print("\n--- V3g: H2+UP, R:R=1.25 ---")
    p = {**base, 'rth_start': '09:00', 'rth_end': '15:00',
         'trend_slope_threshold': 0.03, 'reward_risk_ratio': 1.25,
         'sideways_entries_allowed': False, 'allow_shorts': False, 'min_stop_ticks': 0}
    r = run_config(df, "V3g_rr125", p)
    if r: results.append(r)

    # === V3h: V3b + tighter stop (1.0 ATR) ===
    print("\n--- V3h: H2+UP, tight stop 1.0 ATR ---")
    p = {**base, 'rth_start': '09:00', 'rth_end': '15:00',
         'trend_slope_threshold': 0.03, 'max_stop_atr': 1.0,
         'sideways_entries_allowed': False, 'allow_shorts': False, 'min_stop_ticks': 0}
    r = run_config(df, "V3h_tight_stop", p)
    if r: results.append(r)

    # === V3i: Everything combined — best from analysis ===
    print("\n--- V3i: BEST COMBO ---")
    p = {**base, 'rth_start': '09:00', 'rth_end': '15:00',
         'trend_slope_threshold': 0.03, 'reward_risk_ratio': 1.5,
         'max_stop_atr': 1.5, 'min_stop_ticks': 10,
         'sideways_entries_allowed': False, 'allow_shorts': False,
         'min_body_ratio': 0.3, 'min_signal_quality': 60}
    r = run_config(df, "V3i_best_combo", p)
    if r: results.append(r)

    # === V3j: Add EMA pullback back (tight, longs only) ===
    print("\n--- V3j: H2+EMA_PB longs, no sideways ---")
    p = {**base, 'rth_start': '09:00', 'rth_end': '15:00',
         'trend_slope_threshold': 0.03,
         'ema_pullback_enabled': True, 'ema_pullback_proximity': 0.5,
         'sideways_entries_allowed': False, 'allow_shorts': False, 'min_stop_ticks': 0}
    r = run_config(df, "V3j_h2_ema_long", p)
    if r: results.append(r)

    # Summary
    print("\n" + "=" * 110)
    print(f"{'Config':<20} {'Tr':>6} {'TPD':>5} {'WR%':>5} {'PF':>5} {'P&L':>10} "
          f"{'AvgW':>8} {'AvgL':>8} {'DD':>9} {'PY':>5}")
    print("-" * 110)
    for r in sorted(results, key=lambda x: x['overall']['pf'], reverse=True):
        m = r['overall']
        yr = r['yearly']
        py = sum(1 for y, d in yr.items() if d['pnl'] > 0)
        ty = len(yr)
        print(f"{r['name']:<20} {m['trades']:>6} {m['tpd']:>5} {m['wr']:>5} {m['pf']:>5} "
              f"${m['pnl']:>9.0f} ${m['avg_w']:>7.1f} ${m['avg_l']:>7.1f} ${m['dd']:>8.0f} {py}/{ty}")

    # Save best trades
    best = max(results, key=lambda x: x['overall']['pf'])
    output_dir = workspace / "research" / "al_brooks_system" / "backtests" / "v2"
    if 'trades' in best:
        best['trades'].to_csv(output_dir / "v3_best_trades.csv", index=False)
        print(f"\nBest config '{best['name']}' trades saved")


if __name__ == "__main__":
    main()
