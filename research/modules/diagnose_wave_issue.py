"""
Deep diagnostic: Why does wave filter eliminate everything?
"""

import pandas as pd
from pathlib import Path
from frr_strategy import FRRStrategy


def main():
    print(f"\n{'='*60}")
    print(f"  WAVE FILTER BOTTLENECK DIAGNOSIS")
    print(f"{'='*60}")
    
    # Load data
    data_path = Path.home() / '.openclaw' / 'workspace' / 'data' / 'MNQ_5min.csv'
    df = pd.read_csv(data_path, parse_dates=['time'], index_col='time')
    print(f"\n  Loaded {len(df):,} bars")
    
    # Generate signals with AGGRESSIVE parameters
    strategy = FRRStrategy()
    print(f"\n  Parameters:")
    print(f"    Z-threshold: {strategy.params['z_threshold']}")
    print(f"    Amplitude: {strategy.params['amp_threshold']}")
    print(f"    Chop: {strategy.params['chop_threshold']}")
    print(f"    Swing proximity: {strategy.params['swing_proximity']}")
    
    signals = strategy.generate_signals(df)
    
    # STEP 1: R1 regime coverage
    r1_bars = signals['is_R1'].sum()
    r1_pct = (r1_bars / len(signals)) * 100
    print(f"\n📊 STEP 1: R1 REGIME")
    print(f"  R1 bars: {r1_bars:,} ({r1_pct:.1f}% of all bars)")
    
    # STEP 2: Z-score extremes
    z_long = (signals['zscore'] <= -strategy.params['z_threshold']).sum()
    z_short = (signals['zscore'] >= strategy.params['z_threshold']).sum()
    z_total = z_long + z_short
    print(f"\n📊 STEP 2: Z-SCORE EXTREMES")
    print(f"  Oversold (Z ≤ -{strategy.params['z_threshold']}): {z_long}")
    print(f"  Overbought (Z ≥ {strategy.params['z_threshold']}): {z_short}")
    print(f"  Total Z-extremes: {z_total}")
    
    # STEP 3: Z-score + R1 overlap
    z_r1_long = ((signals['zscore'] <= -strategy.params['z_threshold']) & signals['is_R1']).sum()
    z_r1_short = ((signals['zscore'] >= strategy.params['z_threshold']) & signals['is_R1']).sum()
    z_r1_total = z_r1_long + z_r1_short
    print(f"\n📊 STEP 3: Z-SCORE + R1 OVERLAP")
    print(f"  Long signals (Z + R1): {z_r1_long}")
    print(f"  Short signals (Z + R1): {z_r1_short}")
    print(f"  Total: {z_r1_total}")
    print(f"  Overlap rate: {(z_r1_total/z_total*100):.1f}% of Z-extremes occur in R1")
    
    # STEP 4: Wave direction on Z+R1 signals
    z_r1_mask_long = (signals['zscore'] <= -strategy.params['z_threshold']) & signals['is_R1']
    z_r1_mask_short = (signals['zscore'] >= strategy.params['z_threshold']) & signals['is_R1']
    
    z_r1_long_signals = signals[z_r1_mask_long]
    z_r1_short_signals = signals[z_r1_mask_short]
    
    print(f"\n📊 STEP 4: WAVE DIRECTION ON Z+R1 SIGNALS")
    print(f"\n  LONG SIGNALS (oversold in R1): {len(z_r1_long_signals)}")
    if len(z_r1_long_signals) > 0:
        bearish_long = z_r1_long_signals['bearish_wave'].sum()
        bullish_long = z_r1_long_signals['bullish_wave'].sum()
        neither_long = len(z_r1_long_signals) - bearish_long - bullish_long
        print(f"    With BEARISH wave (needed): {bearish_long} ({bearish_long/len(z_r1_long_signals)*100:.1f}%)")
        print(f"    With BULLISH wave: {bullish_long} ({bullish_long/len(z_r1_long_signals)*100:.1f}%)")
        print(f"    With NEITHER: {neither_long} ({neither_long/len(z_r1_long_signals)*100:.1f}%)")
    
    print(f"\n  SHORT SIGNALS (overbought in R1): {len(z_r1_short_signals)}")
    if len(z_r1_short_signals) > 0:
        bullish_short = z_r1_short_signals['bullish_wave'].sum()
        bearish_short = z_r1_short_signals['bearish_wave'].sum()
        neither_short = len(z_r1_short_signals) - bullish_short - bearish_short
        print(f"    With BULLISH wave (needed): {bullish_short} ({bullish_short/len(z_r1_short_signals)*100:.1f}%)")
        print(f"    With BEARISH wave: {bearish_short} ({bearish_short/len(z_r1_short_signals)*100:.1f}%)")
        print(f"    With NEITHER: {neither_short} ({neither_short/len(z_r1_short_signals)*100:.1f}%)")
    
    # STEP 5: Swing proximity on Z+R1+Wave signals
    z_r1_wave_long = ((signals['zscore'] <= -strategy.params['z_threshold']) & 
                      signals['is_R1'] & 
                      signals['bearish_wave']).sum()
    z_r1_wave_short = ((signals['zscore'] >= strategy.params['z_threshold']) & 
                       signals['is_R1'] & 
                       signals['bullish_wave']).sum()
    
    print(f"\n📊 STEP 5: Z + R1 + WAVE COMBINED")
    print(f"  Long (Z + R1 + bearish wave): {z_r1_wave_long}")
    print(f"  Short (Z + R1 + bullish wave): {z_r1_wave_short}")
    print(f"  Total: {z_r1_wave_long + z_r1_wave_short}")
    
    # STEP 6: Final signals after swing proximity
    final_long = signals['long_entry'].sum()
    final_short = signals['short_entry'].sum()
    print(f"\n📊 STEP 6: FINAL SIGNALS (+ swing proximity)")
    print(f"  Long entries: {final_long}")
    print(f"  Short entries: {final_short}")
    print(f"  Total: {final_long + final_short}")
    
    # ANALYSIS: Where is the bottleneck?
    print(f"\n{'='*60}")
    print(f"  BOTTLENECK ANALYSIS")
    print(f"{'='*60}")
    
    funnel = [
        ("Z-score extremes", z_total),
        ("+ R1 regime", z_r1_total),
        ("+ Wave direction", z_r1_wave_long + z_r1_wave_short),
        ("+ Swing proximity", final_long + final_short),
    ]
    
    print(f"\n  SIGNAL FUNNEL:")
    for i, (stage, count) in enumerate(funnel):
        if i == 0:
            pct = 100.0
            loss = 0
        else:
            prev_count = funnel[i-1][1]
            loss = prev_count - count
            pct = (count / prev_count * 100) if prev_count > 0 else 0
        
        print(f"    {stage:25} {count:5} ({pct:5.1f}% retained, {loss:4} lost)")
    
    # Identify biggest drop
    max_loss = 0
    max_loss_stage = ""
    for i in range(1, len(funnel)):
        loss = funnel[i-1][1] - funnel[i][1]
        if loss > max_loss:
            max_loss = loss
            max_loss_stage = funnel[i][0]
    
    print(f"\n  🔴 BIGGEST BOTTLENECK: {max_loss_stage}")
    print(f"     Lost {max_loss} signals ({max_loss/(funnel[0][1])*100:.1f}% of total)")
    
    # RECOMMENDATION
    print(f"\n{'='*60}")
    print(f"  RECOMMENDATIONS")
    print(f"{'='*60}")
    
    if z_r1_total < z_total * 0.5:
        print(f"\n  ⚠️  Z-extremes rarely occur in R1 regime ({z_r1_total/z_total*100:.1f}% overlap)")
        print(f"     → R1 regime may be TOO SPECIFIC")
        print(f"     → Consider removing R1 filter entirely")
        print(f"     → Or use different regime definition")
    
    if (z_r1_wave_long + z_r1_wave_short) < z_r1_total * 0.3:
        print(f"\n  🔴 WAVE FILTER IS THE PROBLEM ({(z_r1_wave_long + z_r1_wave_short)/z_r1_total*100:.1f}% pass)")
        print(f"     → Wave direction rarely aligns with Z-extremes")
        print(f"     → Options:")
        print(f"        A. Remove wave filter entirely")
        print(f"        B. Invert logic again (maybe we had it right originally)")
        print(f"        C. Use simpler trend filter (EMA-based)")
        print(f"        D. Use wave for exits, not entries")
    
    if (final_long + final_short) < (z_r1_wave_long + z_r1_wave_short) * 0.7:
        print(f"\n  ⚠️  Swing proximity filter too strict")
        print(f"     → Already at {strategy.params['swing_proximity']} bars")
        print(f"     → Consider removing this filter")
    
    print(f"\n{'='*60}\n")


if __name__ == '__main__':
    main()
