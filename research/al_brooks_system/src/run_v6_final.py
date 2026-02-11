"""
V6 Final: Grace 4-6 + Trail combos + Split-sample validation
Goal: Find absolute best config AND validate it's not overfit
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

    base = {
        'tick_size': 0.25, 'tick_value': 0.50,
        'rth_only': True, 'rth_start': '08:30', 'rth_end': '15:00',
        'trend_ema_period': 20, 'trend_slope_lookback': 10, 'trend_slope_threshold': 0.03,
        'sr_lookback': 100, 'sr_proximity_ticks': 8, 'sr_min_touches': 2,
        'pullback_min_size': 0.3, 'pattern_timeout': 30, 'pattern_validity': 3,
        'stop_offset_ticks': 1,
        'daily_loss_limit': -200, 'max_consecutive_losses': 4,
        'ema_pullback_enabled': False, 'counter_trend_allowed': False,
        'use_breakeven_trail': False,
        'min_signal_quality': 60, 'min_body_ratio': 0.3,
        'max_stop_atr': 1.5, 'reward_risk_ratio': 1.5, 'min_target_ticks': 6,
        'sideways_entries_allowed': False, 'allow_shorts': False,
        'min_stop_ticks': 0,
    }

    # ============================================================
    # PART 1: Grace 4-7 × Trail grid on FULL dataset
    # ============================================================
    print("=" * 130, flush=True)
    print("PART 1: GRACE × TRAIL GRID (Full dataset)", flush=True)
    print("=" * 130, flush=True)

    results = []
    for grace in [3, 4, 5, 6, 7]:
        print(f"\n--- Grace {grace} ---", flush=True)

        # No trail (baseline for each grace)
        p = {**base, 'min_bars_before_stop': grace, 'max_hold_bars': 40}
        r = run(df, f"g{grace}_notrl", p)
        if r: results.append(r)

        # Trail combos
        for act in [0.5, 1.0, 1.5]:
            for dist in [0.5, 0.75, 1.0]:
                p = {**base, 'min_bars_before_stop': grace,
                     'use_atr_trail': True, 'atr_trail_activation': act,
                     'atr_trail_distance': dist, 'max_hold_bars': 80}
                r = run(df, f"g{grace}_a{act}_d{dist}", p)
                if r: results.append(r)

    results.sort(key=lambda x: x['overall']['pf'], reverse=True)

    print(f"\n{'='*130}", flush=True)
    print(f"TOP 20 CONFIGS (sorted by PF)", flush=True)
    print(f"{'='*130}", flush=True)
    print(f"{'Config':<35s} {'Tr':>5} {'TPD':>5} {'WR%':>5} {'PF':>5} {'P&L':>9} "
          f"{'AvgW':>7} {'AvgL':>7} {'DD':>8} {'PY':>5}", flush=True)
    print("-"*130, flush=True)
    for r in results[:20]:
        m = r['overall']
        yr = r['yearly']
        py = sum(1 for y, d in yr.items() if d['pnl'] > 0)
        ty = len(yr)
        print(f"{r['name']:<35s} {m['trades']:>5} {m['tpd']:>5} {m['wr']:>5} {m['pf']:>5} "
              f"${m['pnl']:>8.0f} ${m['avg_w']:>6.1f} ${m['avg_l']:>6.1f} ${m['dd']:>7.0f} {py}/{ty}", flush=True)

    # ============================================================
    # PART 2: Split-sample validation for top 5
    # ============================================================
    print(f"\n\n{'='*130}", flush=True)
    print("PART 2: SPLIT-SAMPLE VALIDATION (Train: 2019-2022, Test: 2023-2026)", flush=True)
    print(f"{'='*130}", flush=True)

    # Split data
    split_date = pd.Timestamp('2023-01-01')
    train = df[df['time'] < split_date].copy()
    test = df[df['time'] >= split_date].copy()
    print(f"Train: {len(train):,} bars, Test: {len(test):,} bars\n", flush=True)

    top5 = results[:5]
    for r in top5:
        name = r['name']
        params = r['params']

        # Train
        s_train = AlBrooksV2Strategy(params)
        tr_train = s_train.run_backtest(train, verbose=False)
        m_train = calc(tr_train) if len(tr_train) > 0 else None

        # Test
        s_test = AlBrooksV2Strategy(params)
        tr_test = s_test.run_backtest(test, verbose=False)
        m_test = calc(tr_test) if len(tr_test) > 0 else None

        if m_train and m_test:
            print(f"  {name}:", flush=True)
            print(f"    TRAIN (2019-2022): {m_train['trades']} tr {m_train['tpd']}/d "
                  f"WR={m_train['wr']}% PF={m_train['pf']} P&L=${m_train['pnl']:.0f} DD=${m_train['dd']:.0f}", flush=True)
            print(f"    TEST  (2023-2026): {m_test['trades']} tr {m_test['tpd']}/d "
                  f"WR={m_test['wr']}% PF={m_test['pf']} P&L=${m_test['pnl']:.0f} DD=${m_test['dd']:.0f}", flush=True)
            ratio = m_test['pf'] / m_train['pf'] if m_train['pf'] > 0 else 0
            print(f"    RATIO: {ratio:.2f} (test/train PF)", flush=True)

    # ============================================================
    # PART 3: Walk-forward (4 folds of 2 years each, 50/50 IS/OOS)
    # ============================================================
    print(f"\n\n{'='*130}", flush=True)
    print("PART 3: WALK-FORWARD VALIDATION (2-year folds)", flush=True)
    print(f"{'='*130}", flush=True)

    folds = [
        ("2019-2020", "2021-2022", pd.Timestamp('2019-01-01'), pd.Timestamp('2021-01-01'), pd.Timestamp('2023-01-01')),
        ("2020-2021", "2022-2023", pd.Timestamp('2020-01-01'), pd.Timestamp('2022-01-01'), pd.Timestamp('2024-01-01')),
        ("2021-2022", "2023-2024", pd.Timestamp('2021-01-01'), pd.Timestamp('2023-01-01'), pd.Timestamp('2025-01-01')),
        ("2023-2024", "2025-2026", pd.Timestamp('2023-01-01'), pd.Timestamp('2025-01-01'), pd.Timestamp('2027-01-01')),
    ]

    # Test top 3 configs across folds
    top3 = results[:3]
    for r in top3:
        name = r['name']
        params = r['params']
        print(f"\n  {name}:", flush=True)

        oos_pfs = []
        for fold_name_is, fold_name_oos, start, mid, end in folds:
            fold_is = df[(df['time'] >= start) & (df['time'] < mid)]
            fold_oos = df[(df['time'] >= mid) & (df['time'] < end)]

            s_is = AlBrooksV2Strategy(params)
            tr_is = s_is.run_backtest(fold_is, verbose=False)
            m_is = calc(tr_is) if len(tr_is) > 0 else None

            s_oos = AlBrooksV2Strategy(params)
            tr_oos = s_oos.run_backtest(fold_oos, verbose=False)
            m_oos = calc(tr_oos) if len(tr_oos) > 0 else None

            if m_is and m_oos:
                oos_pfs.append(m_oos['pf'])
                print(f"    IS={fold_name_is}: PF={m_is['pf']:>5.2f} ({m_is['trades']} tr)  "
                      f"OOS={fold_name_oos}: PF={m_oos['pf']:>5.2f} ({m_oos['trades']} tr)", flush=True)

        if oos_pfs:
            avg_oos = np.mean(oos_pfs)
            min_oos = min(oos_pfs)
            all_profitable = all(pf > 1.0 for pf in oos_pfs)
            print(f"    ==> OOS avg PF={avg_oos:.2f}, min={min_oos:.2f}, "
                  f"all profitable: {'YES' if all_profitable else 'NO'}", flush=True)

    # ============================================================
    # PART 4: Yearly breakdown for #1 config
    # ============================================================
    print(f"\n\n{'='*130}", flush=True)
    print(f"BEST CONFIG YEARLY BREAKDOWN: {results[0]['name']}", flush=True)
    print(f"{'='*130}", flush=True)
    best = results[0]
    for y, ym in best['yearly'].items():
        flag = "+" if ym['pnl'] > 0 else "-"
        print(f"  {y}: {ym['trades']:>4} tr {ym['tpd']:.1f}/d WR={ym['wr']:>5.1f}% "
              f"PF={ym['pf']:>5.2f} P&L=${ym['pnl']:>7.0f} DD=${ym['dd']:>7.0f} {flag}", flush=True)

    # Save
    output_dir = workspace / "research" / "al_brooks_system" / "backtests" / "v2"
    if results:
        best = results[0]
        best['trades'].to_csv(output_dir / "v6_best_trades.csv", index=False)
        summary = [{'name': r['name'], 'overall': r['overall'],
                    'yearly': {str(k): v for k, v in r['yearly'].items()},
                    'params': {k: v for k, v in r['params'].items()}}
                   for r in results[:10]]
        with open(output_dir / "v6_sweep_results.json", 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"\nResults saved to {output_dir}", flush=True)


if __name__ == "__main__":
    main()
