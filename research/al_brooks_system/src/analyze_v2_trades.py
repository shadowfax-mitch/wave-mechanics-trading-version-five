"""
Deep analysis of V2 Config F trades to find edge concentration
"""
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from al_brooks_v2_strategy import AlBrooksV2Strategy


def calc(trades_df, label=""):
    if len(trades_df) == 0:
        return f"  {label}: 0 trades"
    t = len(trades_df)
    w = trades_df[trades_df['pnl_dollars'] > 0]
    l = trades_df[trades_df['pnl_dollars'] <= 0]
    gp = w['pnl_dollars'].sum() if len(w) > 0 else 0
    gl = abs(l['pnl_dollars'].sum()) if len(l) > 0 else 0
    pf = gp / gl if gl > 0 else 99
    pnl = trades_df['pnl_dollars'].sum()
    wr = len(w) / t * 100
    days = pd.to_datetime(trades_df['entry_time']).dt.date.nunique()
    tpd = t / days if days > 0 else 0
    return (f"  {label:<25s}: {t:>5} tr | {tpd:.1f}/d | WR={wr:.1f}% | PF={pf:.2f} | "
            f"P&L=${pnl:.0f} | AvgPnl=${pnl/t:.2f}")


def main():
    workspace = Path("/home/shado/.openclaw/workspace")
    df = pd.read_csv(workspace / "data" / "MNQ_5min.csv")
    df['time'] = pd.to_datetime(df['time'])

    # Config F: H2/L2, no trail, quality 60
    params = {
        'tick_size': 0.25, 'tick_value': 0.50,
        'rth_only': True, 'rth_start': '08:30', 'rth_end': '15:00',
        'trend_ema_period': 20, 'trend_slope_lookback': 10,
        'trend_slope_threshold': 0.03,
        'sr_lookback': 100, 'sr_proximity_ticks': 8, 'sr_min_touches': 2,
        'pullback_min_size': 0.3, 'pattern_timeout': 30, 'pattern_validity': 3,
        'stop_offset_ticks': 1, 'max_hold_bars': 40,
        'daily_loss_limit': -200, 'max_consecutive_losses': 4,
        'ema_pullback_enabled': False, 'counter_trend_allowed': False,
        'with_trend_needs_sr': False, 'use_breakeven_trail': False,
        'min_signal_quality': 60, 'min_body_ratio': 0.3,
        'max_stop_atr': 1.5, 'reward_risk_ratio': 1.5, 'min_target_ticks': 6,
    }

    print("Running Config F on full dataset...")
    strategy = AlBrooksV2Strategy(params)
    trades = strategy.run_backtest(df, verbose=True)
    print(f"\nTotal trades: {len(trades)}")

    # Add analysis columns
    trades['entry_time'] = pd.to_datetime(trades['entry_time'])
    trades['hour'] = trades['entry_time'].dt.hour
    trades['minute'] = trades['entry_time'].dt.minute
    trades['time_slot'] = trades['hour'].astype(str) + ':' + (trades['minute'] // 30 * 30).astype(str).str.zfill(2)
    trades['is_winner'] = trades['pnl_dollars'] > 0

    # === TIME OF DAY ===
    print("\n" + "=" * 90)
    print("TIME-OF-DAY ANALYSIS")
    print("=" * 90)

    # By hour
    print("\nBy Hour:")
    for h in sorted(trades['hour'].unique()):
        ht = trades[trades['hour'] == h]
        print(calc(ht, f"Hour {h:02d}"))

    # By 30-min block
    print("\nBy 30-min Block:")
    for slot in sorted(trades['time_slot'].unique()):
        st = trades[trades['time_slot'] == slot]
        print(calc(st, slot))

    # === PATTERN TYPE ===
    print("\n" + "=" * 90)
    print("PATTERN ANALYSIS")
    print("=" * 90)
    for p in trades['pattern'].unique():
        pt = trades[trades['pattern'] == p]
        print(calc(pt, p))

    # === TREND ===
    print("\n" + "=" * 90)
    print("TREND ANALYSIS")
    print("=" * 90)
    for t_val in trades['trend'].unique():
        tt = trades[trades['trend'] == t_val]
        print(calc(tt, t_val))

    # Pattern × Trend
    print("\nPattern × Trend:")
    for p in trades['pattern'].unique():
        for t_val in trades['trend'].unique():
            combo = trades[(trades['pattern'] == p) & (trades['trend'] == t_val)]
            if len(combo) > 10:
                print(calc(combo, f"{p} + {t_val}"))

    # === KEY LEVEL ===
    print("\n" + "=" * 90)
    print("S/R ANALYSIS")
    print("=" * 90)
    for kl in trades['key_level'].unique():
        kt = trades[trades['key_level'] == kl]
        print(calc(kt, kl))

    # === EXIT REASON ===
    print("\n" + "=" * 90)
    print("EXIT REASON")
    print("=" * 90)
    for r in trades['exit_reason'].unique():
        rt = trades[trades['exit_reason'] == r]
        print(calc(rt, r))

    # === BARS HELD ===
    print("\n" + "=" * 90)
    print("BARS HELD DISTRIBUTION")
    print("=" * 90)
    for bucket in [(1, 1), (2, 2), (3, 5), (6, 10), (11, 20), (21, 40)]:
        lo, hi = bucket
        bt = trades[(trades['bars_held'] >= lo) & (trades['bars_held'] <= hi)]
        if len(bt) > 0:
            print(calc(bt, f"Bars {lo}-{hi}"))

    # === ATR REGIME ===
    print("\n" + "=" * 90)
    print("ATR REGIME (by percentile)")
    print("=" * 90)
    atr_quartiles = trades['atr'].quantile([0.25, 0.5, 0.75])
    q1, q2, q3 = atr_quartiles.values
    for label, mask in [
        (f"Low ATR (<{q1:.1f})", trades['atr'] < q1),
        (f"Med ATR ({q1:.1f}-{q2:.1f})", (trades['atr'] >= q1) & (trades['atr'] < q2)),
        (f"High ATR ({q2:.1f}-{q3:.1f})", (trades['atr'] >= q2) & (trades['atr'] < q3)),
        (f"VHigh ATR (>{q3:.1f})", trades['atr'] >= q3),
    ]:
        at = trades[mask]
        if len(at) > 0:
            print(calc(at, label))

    # === SIGNAL QUALITY ===
    print("\n" + "=" * 90)
    print("SIGNAL QUALITY SCORE BUCKETS")
    print("=" * 90)
    for lo, hi in [(40, 59), (60, 79), (80, 99), (100, 120)]:
        qt = trades[(trades['signal_quality'] >= lo) & (trades['signal_quality'] <= hi)]
        if len(qt) > 0:
            print(calc(qt, f"Quality {lo}-{hi}"))

    # === STOP DISTANCE ===
    print("\n" + "=" * 90)
    print("STOP DISTANCE (ticks)")
    print("=" * 90)
    trades['stop_dist_ticks'] = abs(trades['entry_price'] - trades['stop_price']) / 0.25
    for lo, hi in [(0, 10), (11, 20), (21, 30), (31, 50), (51, 100)]:
        st = trades[(trades['stop_dist_ticks'] >= lo) & (trades['stop_dist_ticks'] <= hi)]
        if len(st) > 0:
            print(calc(st, f"Stop {lo}-{hi} ticks"))

    # === BEST FILTERS ===
    print("\n" + "=" * 90)
    print("POTENTIAL FILTER COMBINATIONS")
    print("=" * 90)

    # Exclude toxic hours
    filtered = trades[~trades['hour'].isin([8, 14])]
    print(calc(filtered, "No 8:xx or 14:xx"))

    # Only 9:30-13:30
    filtered = trades[(trades['hour'] >= 9) & ((trades['hour'] < 13) | ((trades['hour'] == 13) & (trades['minute'] < 30)))]
    print(calc(filtered, "9:00-13:30 only"))

    # Only H2 with-trend
    filtered = trades[(trades['pattern'] == 'H2') & (trades['trend'] == 'UP')]
    print(calc(filtered, "H2+UP only"))

    # Only L2 with-trend
    filtered = trades[(trades['pattern'] == 'L2') & (trades['trend'] == 'DOWN')]
    print(calc(filtered, "L2+DOWN only"))

    # With S/R confluence
    filtered = trades[trades['key_level'] != 'NONE']
    print(calc(filtered, "S/R confluence"))

    # No S/R
    filtered = trades[trades['key_level'] == 'NONE']
    print(calc(filtered, "No S/R"))

    # High quality only
    filtered = trades[trades['signal_quality'] >= 80]
    print(calc(filtered, "Quality >= 80"))

    # Tight stops only
    filtered = trades[trades['stop_dist_ticks'] <= 20]
    print(calc(filtered, "Stop <= 20 ticks"))

    # Combo: quality >= 80 + no toxic hours
    filtered = trades[(trades['signal_quality'] >= 80) & (~trades['hour'].isin([8, 14]))]
    print(calc(filtered, "Q80 + no toxic hours"))

    # Combo: quality >= 80 + tight stops
    filtered = trades[(trades['signal_quality'] >= 80) & (trades['stop_dist_ticks'] <= 20)]
    print(calc(filtered, "Q80 + stop<=20"))

    # Combo: 9:30-13:30 + quality >= 80
    filtered = trades[(trades['signal_quality'] >= 80) &
                     (trades['hour'] >= 9) &
                     ((trades['hour'] < 13) | ((trades['hour'] == 13) & (trades['minute'] < 30)))]
    print(calc(filtered, "Q80 + 9:00-13:30"))

    # Save full trades for inspection
    output = workspace / "research" / "al_brooks_system" / "backtests" / "v2"
    trades.to_csv(output / "config_f_all_trades.csv", index=False)
    print(f"\nTrades saved to {output / 'config_f_all_trades.csv'}")


if __name__ == "__main__":
    main()
