"""
Deep dive into wave direction filter issue
"""

import pandas as pd
from pathlib import Path
from frr_strategy import FRRStrategy


def main():
    print(f"\n{'='*60}")
    print(f"  WAVE DIRECTION DEEP DIVE")
    print(f"{'='*60}")
    
    # Load data
    data_path = Path.home() / '.openclaw' / 'workspace' / 'data' / 'MNQ_5min.csv'
    df = pd.read_csv(data_path, parse_dates=['time'], index_col='time')
    test_df = df.loc['2023-01-01':'2024-12-31']
    print(f"\n  Loaded {len(test_df):,} bars")
    
    # Generate signals
    strategy = FRRStrategy()
    signals = strategy.generate_signals(test_df)
    
    # Find the 99 signals that pass Z + R1
    z_r1_mask = (
        signals['is_R1'] &
        ((signals['zscore'] <= -strategy.params['z_threshold']) | 
         (signals['zscore'] >= strategy.params['z_threshold']))
    )
    
    z_r1_signals = signals[z_r1_mask].copy()
    print(f"\n  Found {len(z_r1_signals)} signals passing Z + R1 filter")
    
    # Check wave direction on these signals
    bullish_count = z_r1_signals['bullish_wave'].sum()
    bearish_count = z_r1_signals['bearish_wave'].sum()
    neither_count = len(z_r1_signals) - bullish_count - bearish_count
    
    print(f"\n📊 WAVE DIRECTION ON Z+R1 SIGNALS:")
    print(f"  Bullish wave: {bullish_count}")
    print(f"  Bearish wave: {bearish_count}")
    print(f"  Neither: {neither_count}")
    
    # Check long signals specifically
    long_z_r1 = signals[signals['is_R1'] & (signals['zscore'] <= -strategy.params['z_threshold'])].copy()
    print(f"\n📉 LONG SIGNALS (oversold in R1): {len(long_z_r1)}")
    print(f"  With bearish wave: {long_z_r1['bearish_wave'].sum()}")
    print(f"  With bullish wave: {long_z_r1['bullish_wave'].sum()}")
    print(f"  With neither: {len(long_z_r1) - long_z_r1['bearish_wave'].sum() - long_z_r1['bullish_wave'].sum()}")
    
    # Check short signals specifically
    short_z_r1 = signals[signals['is_R1'] & (signals['zscore'] >= strategy.params['z_threshold'])].copy()
    print(f"\n📈 SHORT SIGNALS (overbought in R1): {len(short_z_r1)}")
    print(f"  With bullish wave: {short_z_r1['bullish_wave'].sum()}")
    print(f"  With bearish wave: {short_z_r1['bearish_wave'].sum()}")
    print(f"  With neither: {len(short_z_r1) - short_z_r1['bullish_wave'].sum() - short_z_r1['bearish_wave'].sum()}")
    
    # Check if wave calculation is working at all
    print(f"\n🌊 OVERALL WAVE STATISTICS:")
    print(f"  Total bars: {len(signals):,}")
    print(f"  Bullish wave: {signals['bullish_wave'].sum():,} ({signals['bullish_wave'].sum()/len(signals)*100:.1f}%)")
    print(f"  Bearish wave: {signals['bearish_wave'].sum():,} ({signals['bearish_wave'].sum()/len(signals)*100:.1f}%)")
    print(f"  Neither: {(~signals['bullish_wave'] & ~signals['bearish_wave']).sum():,}")
    
    # Sample some Z+R1 signals to inspect
    if len(long_z_r1) > 0:
        print(f"\n🔍 SAMPLE LONG Z+R1 SIGNAL (first occurrence):")
        sample = long_z_r1.iloc[0]
        print(f"  Time: {sample.name}")
        print(f"  Z-score: {sample['zscore']:.2f}")
        print(f"  Bullish wave: {sample['bullish_wave']}")
        print(f"  Bearish wave: {sample['bearish_wave']}")
        print(f"  Bars since swing low: {sample['bars_since_swing_low']:.0f}")
    
    if len(short_z_r1) > 0:
        print(f"\n🔍 SAMPLE SHORT Z+R1 SIGNAL (first occurrence):")
        sample = short_z_r1.iloc[0]
        print(f"  Time: {sample.name}")
        print(f"  Z-score: {sample['zscore']:.2f}")
        print(f"  Bullish wave: {sample['bullish_wave']}")
        print(f"  Bearish wave: {sample['bearish_wave']}")
        print(f"  Bars since swing high: {sample['bars_since_swing_high']:.0f}")
    
    print(f"\n{'='*60}\n")


if __name__ == '__main__':
    main()
