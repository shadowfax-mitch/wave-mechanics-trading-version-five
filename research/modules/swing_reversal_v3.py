"""
Swing Reversal Strategy V3 - EMA Trend Filter Added

Filter Layer 1: RTH Only (8:30 AM - 3:00 PM CT)
Filter Layer 2: EMA Trend Filter
  - Only LONG when price > EMA(21)
  - Only SHORT when price < EMA(21)
  - Trend-following reduces counter-trend whipsaw

Based on V2 (RTH), adds trend confirmation.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from swing_reversal_v2 import SwingReversalV2

class SwingReversalV3(SwingReversalV2):
    """
    Swing reversal strategy with RTH + EMA trend filters
    Inherits from V2, adds EMA trend confirmation
    """
    
    def __init__(self, params: Optional[Dict] = None):
        """Initialize with EMA trend filter"""
        super().__init__(params)
        
        # Add EMA period parameter
        if 'ema_period' not in self.params:
            self.params['ema_period'] = 21  # Default to EMA(21)
    
    def calculate_ema(self, df: pd.DataFrame, period: int) -> pd.Series:
        """
        Calculate Exponential Moving Average
        
        Args:
            df: DataFrame with close prices
            period: EMA period
        
        Returns:
            EMA series
        """
        return df['close'].ewm(span=period, adjust=False).mean()
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate signals with EMA added
        
        Returns:
            DataFrame with swing points, ATR, and EMA
        """
        # Get base signals from parent class (swings + ATR)
        signals = super().generate_signals(df)
        
        # Add EMA
        signals['ema'] = self.calculate_ema(df, self.params['ema_period'])
        
        return signals
    
    def backtest(self, df: pd.DataFrame, 
                 slippage: float = 2.0, 
                 commission: float = 1.0) -> Dict:
        """
        Run backtest with RTH + EMA trend filters
        
        Modifications from V2:
        - Adds EMA trend check before entry
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
            
            # Exit logic (runs always)
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
            
            # Circuit breaker check
            if self.daily_pnl <= self.params['max_daily_loss']:
                continue
            if self.consecutive_losses >= self.params['max_consecutive_losses']:
                continue
            
            # Skip if already in position
            if self.in_position:
                continue
            
            # RTH filter (from V2)
            if not self.is_rth(current_bar.name):
                continue
            
            # Skip if ATR or EMA not ready
            if pd.isna(current_bar['atr']) or current_bar['atr'] == 0:
                continue
            if pd.isna(current_bar['ema']):
                continue
            
            # Entry logic with swing + EMA trend filter
            entry_signal = None
            direction = None
            
            # SHORT at swing high - BUT ONLY if price < EMA (downtrend)
            if current_bar['swing_high'] and current_bar['close'] < current_bar['ema']:
                entry_signal = 'SWING_HIGH'
                direction = 'SHORT'
                entry_price = current_bar['close'] - slippage
                stop_price = current_bar['high'] + (self.params['stop_atr_mult'] * current_bar['atr'])
                target_price = entry_price - (self.params['target_atr_mult'] * current_bar['atr'])
            
            # LONG at swing low - BUT ONLY if price > EMA (uptrend)
            elif current_bar['swing_low'] and current_bar['close'] > current_bar['ema']:
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
    print("Swing Reversal V3 - RTH + EMA Trend Filter")
    print("Only trades with trend: Long if price>EMA(21), Short if price<EMA(21)")
    print("Run with run_backtest_swing_v3.py for full validation")
