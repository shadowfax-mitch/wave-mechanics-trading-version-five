"""Diagnose where V2 signals are being filtered out"""
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent))
from al_brooks_v2_strategy import AlBrooksV2Strategy, Trend, PatternType


def main():
    workspace = Path("/home/shado/.openclaw/workspace")
    df = pd.read_csv(workspace / "data" / "MNQ_5min.csv")
    df['time'] = pd.to_datetime(df['time'])
    print(f"Loaded {len(df):,} bars")

    params = {
        'tick_size': 0.25, 'tick_value': 0.50,
        'rth_only': True, 'rth_start': '08:30', 'rth_end': '15:00',
        'trend_slope_threshold': 0.03, 'trend_slope_lookback': 10,
        'sr_lookback': 100, 'sr_proximity_ticks': 8, 'sr_min_touches': 2,
        'pullback_min_size': 0.3, 'pattern_timeout': 30, 'pattern_validity': 3,
        'ema_pullback_proximity': 1.0, 'min_signal_quality': 40,
        'min_body_ratio': 0.3, 'max_stop_atr': 1.5, 'reward_risk_ratio': 1.5,
        'min_target_ticks': 6, 'max_hold_bars': 40, 'use_breakeven_trail': True,
        'with_trend_needs_sr': False, 'counter_trend_allowed': True,
        'ema_pullback_enabled': True, 'daily_loss_limit': -200, 'max_consecutive_losses': 4,
    }

    strategy = AlBrooksV2Strategy(params)
    df_prep = strategy.prepare_data(df)

    # Sample bars from different years
    sample_years = [2020, 2021, 2022, 2023, 2024, 2025]

    # Count trends across dataset
    trend_counts = Counter()
    rth_count = 0
    valid_atr_count = 0
    h2_count = 0
    l2_count = 0
    ema_pb_long = 0
    ema_pb_short = 0

    # Reset state for fresh run
    strategy.reset_state()

    # Check a sample of bars
    total = len(df_prep)
    for idx in range(total):
        if idx % 100000 == 0:
            print(f"Scanning: {idx:,}/{total:,}")

        if not df_prep['is_rth'].iloc[idx]:
            continue
        rth_count += 1

        if pd.isna(df_prep['atr'].iloc[idx]) or df_prep['atr'].iloc[idx] <= 0:
            continue
        valid_atr_count += 1

        trend = strategy.detect_trend(df_prep, idx)
        trend_counts[trend.value] += 1

        # Update pattern states
        strategy.update_pattern_states(df_prep, idx)

        # Check patterns
        patterns = strategy.detect_patterns(df_prep, idx, trend)
        for p in patterns:
            if p == PatternType.SECOND_ENTRY_LONG:
                h2_count += 1
            elif p == PatternType.SECOND_ENTRY_SHORT:
                l2_count += 1
            elif p == PatternType.EMA_PULLBACK_LONG:
                ema_pb_long += 1
            elif p == PatternType.EMA_PULLBACK_SHORT:
                ema_pb_short += 1

    print(f"\n=== DIAGNOSTIC RESULTS ===")
    print(f"Total bars: {total:,}")
    print(f"RTH bars: {rth_count:,}")
    print(f"Valid ATR: {valid_atr_count:,}")
    print(f"\nTrend distribution:")
    for t, c in trend_counts.most_common():
        print(f"  {t}: {c:,} ({c/valid_atr_count*100:.1f}%)")
    print(f"\nPattern signals (raw, before quality/S/R filter):")
    print(f"  H2: {h2_count:,}")
    print(f"  L2: {l2_count:,}")
    print(f"  EMA PB Long: {ema_pb_long:,}")
    print(f"  EMA PB Short: {ema_pb_short:,}")
    print(f"  TOTAL: {h2_count + l2_count + ema_pb_long + ema_pb_short:,}")

    # Check by year
    print(f"\n=== PATTERN SIGNALS BY YEAR ===")
    strategy.reset_state()
    yearly_patterns = {}

    for idx in range(total):
        if not df_prep['is_rth'].iloc[idx]:
            continue
        if pd.isna(df_prep['atr'].iloc[idx]) or df_prep['atr'].iloc[idx] <= 0:
            continue

        year = df_prep.index[idx].year
        if year not in yearly_patterns:
            yearly_patterns[year] = Counter()

        trend = strategy.detect_trend(df_prep, idx)
        strategy.update_pattern_states(df_prep, idx)
        patterns = strategy.detect_patterns(df_prep, idx, trend)

        for p in patterns:
            yearly_patterns[year][p.value] += 1

    for year in sorted(yearly_patterns):
        c = yearly_patterns[year]
        total_p = sum(c.values())
        print(f"  {year}: {total_p} total — {dict(c)}")


if __name__ == "__main__":
    main()
