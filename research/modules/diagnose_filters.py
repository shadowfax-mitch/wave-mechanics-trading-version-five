"""
Diagnostic script to understand why FRR strategy generates zero trades
"""

import pandas as pd
from pathlib import Path
from frr_strategy import FRRStrategy


def main():
    print(f"\n{'='*60}")
    print(f"  FRR FILTER DIAGNOSIS")
    print(f"{'='*60}")
    
    # Load data
    print(f"\n📂 Loading 2023-2024 data...")
    data_path = Path.home() / '.openclaw' / 'workspace' / 'data' / 'MNQ_5min.csv'
    df = pd.read_csv(data_path, parse_dates=['time'], index_col='time')
    test_df = df.loc['2023-01-01':'2024-12-31']
    print(f"  ✓ {len(test_df):,} bars loaded")
    
    # Generate signals
    print(f"\n🔬 Generating signals...")
    strategy = FRRStrategy()
    signals = strategy.generate_signals(test_df)
    
    # Analyze each filter
    print(f"\n📊 FILTER ANALYSIS")
    print(f"{'='*60}")
    
    # Z-score signals
    long_zscore = (signals['zscore'] <= -strategy.params['z_threshold']).sum()
    short_zscore = (signals['zscore'] >= strategy.params['z_threshold']).sum()
    print(f"\n1️⃣  Z-SCORE FILTER (threshold ±{strategy.params['z_threshold']})")
    print(f"  Oversold signals (Z ≤ -{strategy.params['z_threshold']}): {long_zscore}")
    print(f"  Overbought signals (Z ≥ {strategy.params['z_threshold']}): {short_zscore}")
    print(f"  Total Z-score extremes: {long_zscore + short_zscore}")
    
    # R1 regime
    r1_bars = signals['is_R1'].sum()
    r1_pct = (r1_bars / len(signals)) * 100
    print(f"\n2️⃣  R1 REGIME FILTER")
    print(f"  R1 regime bars: {r1_bars:,} ({r1_pct:.1f}% of time)")
    
    # Z-score + R1
    long_z_r1 = ((signals['zscore'] <= -strategy.params['z_threshold']) & signals['is_R1']).sum()
    short_z_r1 = ((signals['zscore'] >= strategy.params['z_threshold']) & signals['is_R1']).sum()
    print(f"\n3️⃣  Z-SCORE + R1 COMBINED")
    print(f"  Long signals (Z + R1): {long_z_r1}")
    print(f"  Short signals (Z + R1): {short_z_r1}")
    print(f"  Total: {long_z_r1 + short_z_r1}")
    
    # Wave direction
    bullish_wave_bars = signals['bullish_wave'].sum()
    bearish_wave_bars = signals['bearish_wave'].sum()
    print(f"\n4️⃣  WAVE DIRECTION FILTER")
    print(f"  Bullish wave bars: {bullish_wave_bars:,}")
    print(f"  Bearish wave bars: {bearish_wave_bars:,}")
    
    # Z-score + R1 + Wave (inverted: bearish wave for longs, bullish wave for shorts)
    long_z_r1_wave = ((signals['zscore'] <= -strategy.params['z_threshold']) &
                      signals['is_R1'] &
                      signals['bearish_wave']).sum()
    short_z_r1_wave = ((signals['zscore'] >= strategy.params['z_threshold']) &
                       signals['is_R1'] &
                       signals['bullish_wave']).sum()
    print(f"\n5️⃣  Z-SCORE + R1 + WAVE COMBINED")
    print(f"  Long signals (Z + R1 + Wave): {long_z_r1_wave}")
    print(f"  Short signals (Z + R1 + Wave): {short_z_r1_wave}")
    print(f"  Total: {long_z_r1_wave + short_z_r1_wave}")
    
    # Swing proximity
    proximity = strategy.params['swing_proximity']
    near_swing_low = (signals['bars_since_swing_low'] <= proximity).sum()
    near_swing_high = (signals['bars_since_swing_high'] <= proximity).sum()
    print(f"\n6️⃣  SWING PROXIMITY FILTER (within {proximity} bars)")
    print(f"  Bars near swing low: {near_swing_low:,}")
    print(f"  Bars near swing high: {near_swing_high:,}")
    
    # Final entry signals
    long_entries = signals['long_entry'].sum()
    short_entries = signals['short_entry'].sum()
    print(f"\n7️⃣  FINAL ENTRY SIGNALS (all filters)")
    print(f"  Long entry signals: {long_entries}")
    print(f"  Short entry signals: {short_entries}")
    print(f"  Total entry signals: {long_entries + short_entries}")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"  DIAGNOSIS SUMMARY")
    print(f"{'='*60}")
    
    if long_entries + short_entries == 0:
        print(f"\n❌ ZERO TRADES - Filter Analysis:")
        
        if long_zscore + short_zscore == 0:
            print(f"  🔴 CRITICAL: No Z-score extremes found")
            print(f"     → Z-threshold {strategy.params['z_threshold']} is too high")
            print(f"     → Recommendation: Lower to 4.0 or 4.5")
        
        elif r1_bars == 0:
            print(f"  🔴 CRITICAL: R1 regime never detected")
            print(f"     → Regime thresholds may be wrong")
            print(f"     → Check amplitude/chop/energy calculations")
        
        elif long_z_r1 + short_z_r1 == 0:
            print(f"  🔴 PROBLEM: Z-extremes and R1 never overlap")
            print(f"     → Z-extremes may occur outside R1 regime")
            print(f"     → Consider removing R1 filter or adjusting thresholds")
        
        elif long_z_r1_wave + short_z_r1_wave == 0:
            print(f"  🔴 PROBLEM: Wave direction filter eliminates all signals")
            print(f"     → Wave calculation may be incorrect")
            print(f"     → Or Z-extremes don't align with wave direction")
        
        else:
            print(f"  🔴 PROBLEM: Swing proximity filter eliminates all signals")
            print(f"     → Signals occur far from swing points")
            print(f"     → Consider increasing proximity threshold (2 → 5 bars)")
    
    else:
        print(f"\n✅ {long_entries + short_entries} entry signals found")
        print(f"  → Should generate trades (check circuit breakers)")
    
    print(f"\n{'='*60}\n")


if __name__ == '__main__':
    main()
