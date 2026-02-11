"""
V4 PF Boost Sweep: Targeted improvements to push PF above 1.18
Based on deep analysis findings:
  - 1-bar trades PF=0.62 (grace period fix)
  - 6+ bar trades PF=1.70 (trailing stop to let winners run)
  - Hour 8 toxic, hour 11 weak (time filter)
  - Stops 0-10 ticks PF=0.61 (min stop distance)
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
        r = calc(trades_df[trades_df['year'] == y])
        if r:
            results[y] = r
    return results


def run(df, name, params):
    s = AlBrooksV2Strategy(params)
    tr = s.run_backtest(df, verbose=False)
    if len(tr) == 0:
        print(f"  {name}: NO TRADES")
        return None
    m = calc(tr)
    yr = yearly(tr)
    prof = sum(1 for y, r in yr.items() if r['pnl'] > 0)
    tot = len(yr)
    print(f"  {name:<28s} {m['trades']:>5} tr {m['tpd']:.1f}/d WR={m['wr']:>5.1f}% "
          f"PF={m['pf']:>5.2f} P&L=${m['pnl']:>8.0f} W=${m['avg_w']:>6.1f} L=${m['avg_l']:>7.1f} "
          f"DD=${m['dd']:>7.0f} {prof}/{tot}yr")
    return {'name': name, 'overall': m, 'yearly': yr, 'params': params, 'trades': tr}


def main():
    workspace = Path("/home/shado/.openclaw/workspace")
    df = pd.read_csv(workspace / "data" / "MNQ_5min.csv")
    df['time'] = pd.to_datetime(df['time'])
    print(f"Loaded {len(df):,} bars\n")

    # V3a baseline (our current best)
    v3a = {
        'tick_size': 0.25, 'tick_value': 0.50,
        'rth_only': True, 'rth_start': '08:30', 'rth_end': '15:00',
        'trend_ema_period': 20, 'trend_slope_lookback': 10, 'trend_slope_threshold': 0.03,
        'sr_lookback': 100, 'sr_proximity_ticks': 8, 'sr_min_touches': 2,
        'pullback_min_size': 0.3, 'pattern_timeout': 30, 'pattern_validity': 3,
        'stop_offset_ticks': 1, 'max_hold_bars': 40,
        'daily_loss_limit': -200, 'max_consecutive_losses': 4,
        'ema_pullback_enabled': False, 'counter_trend_allowed': False,
        'use_breakeven_trail': False, 'use_atr_trail': False,
        'min_signal_quality': 60, 'min_body_ratio': 0.3,
        'max_stop_atr': 1.5, 'reward_risk_ratio': 1.5, 'min_target_ticks': 6,
        'sideways_entries_allowed': False, 'allow_shorts': False,
        'min_stop_ticks': 0, 'min_bars_before_stop': 0,
    }

    results = []

    # === BASELINE ===
    print("=== BASELINE (V3a) ===")
    r = run(df, "V3a_baseline", v3a)
    if r: results.append(r)

    # === 1. GRACE PERIOD (don't stop on first N bars) ===
    print("\n=== GRACE PERIOD ===")
    for grace in [1, 2, 3]:
        p = {**v3a, 'min_bars_before_stop': grace}
        r = run(df, f"grace_{grace}bar", p)
        if r: results.append(r)

    # === 2. MINIMUM STOP DISTANCE ===
    print("\n=== MIN STOP DISTANCE ===")
    for ms in [10, 15, 20, 25]:
        p = {**v3a, 'min_stop_ticks': ms}
        r = run(df, f"minstop_{ms}t", p)
        if r: results.append(r)

    # === 3. ATR TRAILING STOP (let winners run) ===
    print("\n=== ATR TRAILING STOP ===")
    for act in [0.5, 1.0, 1.5]:
        for dist in [0.5, 0.75, 1.0, 1.5]:
            p = {**v3a, 'use_atr_trail': True, 'atr_trail_activation': act,
                 'atr_trail_distance': dist, 'max_hold_bars': 60}
            r = run(df, f"trail_a{act}_d{dist}", p)
            if r: results.append(r)

    # === 4. TIME FILTERS ===
    print("\n=== TIME FILTERS ===")
    for start, end in [('09:00', '15:00'), ('09:00', '14:00'), ('09:30', '14:30'),
                        ('09:00', '13:00'), ('09:30', '13:30')]:
        p = {**v3a, 'rth_start': start, 'rth_end': end}
        r = run(df, f"time_{start}-{end}", p)
        if r: results.append(r)

    # === 5. GRACE + MIN STOP COMBOS ===
    print("\n=== GRACE + MIN STOP COMBOS ===")
    for grace in [1, 2]:
        for ms in [10, 15, 20]:
            p = {**v3a, 'min_bars_before_stop': grace, 'min_stop_ticks': ms}
            r = run(df, f"g{grace}_ms{ms}", p)
            if r: results.append(r)

    # === 6. TRAIL + GRACE COMBOS ===
    print("\n=== TRAIL + GRACE COMBOS ===")
    for grace in [1, 2]:
        for act, dist in [(1.0, 0.75), (1.0, 1.0), (0.5, 0.75), (1.5, 1.0)]:
            p = {**v3a, 'use_atr_trail': True, 'min_bars_before_stop': grace,
                 'atr_trail_activation': act, 'atr_trail_distance': dist, 'max_hold_bars': 60}
            r = run(df, f"tg{grace}_a{act}_d{dist}", p)
            if r: results.append(r)

    # === 7. BEST COMBOS: grace + minstop + time ===
    print("\n=== TRIPLE COMBOS ===")
    combos = [
        ('combo_a', {'min_bars_before_stop': 1, 'min_stop_ticks': 15, 'rth_start': '09:00', 'rth_end': '15:00'}),
        ('combo_b', {'min_bars_before_stop': 2, 'min_stop_ticks': 15, 'rth_start': '09:00', 'rth_end': '15:00'}),
        ('combo_c', {'min_bars_before_stop': 1, 'min_stop_ticks': 10, 'rth_start': '09:00', 'rth_end': '14:00'}),
        ('combo_d', {'min_bars_before_stop': 2, 'min_stop_ticks': 15, 'rth_start': '09:00', 'rth_end': '14:00'}),
        ('combo_e', {'min_bars_before_stop': 1, 'min_stop_ticks': 20, 'rth_start': '09:00', 'rth_end': '15:00'}),
    ]
    for name, overrides in combos:
        p = {**v3a, **overrides}
        r = run(df, name, p)
        if r: results.append(r)

    # === 8. TRAIL + TIME + GRACE ===
    print("\n=== TRAIL + TIME + GRACE ===")
    trail_combos = [
        ('trail_combo_a', {'use_atr_trail': True, 'atr_trail_activation': 1.0, 'atr_trail_distance': 0.75,
                           'min_bars_before_stop': 1, 'rth_start': '09:00', 'max_hold_bars': 60}),
        ('trail_combo_b', {'use_atr_trail': True, 'atr_trail_activation': 1.0, 'atr_trail_distance': 1.0,
                           'min_bars_before_stop': 2, 'rth_start': '09:00', 'max_hold_bars': 60}),
        ('trail_combo_c', {'use_atr_trail': True, 'atr_trail_activation': 0.5, 'atr_trail_distance': 0.75,
                           'min_bars_before_stop': 1, 'min_stop_ticks': 15, 'rth_start': '09:00', 'max_hold_bars': 60}),
        ('trail_combo_d', {'use_atr_trail': True, 'atr_trail_activation': 1.5, 'atr_trail_distance': 1.0,
                           'min_bars_before_stop': 1, 'rth_start': '09:00', 'max_hold_bars': 80}),
    ]
    for name, overrides in trail_combos:
        p = {**v3a, **overrides}
        r = run(df, name, p)
        if r: results.append(r)

    # === 9. R:R variants with grace ===
    print("\n=== R:R + GRACE ===")
    for rr in [1.5, 2.0, 2.5, 3.0]:
        p = {**v3a, 'reward_risk_ratio': rr, 'min_bars_before_stop': 1, 'rth_start': '09:00'}
        r = run(df, f"rr{rr}_g1", p)
        if r: results.append(r)

    # === 10. Pullback depth ===
    print("\n=== PULLBACK DEPTH ===")
    for pb in [0.3, 0.5, 0.7, 1.0]:
        p = {**v3a, 'pullback_min_size': pb, 'min_bars_before_stop': 1, 'rth_start': '09:00'}
        r = run(df, f"pb{pb}_g1", p)
        if r: results.append(r)

    # Sort by PF
    results.sort(key=lambda x: x['overall']['pf'], reverse=True)

    # Print top 25
    print(f"\n{'='*120}")
    print(f"TOP 25 CONFIGS (sorted by PF)")
    print(f"{'='*120}")
    print(f"{'Config':<28s} {'Tr':>5} {'TPD':>5} {'WR%':>5} {'PF':>5} {'P&L':>9} "
          f"{'AvgW':>7} {'AvgL':>7} {'DD':>8} {'PY':>5}")
    print("-"*120)
    for r in results[:25]:
        m = r['overall']
        yr = r['yearly']
        py = sum(1 for y, d in yr.items() if d['pnl'] > 0)
        ty = len(yr)
        print(f"{r['name']:<28s} {m['trades']:>5} {m['tpd']:>5} {m['wr']:>5} {m['pf']:>5} "
              f"${m['pnl']:>8.0f} ${m['avg_w']:>6.1f} ${m['avg_l']:>6.1f} ${m['dd']:>7.0f} {py}/{ty}")

    # Print yearly for top 5
    print(f"\n{'='*120}")
    print("TOP 5 YEARLY BREAKDOWNS")
    print(f"{'='*120}")
    for r in results[:5]:
        print(f"\n  {r['name']} (PF={r['overall']['pf']}, {r['overall']['trades']} trades)")
        for y, ym in r['yearly'].items():
            flag = "+" if ym['pnl'] > 0 else "-"
            print(f"    {y}: {ym['trades']:>4} tr {ym['tpd']:.1f}/d WR={ym['wr']:>5.1f}% "
                  f"PF={ym['pf']:>5.2f} P&L=${ym['pnl']:>7.0f} {flag}")

    # Save top config trades
    output_dir = workspace / "research" / "al_brooks_system" / "backtests" / "v2"
    if results:
        best = results[0]
        best['trades'].to_csv(output_dir / "v4_best_trades.csv", index=False)
        summary = [{'name': r['name'], 'overall': r['overall'],
                    'yearly': {str(k): v for k, v in r['yearly'].items()}}
                   for r in results[:10]]
        with open(output_dir / "v4_sweep_results.json", 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"\nBest '{best['name']}' saved to {output_dir}")


if __name__ == "__main__":
    main()
