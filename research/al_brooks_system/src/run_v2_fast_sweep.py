"""
Fast sweep: Test on 2-year subset (2023-2024), then validate best on full set
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


def run(df, name, params):
    s = AlBrooksV2Strategy(params)
    tr = s.run_backtest(df, verbose=False)
    if len(tr) == 0:
        return None
    m = calc(tr)
    return {'name': name, 'overall': m, 'params': params}


def main():
    workspace = Path("/home/shado/.openclaw/workspace")
    df_full = pd.read_csv(workspace / "data" / "MNQ_5min.csv")
    df_full['time'] = pd.to_datetime(df_full['time'])

    # Use 2023-2024 as development set (~2 years)
    mask = (df_full['time'] >= '2023-01-01') & (df_full['time'] < '2025-01-01')
    df_dev = df_full[mask].copy()
    print(f"Dev set: {len(df_dev):,} bars ({df_dev['time'].min()} to {df_dev['time'].max()})")

    base = {
        'tick_size': 0.25, 'tick_value': 0.50,
        'rth_only': True, 'rth_start': '08:30', 'rth_end': '15:00',
        'trend_ema_period': 20, 'trend_slope_lookback': 10,
        'sr_lookback': 100, 'sr_proximity_ticks': 8, 'sr_min_touches': 2,
        'pullback_min_size': 0.3, 'pattern_timeout': 30, 'pattern_validity': 3,
        'stop_offset_ticks': 1, 'max_hold_bars': 40,
        'daily_loss_limit': -200, 'max_consecutive_losses': 4,
        'ema_pullback_enabled': False,
        'counter_trend_allowed': False,
        'with_trend_needs_sr': False,
        'use_breakeven_trail': False,
        'min_body_ratio': 0.3,
        'min_target_ticks': 6,
    }

    results = []

    # Grid: quality x R:R x stop
    print("\n=== GRID SWEEP (Quality × R:R × Stop) ===")
    for q in [50, 60, 70]:
        for rr in [1.0, 1.25, 1.5, 2.0]:
            for stop in [1.0, 1.5, 2.0]:
                name = f"Q{q}_RR{rr}_S{stop}"
                p = {**base, 'trend_slope_threshold': 0.03,
                     'min_signal_quality': q, 'max_stop_atr': stop, 'reward_risk_ratio': rr}
                r = run(df_dev, name, p)
                if r:
                    results.append(r)

    # Add some with body ratio and trend slope
    print("\n=== BODY + SLOPE VARIANTS ===")
    for body in [0.3, 0.4, 0.5]:
        for slope in [0.03, 0.05]:
            name = f"B{body}_TS{slope}"
            p = {**base, 'trend_slope_threshold': slope, 'min_body_ratio': body,
                 'min_signal_quality': 60, 'max_stop_atr': 1.5, 'reward_risk_ratio': 1.5}
            r = run(df_dev, name, p)
            if r:
                results.append(r)

    # RTH end variants
    print("\n=== RTH END ===")
    for end in ['13:30', '14:00', '14:30']:
        name = f"End{end}"
        p = {**base, 'rth_end': end, 'trend_slope_threshold': 0.03,
             'min_signal_quality': 60, 'max_stop_atr': 1.5, 'reward_risk_ratio': 1.5}
        r = run(df_dev, name, p)
        if r:
            results.append(r)

    # Pullback size
    print("\n=== PULLBACK SIZE ===")
    for pb in [0.2, 0.3, 0.5, 0.7]:
        name = f"PB{pb}"
        p = {**base, 'pullback_min_size': pb, 'trend_slope_threshold': 0.03,
             'min_signal_quality': 60, 'max_stop_atr': 1.5, 'reward_risk_ratio': 1.5}
        r = run(df_dev, name, p)
        if r:
            results.append(r)

    # EMA pullback variants (tight)
    print("\n=== EMA PULLBACK TIGHT ===")
    for prox in [0.3, 0.5]:
        for q in [60, 70]:
            name = f"EMA_p{prox}_q{q}"
            p = {**base, 'ema_pullback_enabled': True, 'ema_pullback_proximity': prox,
                 'trend_slope_threshold': 0.05, 'min_signal_quality': q,
                 'min_body_ratio': 0.4, 'max_stop_atr': 1.5, 'reward_risk_ratio': 1.5}
            r = run(df_dev, name, p)
            if r:
                results.append(r)

    # Sort by PF
    results.sort(key=lambda x: x['overall']['pf'], reverse=True)

    print(f"\n{'='*110}")
    print(f"TOP 20 CONFIGS (sorted by PF, dev set 2023-2024)")
    print(f"{'='*110}")
    print(f"{'Config':<20} {'Tr':>5} {'TPD':>5} {'WR%':>5} {'PF':>5} {'P&L':>9} "
          f"{'AvgW':>7} {'AvgL':>7} {'DD':>8}")
    print("-"*110)
    for r in results[:20]:
        m = r['overall']
        print(f"{r['name']:<20} {m['trades']:>5} {m['tpd']:>5} {m['wr']:>5} {m['pf']:>5} "
              f"${m['pnl']:>8.0f} ${m['avg_w']:>6.1f} ${m['avg_l']:>6.1f} ${m['dd']:>7.0f}")

    # Validate top 5 on full dataset
    print(f"\n{'='*110}")
    print(f"VALIDATION ON FULL DATASET (2019-2026)")
    print(f"{'='*110}")

    for r in results[:5]:
        name = f"FULL_{r['name']}"
        params = r['params']
        s = AlBrooksV2Strategy(params)
        tr = s.run_backtest(df_full, verbose=False)
        if len(tr) == 0:
            print(f"  {name}: NO TRADES")
            continue
        m = calc(tr)

        # Yearly
        tr_copy = tr.copy()
        tr_copy['year'] = pd.to_datetime(tr_copy['entry_time']).dt.year
        yearly_results = {}
        for y in sorted(tr_copy['year'].unique()):
            yt = tr_copy[tr_copy['year'] == y]
            yearly_results[y] = calc(yt)

        prof = sum(1 for y, d in yearly_results.items() if d['pnl'] > 0)
        tot = len(yearly_results)

        print(f"\n  {name}: {m['trades']} tr | {m['tpd']}/d | WR={m['wr']}% | PF={m['pf']} | "
              f"P&L=${m['pnl']:.0f} | W=${m['avg_w']:.1f} L=${m['avg_l']:.1f} | DD=${m['dd']:.0f} | {prof}/{tot}yr")
        for y, ym in yearly_results.items():
            flag = "+" if ym['pnl'] > 0 else "-"
            print(f"    {y}: {ym['trades']} tr {ym['tpd']}/d WR={ym['wr']}% PF={ym['pf']} P&L=${ym['pnl']:.0f} {flag}")


if __name__ == "__main__":
    main()
