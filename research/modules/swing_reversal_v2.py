"""
Swing Reversal Strategy V2 - RTH Filter Added

Filter Layer 1: Regular Trading Hours Only (8:30 AM - 3:00 PM CT)
- Filters out overnight and extended hours swings
- ES/MNQ have best liquidity during RTH
- PAT trades RTH exclusively

Based on V1 baseline, adds simple time filter.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from swing_reversal_v1 import SwingReversalV1

class SwingReversalV2(SwingReversalV1):
    """
    Swing reversal strategy with RTH filter
    Inherits from V1, adds time-of-day filtering
    """
    
    def __init__(self, params: Optional[Dict] = None):
        """Initialize with RTH filter enabled by default"""
        super().__init__(params)
        
        # RTH hours (Central Time)
        self.rth_start_hour = 8
        self.rth_start_minute = 30
        self.rth_end_hour = 15
        self.rth_end_minute = 0
    
    def is_rth(self, timestamp) -> bool:
        """
        Check if timestamp is during Regular Trading Hours (RTH)
        
        Args:
            timestamp: pandas Timestamp
        
        Returns:
            True if during RTH (8:30 AM - 3:00 PM CT)
        """
        # Convert to time for comparison
        current_time = timestamp.time()
        
        # RTH start: 8:30 AM
        rth_start = pd.Timestamp(
            year=timestamp.year,
            month=timestamp.month, 
            day=timestamp.day,
            hour=self.rth_start_hour,
            minute=self.rth_start_minute
        ).time()
        
        # RTH end: 3:00 PM  
        rth_end = pd.Timestamp(
            year=timestamp.year,
            month=timestamp.month,
            day=timestamp.day, 
            hour=self.rth_end_hour,
            minute=self.rth_end_minute
        ).time()
        
        return rth_start <= current_time < rth_end
    
    def backtest(self, df: pd.DataFrame, 
                 slippage: float = 2.0, 
                 commission: float = 1.0) -> Dict:
        """
        Run backtest with RTH filter
        
        Only modification from V1: Skip entries outside RTH
        """
        self.reset_state()
        
        # Generate signals
        signals = self.generate_signals(df)
        
        # Track daily state
        current_date = None
        
        # Iterate through bars
        for i in range(len(signals)):
            current_bar = signals.iloc[i]
            bar_date = current_bar.name.date()
            
            # Reset daily trackers on new day
            if current_date != bar_date:
                current_date = bar_date
                self.daily_pnl = 0
                self.consecutive_losses = 0
            
            # Exit logic (runs even during circuit breaker and outside RTH)
            if self.in_position:
                bars_held = i - self.entry_bar
                exit_signal = None
                exit_price = None
                
                # Check stop loss
                if self.position_type == 'LONG':
                    if current_bar['low'] <= self.stop_price:
                        exit_signal = 'STOP'
                        exit_price = self.stop_price
                elif self.position_type == 'SHORT':
                    if current_bar['high'] >= self.stop_price:
                        exit_signal = 'STOP'
                        exit_price = self.stop_price
                
                # Check profit target
                if not exit_signal:
                    if self.position_type == 'LONG':
                        if current_bar['high'] >= self.target_price:
                            exit_signal = 'TARGET'
                            exit_price = self.target_price
                    elif self.position_type == 'SHORT':
                        if current_bar['low'] <= self.target_price:
                            exit_signal = 'TARGET'
                            exit_price = self.target_price
                
                # Time-based exit
                if not exit_signal and bars_held >= self.params['max_hold_bars']:
                    exit_signal = 'TIME'
                    exit_price = current_bar['close']
                
                # Execute exit
                if exit_signal:
                    self._exit_trade(
                        exit_bar=i,
                        exit_time=current_bar.name,
                        exit_price=exit_price,
                        exit_reason=exit_signal,
                        slippage=slippage,
                        commission=commission
                    )
            
            # Circuit breaker check (only gates new entries)
            if self.daily_pnl <= self.params['max_daily_loss']:
                continue
            if self.consecutive_losses >= self.params['max_consecutive_losses']:
                continue
            
            # Skip if already in position
            if self.in_position:
                continue
            
            # *** RTH FILTER - NEW IN V2 ***
            if not self.is_rth(current_bar.name):
                continue
            
            # Skip if ATR not ready
            if pd.isna(current_bar['atr']) or current_bar['atr'] == 0:
                continue
            
            # Entry logic: Fade swing highs and lows (same as V1)
            entry_signal = None
            direction = None
            
            # SHORT at swing high (fade the peak)
            if current_bar['swing_high']:
                entry_signal = 'SWING_HIGH'
                direction = 'SHORT'
                entry_price = current_bar['close'] - slippage
                stop_price = current_bar['high'] + (self.params['stop_atr_mult'] * current_bar['atr'])
                target_price = entry_price - (self.params['target_atr_mult'] * current_bar['atr'])
            
            # LONG at swing low (fade the trough)
            elif current_bar['swing_low']:
                entry_signal = 'SWING_LOW'
                direction = 'LONG'
                entry_price = current_bar['close'] + slippage
                stop_price = current_bar['low'] - (self.params['stop_atr_mult'] * current_bar['atr'])
                target_price = entry_price + (self.params['target_atr_mult'] * current_bar['atr'])
            
            # Execute entry
            if entry_signal:
                self._enter_trade(
                    direction=direction,
                    entry_bar=i,
                    entry_time=current_bar.name,
                    entry_price=entry_price,
                    stop_price=stop_price,
                    target_price=target_price,
                    entry_reason=entry_signal
                )
        
        # Calculate statistics
        return self._calculate_statistics()

if __name__ == '__main__':
    print("Swing Reversal V2 - RTH Filter")
    print("Only trades during Regular Trading Hours (8:30 AM - 3:00 PM CT)")
    print("Run with run_backtest_swing_v2.py for full validation")
