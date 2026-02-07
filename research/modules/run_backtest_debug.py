"""
Debug backtest to see why only 15 trades execute
"""

import pandas as pd
from pathlib import Path
from frr_strategy import FRRStrategy


def main():
    print(f"\n{'='*60}")
    print(f"  DEBUG BACKTEST")
    print(f"{'='*60}")
    
    # Load small dataset for debugging
    data_path = Path.home() / '.openclaw' / 'workspace' / 'data' / 'MNQ_5min.csv'
    df = pd.read_csv(data_path, parse_dates=['time'], index_col='time')
    
    # Use just first 100K bars for speed
    df = df.iloc[:100000]
    print(f"\n  Loaded {len(df):,} bars (first 100K for debug)")
    
    # Generate signals
    strategy = FRRStrategy()
    signals = strategy.generate_signals(df)
    
    # Count total entry signals
    long_signals = signals['long_entry'].sum()
    short_signals = signals['short_entry'].sum()
    total_signals = long_signals + short_signals
    
    print(f"\n📊 ENTRY SIGNALS GENERATED:")
    print(f"  Long:  {long_signals}")
    print(f"  Short: {short_signals}")
    print(f"  Total: {total_signals}")
    
    # Now run backtest and track why signals don't become trades
    strategy.reset_state()
    
    trades_executed = 0
    signals_while_in_position = 0
    signals_daily_limit = 0
    signals_consecutive_losses = 0
    
    current_date = None
    daily_pnl = 0
    consecutive_losses = 0
    in_position = False
    
    for i in range(1, len(signals)):
        current_bar = signals.iloc[i]
        prev_bar = signals.iloc[i - 1]
        
        # Reset daily P&L
        bar_date = current_bar.name.date()
        if current_date != bar_date:
            current_date = bar_date
            daily_pnl = 0
        
        # Check for entry signal
        has_long_signal = prev_bar['long_entry']
        has_short_signal = prev_bar['short_entry']
        has_signal = has_long_signal or has_short_signal
        
        if has_signal:
            # Why didn't it trade?
            if in_position:
                signals_while_in_position += 1
            elif daily_pnl <= strategy.params['daily_loss_limit']:
                signals_daily_limit += 1
            elif consecutive_losses >= strategy.params['max_consecutive_losses']:
                signals_consecutive_losses += 1
            else:
                # This signal should become a trade
                trades_executed += 1
                in_position = True
                
                # Simulate exit after avg 4 bars (from backtest results)
                # This is simplified - real backtest has complex exit logic
        
        # Simplified exit (assuming avg 4 bars held)
        if in_position and i % 4 == 0:
            in_position = False
            # Simulate random win/loss for circuit breaker tracking
            pnl = 10 if i % 2 == 0 else -15
            daily_pnl += pnl
            if pnl < 0:
                consecutive_losses += 1
            else:
                consecutive_losses = 0
    
    print(f"\n🚫 SIGNALS BLOCKED:")
    print(f"  While in position:      {signals_while_in_position} ({signals_while_in_position/total_signals*100:.1f}%)")
    print(f"  Daily loss limit hit:   {signals_daily_limit} ({signals_daily_limit/total_signals*100:.1f}%)")
    print(f"  Consecutive losses:     {signals_consecutive_losses} ({signals_consecutive_losses/total_signals*100:.1f}%)")
    print(f"  Trades executed:        {trades_executed} ({trades_executed/total_signals*100:.1f}%)")
    
    print(f"\n{'='*60}\n")


if __name__ == '__main__':
    main()
