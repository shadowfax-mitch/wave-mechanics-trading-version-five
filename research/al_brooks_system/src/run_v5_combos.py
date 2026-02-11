"""
V5 Combo Sweep: Build on grace_3bar (PF=1.48) winner
Test combinations of grace_3bar + trailing stops, time filters, min stops, R:R
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
        print(f"  {name}: NO TRADES", flush=True)
        return None
    m = calc(tr)
    yr = yearly(tr)
    prof = sum(1 for y, r in yr.items() if r['pnl'] > 0)
    tot = len(yr)
    print(f"  {name:<35s} {m['trades']:>5} tr {m['tpd']:.1f}/d WR={m['wr']:>5.1f}% "
          f"PF={m['pf']:>5.2f} P&L=${m['pnl']:>8.0f} W=${m['avg_w']:>6.1f} L=${m['avg_l']:>7.1f} "
          f"DD=${m['dd']:>7.0f} {prof}/{tot}yr", flush=True)
    return {'name': name, 'overall': m, 'yearly': yr, 'params': params, 'trades': tr}


def main():
    workspace = Path("/home/shado/.openclaw/workspace")
    df = pd.read_csv(workspace / "data" / "MNQ_5min.csv")
    df['time'] = pd.to_datetime(df['time'])
    print(f"Loaded {len(df):,} bars\n", flush=True)

    # V3a baseline with grace_3bar (our new best = PF 1.48)
    base = {
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
        'min_stop_ticks': 0, 'min_bars_before_stop': 3,
    }

    results = []

    # === BASELINE: grace_3bar ===
    print("=== BASELINE (grace_3bar) ===", flush=True)
    r = run(df, "grace_3bar_baseline", base)
    if r: results.append(r)

    # === 1. GRACE 3 + TIME FILTERS ===
    print("\n=== GRACE 3 + TIME FILTERS ===", flush=True)
    for start, end, label in [
        ('09:00', '15:00', 'skip_open'),
        ('09:00', '14:00', '9am-2pm'),
        ('09:30', '14:30', '930-230'),
        ('09:00', '13:00', '9am-1pm'),
        ('08:30', '14:00', 'no_close'),
    ]:
        p = {**base, 'rth_start': start, 'rth_end': end}
        r = run(df, f"g3_t_{label}", p)
        if r: results.append(r)

    # === 2. GRACE 3 + MIN STOP ===
    print("\n=== GRACE 3 + MIN STOP ===", flush=True)
    for ms in [10, 15, 20]:
        p = {**base, 'min_stop_ticks': ms}
        r = run(df, f"g3_ms{ms}", p)
        if r: results.append(r)

    # === 3. GRACE 3 + TRAILING STOP (replace fixed target) ===
    print("\n=== GRACE 3 + ATR TRAIL ===", flush=True)
    for act in [0.5, 1.0, 1.5, 2.0]:
        for dist in [0.5, 0.75, 1.0, 1.5]:
            p = {**base, 'use_atr_trail': True, 'atr_trail_activation': act,
                 'atr_trail_distance': dist, 'max_hold_bars': 80}
            r = run(df, f"g3_trail_a{act}_d{dist}", p)
            if r: results.append(r)

    # === 4. GRACE 3 + R:R VARIANTS ===
    print("\n=== GRACE 3 + R:R ===", flush=True)
    for rr in [1.0, 1.25, 1.75, 2.0, 2.5, 3.0]:
        p = {**base, 'reward_risk_ratio': rr}
        r = run(df, f"g3_rr{rr}", p)
        if r: results.append(r)

    # === 5. GRACE 3 + MAX HOLD BARS ===
    print("\n=== GRACE 3 + HOLD BARS ===", flush=True)
    for mh in [20, 30, 60, 80]:
        p = {**base, 'max_hold_bars': mh}
        r = run(df, f"g3_hold{mh}", p)
        if r: results.append(r)

    # === 6. GRACE 4 and 5 ===
    print("\n=== GRACE 4, 5 ===", flush=True)
    for grace in [4, 5]:
        p = {**base, 'min_bars_before_stop': grace}
        r = run(df, f"grace_{grace}bar", p)
        if r: results.append(r)

    # === 7. TRIPLE COMBOS: grace3 + time + other ===
    print("\n=== TRIPLE COMBOS ===", flush=True)
    combos = [
        ('g3_t9_ms10', {'rth_start': '09:00', 'min_stop_ticks': 10}),
        ('g3_t9_ms15', {'rth_start': '09:00', 'min_stop_ticks': 15}),
        ('g3_t9_rr2', {'rth_start': '09:00', 'reward_risk_ratio': 2.0}),
        ('g3_t9_rr1.75', {'rth_start': '09:00', 'reward_risk_ratio': 1.75}),
        ('g3_t9_hold60', {'rth_start': '09:00', 'max_hold_bars': 60}),
        ('g3_t9_14_ms10', {'rth_start': '09:00', 'rth_end': '14:00', 'min_stop_ticks': 10}),
        ('g3_t9_14_rr2', {'rth_start': '09:00', 'rth_end': '14:00', 'reward_risk_ratio': 2.0}),
        ('g3_ms15_rr2', {'min_stop_ticks': 15, 'reward_risk_ratio': 2.0}),
        ('g3_ms10_rr1.75', {'min_stop_ticks': 10, 'reward_risk_ratio': 1.75}),
        ('g3_ms10_hold60', {'min_stop_ticks': 10, 'max_hold_bars': 60}),
    ]
    for name, overrides in combos:
        p = {**base, **overrides}
        r = run(df, name, p)
        if r: results.append(r)

    # === 8. GRACE 3 + TRAIL + TIME ===
    print("\n=== GRACE 3 + TRAIL + TIME ===", flush=True)
    trail_combos = [
        ('g3_t9_tr_a1_d075', {'rth_start': '09:00', 'use_atr_trail': True,
                               'atr_trail_activation': 1.0, 'atr_trail_distance': 0.75, 'max_hold_bars': 80}),
        ('g3_t9_tr_a15_d1', {'rth_start': '09:00', 'use_atr_trail': True,
                              'atr_trail_activation': 1.5, 'atr_trail_distance': 1.0, 'max_hold_bars': 80}),
        ('g3_t9_tr_a05_d075', {'rth_start': '09:00', 'use_atr_trail': True,
                                'atr_trail_activation': 0.5, 'atr_trail_distance': 0.75, 'max_hold_bars': 80}),
        ('g3_t9_tr_a2_d1', {'rth_start': '09:00', 'use_atr_trail': True,
                             'atr_trail_activation': 2.0, 'atr_trail_distance': 1.0, 'max_hold_bars': 80}),
    ]
    for name, overrides in trail_combos:
        p = {**base, **overrides}
        r = run(df, name, p)
        if r: results.append(r)

    # === 9. ATR STOP CAP VARIANTS ===
    print("\n=== GRACE 3 + ATR CAP ===", flush=True)
    for cap in [1.0, 1.25, 2.0]:
        p = {**base, 'max_stop_atr': cap}
        r = run(df, f"g3_cap{cap}atr", p)
        if r: results.append(r)

    # Sort by PF
    results.sort(key=lambda x: x['overall']['pf'], reverse=True)

    # Print top 30
    print(f"\n{'='*130}", flush=True)
    print(f"TOP 30 CONFIGS (sorted by PF)", flush=True)
    print(f"{'='*130}", flush=True)
    print(f"{'Config':<35s} {'Tr':>5} {'TPD':>5} {'WR%':>5} {'PF':>5} {'P&L':>9} "
          f"{'AvgW':>7} {'AvgL':>7} {'DD':>8} {'PY':>5}", flush=True)
    print("-"*130, flush=True)
    for r in results[:30]:
        m = r['overall']
        yr = r['yearly']
        py = sum(1 for y, d in yr.items() if d['pnl'] > 0)
        ty = len(yr)
        print(f"{r['name']:<35s} {m['trades']:>5} {m['tpd']:>5} {m['wr']:>5} {m['pf']:>5} "
              f"${m['pnl']:>8.0f} ${m['avg_w']:>6.1f} ${m['avg_l']:>6.1f} ${m['dd']:>7.0f} {py}/{ty}", flush=True)

    # Print yearly for top 5
    print(f"\n{'='*130}", flush=True)
    print("TOP 5 YEARLY BREAKDOWNS", flush=True)
    print(f"{'='*130}", flush=True)
    for r in results[:5]:
        print(f"\n  {r['name']} (PF={r['overall']['pf']}, {r['overall']['trades']} trades)", flush=True)
        for y, ym in r['yearly'].items():
            flag = "+" if ym['pnl'] > 0 else "-"
            print(f"    {y}: {ym['trades']:>4} tr {ym['tpd']:.1f}/d WR={ym['wr']:>5.1f}% "
                  f"PF={ym['pf']:>5.2f} P&L=${ym['pnl']:>7.0f} {flag}", flush=True)

    # Save results
    output_dir = workspace / "research" / "al_brooks_system" / "backtests" / "v2"
    if results:
        best = results[0]
        best['trades'].to_csv(output_dir / "v5_best_trades.csv", index=False)
        summary = [{'name': r['name'], 'overall': r['overall'],
                    'yearly': {str(k): v for k, v in r['yearly'].items()},
                    'params': {k: v for k, v in r['params'].items() if k != 'trades'}}
                   for r in results[:15]]
        with open(output_dir / "v5_sweep_results.json", 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"\nBest '{best['name']}' saved to {output_dir}", flush=True)
        print(f"\nBest params: {json.dumps(best['params'], indent=2, default=str)}", flush=True)


if __name__ == "__main__":
    main()
