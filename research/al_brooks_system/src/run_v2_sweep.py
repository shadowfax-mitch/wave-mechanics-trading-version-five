"""
Sweep V2 configurations to find the sweet spot:
~1 trade/day, positive PF, good R:R
"""
import pandas as pd
import numpy as np
import json
import sys
from pathlib import Path
from datetime import datetime

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
        'trades': t,
        'wr': round(len(w) / t * 100, 1),
        'pf': round(pf, 2),
        'pnl': round(trades_df['pnl_dollars'].sum(), 0),
        'avg_w': round(w['pnl_dollars'].mean(), 2) if len(w) > 0 else 0,
        'avg_l': round(l['pnl_dollars'].mean(), 2) if len(l) > 0 else 0,
        'dd': round(dd, 0),
        'days': days,
        'tpd': round(t / days, 2) if days > 0 else 0,
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
    # Count profitable years
    prof_years = sum(1 for y, r in yr.items() if r['pnl'] > 0)
    total_years = len(yr)
    print(f"  {name}: {m['trades']} trades | {m['tpd']}/day | WR={m['wr']}% | "
          f"PF={m['pf']} | P&L=${m['pnl']:.0f} | W=${m['avg_w']:.1f} L=${m['avg_l']:.1f} | "
          f"DD=${m['dd']:.0f} | Prof years: {prof_years}/{total_years}")
    for y, r in yr.items():
        flag = "+" if r['pnl'] > 0 else "-"
        print(f"    {y}: {r['trades']} tr {r['tpd']}/d WR={r['wr']}% PF={r['pf']} P&L=${r['pnl']:.0f} {flag}")
    return {'name': name, 'overall': m, 'yearly': yr, 'trades_df': trades}


def main():
    workspace = Path("/home/shado/.openclaw/workspace")
    df = pd.read_csv(workspace / "data" / "MNQ_5min.csv")
    df['time'] = pd.to_datetime(df['time'])
    print(f"Loaded {len(df):,} bars\n")

    base = {
        'tick_size': 0.25, 'tick_value': 0.50,
        'rth_only': True, 'rth_start': '08:30', 'rth_end': '15:00',
        'trend_ema_period': 20, 'trend_slope_lookback': 10,
        'sr_lookback': 100, 'sr_proximity_ticks': 8, 'sr_min_touches': 2,
        'pullback_min_size': 0.3, 'pattern_timeout': 30, 'pattern_validity': 3,
        'stop_offset_ticks': 1, 'max_hold_bars': 40,
        'daily_loss_limit': -200, 'max_consecutive_losses': 4,
    }

    configs = {}

    # A: H2/L2 only, quality 60, no counter-trend
    configs['A_h2l2_q60'] = {
        **base,
        'trend_slope_threshold': 0.03,
        'ema_pullback_enabled': False,
        'counter_trend_allowed': False,
        'with_trend_needs_sr': False,
        'min_signal_quality': 60,
        'min_body_ratio': 0.3,
        'max_stop_atr': 1.5,
        'reward_risk_ratio': 1.5,
        'min_target_ticks': 6,
        'use_breakeven_trail': True,
    }

    # B: H2/L2 only, tighter stop, higher R:R
    configs['B_h2l2_tight'] = {
        **base,
        'trend_slope_threshold': 0.03,
        'ema_pullback_enabled': False,
        'counter_trend_allowed': False,
        'with_trend_needs_sr': False,
        'min_signal_quality': 60,
        'min_body_ratio': 0.3,
        'max_stop_atr': 1.0,
        'reward_risk_ratio': 2.0,
        'min_target_ticks': 6,
        'use_breakeven_trail': True,
    }

    # C: EMA pullback with tight filter, with-trend only
    configs['C_ema_tight'] = {
        **base,
        'trend_slope_threshold': 0.05,
        'ema_pullback_enabled': True,
        'ema_pullback_proximity': 0.5,
        'counter_trend_allowed': False,
        'with_trend_needs_sr': False,
        'min_signal_quality': 60,
        'min_body_ratio': 0.4,
        'max_stop_atr': 1.0,
        'reward_risk_ratio': 2.0,
        'min_target_ticks': 6,
        'use_breakeven_trail': True,
    }

    # D: Everything with strong quality filter
    configs['D_all_q70'] = {
        **base,
        'trend_slope_threshold': 0.03,
        'ema_pullback_enabled': True,
        'ema_pullback_proximity': 0.5,
        'counter_trend_allowed': False,
        'with_trend_needs_sr': False,
        'min_signal_quality': 70,
        'min_body_ratio': 0.4,
        'max_stop_atr': 1.5,
        'reward_risk_ratio': 1.5,
        'min_target_ticks': 6,
        'use_breakeven_trail': True,
    }

    # E: H2/L2 + with-trend S/R required (most selective)
    configs['E_h2l2_sr'] = {
        **base,
        'trend_slope_threshold': 0.03,
        'ema_pullback_enabled': False,
        'counter_trend_allowed': False,
        'with_trend_needs_sr': True,
        'min_signal_quality': 50,
        'min_body_ratio': 0.3,
        'max_stop_atr': 1.5,
        'reward_risk_ratio': 1.5,
        'min_target_ticks': 6,
        'use_breakeven_trail': True,
    }

    # F: H2/L2 only, no BE trail (let winners run to full target)
    configs['F_h2l2_notrail'] = {
        **base,
        'trend_slope_threshold': 0.03,
        'ema_pullback_enabled': False,
        'counter_trend_allowed': False,
        'with_trend_needs_sr': False,
        'min_signal_quality': 60,
        'min_body_ratio': 0.3,
        'max_stop_atr': 1.5,
        'reward_risk_ratio': 1.5,
        'min_target_ticks': 6,
        'use_breakeven_trail': False,
    }

    # G: H2/L2, higher body ratio (0.5), moderate stop
    configs['G_h2l2_body50'] = {
        **base,
        'trend_slope_threshold': 0.03,
        'ema_pullback_enabled': False,
        'counter_trend_allowed': False,
        'with_trend_needs_sr': False,
        'min_signal_quality': 50,
        'min_body_ratio': 0.5,
        'max_stop_atr': 1.2,
        'reward_risk_ratio': 1.5,
        'min_target_ticks': 6,
        'use_breakeven_trail': True,
    }

    # H: Late-day filter (RTH end at 14:00 instead of 15:00)
    configs['H_h2l2_early'] = {
        **base,
        'rth_end': '14:00',
        'trend_slope_threshold': 0.03,
        'ema_pullback_enabled': False,
        'counter_trend_allowed': False,
        'with_trend_needs_sr': False,
        'min_signal_quality': 60,
        'min_body_ratio': 0.3,
        'max_stop_atr': 1.5,
        'reward_risk_ratio': 1.5,
        'min_target_ticks': 6,
        'use_breakeven_trail': True,
    }

    results = []
    for name, params in configs.items():
        print(f"\n--- Config {name} ---")
        r = run_config(df, name, params)
        if r:
            results.append(r)

    # Summary table
    print("\n" + "=" * 100)
    print("CONFIGURATION COMPARISON")
    print("=" * 100)
    print(f"{'Config':<20} {'Trades':>7} {'TPD':>5} {'WR%':>5} {'PF':>5} {'P&L':>10} "
          f"{'AvgW':>8} {'AvgL':>8} {'DD':>10} {'ProfYr':>7}")
    print("-" * 100)
    for r in results:
        m = r['overall']
        yr = r['yearly']
        prof = sum(1 for y, d in yr.items() if d['pnl'] > 0)
        tot = len(yr)
        print(f"{r['name']:<20} {m['trades']:>7} {m['tpd']:>5} {m['wr']:>5} {m['pf']:>5} "
              f"${m['pnl']:>9.0f} ${m['avg_w']:>7.1f} ${m['avg_l']:>7.1f} ${m['dd']:>9.0f} "
              f"{prof}/{tot}")

    # Save best config trades
    output_dir = workspace / "research" / "al_brooks_system" / "backtests" / "v2"
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = []
    for r in results:
        entry = {'name': r['name'], 'overall': r['overall'], 'yearly': {str(k): v for k, v in r['yearly'].items()}}
        summary.append(entry)
    with open(output_dir / "v2_sweep_results.json", 'w') as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\nSaved to {output_dir / 'v2_sweep_results.json'}")


if __name__ == "__main__":
    main()
