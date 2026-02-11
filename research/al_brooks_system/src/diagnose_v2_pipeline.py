"""Diagnose the signal-to-trade conversion pipeline"""
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent))
from al_brooks_v2_strategy import AlBrooksV2Strategy, Trend, PatternType


class DiagnosticV2(AlBrooksV2Strategy):
    """V2 with diagnostic counters injected"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.diag = Counter()

    def _check_entry_signals(self, df, idx):
        self.diag['check_called'] += 1

        trend = self.detect_trend(df, idx)
        patterns = self.detect_patterns(df, idx, trend)

        if not patterns:
            self.diag['no_pattern'] += 1
            return

        self.diag['has_pattern'] += 1
        pattern = patterns[0]
        self.diag[f'pattern_{pattern.value}'] += 1

        # Signal bar quality
        signal_bar = self.analyze_signal_bar(df, idx, pattern)
        if signal_bar.quality_score < self.params['min_signal_quality']:
            self.diag['quality_reject'] += 1
            self.diag[f'quality_reject_{pattern.value}'] += 1
            return

        self.diag['quality_pass'] += 1

        # S/R check
        is_long = pattern in [PatternType.SECOND_ENTRY_LONG, PatternType.EMA_PULLBACK_LONG]
        is_with_trend = (is_long and trend == Trend.UP) or (not is_long and trend == Trend.DOWN)
        is_counter_trend = (is_long and trend == Trend.DOWN) or (not is_long and trend == Trend.UP)

        key_level = None

        if is_counter_trend:
            if not self.params['counter_trend_allowed']:
                self.diag['counter_trend_blocked'] += 1
                return
            key_level = self.is_at_key_level(df, idx, self.key_levels)
            if key_level is None:
                self.diag['sr_reject_counter'] += 1
                return
        elif is_with_trend:
            self.diag['with_trend_signal'] += 1
            if self.params['with_trend_needs_sr']:
                key_level = self.is_at_key_level(df, idx, self.key_levels)
                if key_level is None:
                    self.diag['sr_reject_with_trend'] += 1
                    return
            else:
                key_level = self.is_at_key_level(df, idx, self.key_levels)
        else:
            # Sideways
            key_level = self.is_at_key_level(df, idx, self.key_levels)
            if key_level is None:
                self.diag['sr_reject_sideways'] += 1
                return

        self.diag['sr_pass'] += 1

        # Entry
        entry, stop, target = self.calculate_entry_stop_target(df, idx, pattern)

        self.diag['entry_executed'] += 1

        # Actually enter
        self.in_position = True
        self.position_type = 'LONG' if is_long else 'SHORT'
        self.entry_bar = idx
        self.entry_price = entry
        self.stop_price = stop
        self.original_stop = stop
        self.target_price = target

        self.current_trade = {
            'entry_time': df.index[idx],
            'entry_idx': idx,
            'entry_price': entry,
            'stop_price': stop,
            'target_price': target,
            'position_type': self.position_type,
            'pattern': pattern.value,
            'trend': trend.value,
            'key_level': key_level.level_type if key_level else 'NONE',
            'key_level_price': key_level.price if key_level else 0,
            'signal_quality': signal_bar.quality_score,
            'atr': df['atr'].iloc[idx],
        }

        if pattern == PatternType.SECOND_ENTRY_LONG:
            self.h2_state.__init__()
        elif pattern == PatternType.SECOND_ENTRY_SHORT:
            self.l2_state.__init__()


def main():
    workspace = Path("/home/shado/.openclaw/workspace")
    df = pd.read_csv(workspace / "data" / "MNQ_5min.csv")
    df['time'] = pd.to_datetime(df['time'])

    # Test on recent 6 months (like V1 did)
    recent = df.tail(30000).copy()
    print(f"Testing on recent 30K bars: {recent['time'].iloc[0]} to {recent['time'].iloc[-1]}")

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

    strategy = DiagnosticV2(params)
    trades = strategy.run_backtest(recent, verbose=False)

    print(f"\n=== PIPELINE DIAGNOSTIC (Recent 30K bars) ===")
    print(f"Trades generated: {len(trades)}")
    print(f"\nPipeline breakdown:")
    for key, count in sorted(strategy.diag.items(), key=lambda x: -x[1]):
        print(f"  {key:30s}: {count:,}")

    # Also test on full dataset
    print(f"\n\n=== NOW TESTING FULL DATASET ===")
    strategy2 = DiagnosticV2(params)
    trades2 = strategy2.run_backtest(df, verbose=False)

    print(f"Trades generated: {len(trades2)}")
    print(f"\nPipeline breakdown:")
    for key, count in sorted(strategy2.diag.items(), key=lambda x: -x[1]):
        print(f"  {key:30s}: {count:,}")


if __name__ == "__main__":
    main()
