"""
Swing Reversal Strategy V1 - Simple baseline using fractal swing detection

Strategy:
- Detect swing highs and swing lows (strength=2 fractals)
- Enter OPPOSITE direction when swing confirms (reversal strategy)
  - Swing high confirmed → Enter SHORT (fade the high)
  - Swing low confirmed → Enter LONG (fade the low)
- Exit: Fixed profit target or stop loss based on swing distance

This will trade A LOT - filtering comes later.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional

class SwingReversalV1:
    """
    Simple swing reversal strategy - baseline for filtering experiments
    """
    
    def __init__(self, params: Optional[Dict] = None):
        """
        Initialize strategy with parameters
        
        Args:
            params: Dictionary of strategy parameters
        """
        # Default parameters
        self.params = {
            'swing_strength': 2,        # Fractal lookback (2 = standard)
            'stop_atr_mult': 1.5,       # Stop loss distance (ATR multiplier)
            'target_atr_mult': 2.0,     # Profit target (ATR multiplier)
            'atr_period': 14,           # ATR calculation period
            'max_hold_bars': 30,        # Maximum bars to hold position
            'max_daily_loss': -200,     # Daily loss circuit breaker
            'max_consecutive_losses': 3 # Consecutive loss circuit breaker
        }
        
        if params:
            self.params.update(params)
        
        self.reset_state()
    
    def reset_state(self):
        """Reset strategy state for new backtest"""
        self.in_position = False
        self.position_type = None
        self.entry_bar = None
        self.entry_price = None
        self.stop_price = None
        self.target_price = None
        self.trades = []
        self.daily_pnl = 0
        self.consecutive_losses = 0
    
    def detect_swing_highs(self, df: pd.DataFrame, strength: int = 2) -> pd.Series:
        """
        Detect swing highs (peaks) - CORRECTED for look-ahead bias
        
        A swing high at bar i requires:
        - high[i] > high[i-1], high[i-2], ..., high[i-strength]
        - high[i] > high[i+1], high[i+2], ..., high[i+strength]
        
        BUT we can only KNOW this at bar i+strength (after confirmation)
        
        Args:
            df: DataFrame with OHLC data
            strength: Number of bars on each side for comparison
        
        Returns:
            Boolean series (True = swing high JUST CONFIRMED at this bar)
        """
        highs = df['high']
        is_swing = pd.Series(True, index=df.index)
        
        # Check bars BEFORE (these we can see in real-time)
        for i in range(1, strength + 1):
            is_swing &= highs > highs.shift(i)
        
        # Check bars AFTER (look-ahead bias - need to shift result forward)
        for i in range(1, strength + 1):
            is_swing &= highs > highs.shift(-i)
        
        # CRITICAL FIX: Shift result forward by 'strength' bars
        # This simulates the confirmation delay in real trading
        is_swing = is_swing.shift(strength).fillna(False)
        
        return is_swing
    
    def detect_swing_lows(self, df: pd.DataFrame, strength: int = 2) -> pd.Series:
        """
        Detect swing lows (troughs) - CORRECTED for look-ahead bias
        
        Returns:
            Boolean series (True = swing low JUST CONFIRMED at this bar)
        """
        lows = df['low']
        is_swing = pd.Series(True, index=df.index)
        
        # Check bars BEFORE
        for i in range(1, strength + 1):
            is_swing &= lows < lows.shift(i)
        
        # Check bars AFTER (look-ahead)
        for i in range(1, strength + 1):
            is_swing &= lows < lows.shift(-i)
        
        # CRITICAL FIX: Shift forward by 'strength' bars
        is_swing = is_swing.shift(strength).fillna(False)
        
        return is_swing
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate entry signals based on swing reversals
        
        Returns:
            DataFrame with swing points and ATR
        """
        signals = df.copy()
        
        # Detect swing points (with confirmation delay)
        signals['swing_high'] = self.detect_swing_highs(df, self.params['swing_strength'])
        signals['swing_low'] = self.detect_swing_lows(df, self.params['swing_strength'])
        
        # Calculate ATR for stops/targets
        signals['atr'] = self.calculate_atr(df, self.params['atr_period'])
        
        # Track last swing levels (for reference)
        signals['last_swing_high'] = df['high'].where(signals['swing_high']).ffill()
        signals['last_swing_low'] = df['low'].where(signals['swing_low']).ffill()
        
        return signals
    
    def backtest(self, df: pd.DataFrame, 
                 slippage: float = 2.0, 
                 commission: float = 1.0) -> Dict:
        """
        Run backtest on historical data
        
        Args:
            df: DataFrame with OHLC data, indexed by timestamp
            slippage: Points of slippage per trade
            commission: Dollar commission per round trip
        
        Returns:
            Dictionary with backtest results
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
            
            # Exit logic (runs even during circuit breaker)
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
            
            # Skip if ATR not ready
            if pd.isna(current_bar['atr']) or current_bar['atr'] == 0:
                continue
            
            # Entry logic: Fade swing highs and lows
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
    
    def _enter_trade(self, direction: str, entry_bar: int, entry_time, 
                     entry_price: float, stop_price: float, target_price: float,
                     entry_reason: str):
        """Enter a new trade"""
        self.in_position = True
        self.position_type = direction
        self.entry_bar = entry_bar
        self.entry_price = entry_price
        self.stop_price = stop_price
        self.target_price = target_price
    
    def _exit_trade(self, exit_bar: int, exit_time, exit_price: float, 
                    exit_reason: str, slippage: float, commission: float):
        """Exit current trade"""
        # Calculate P&L
        if self.position_type == 'LONG':
            pnl = (exit_price - self.entry_price) - commission
        else:  # SHORT
            pnl = (self.entry_price - exit_price) - commission
        
        # Record trade
        self.trades.append({
            'direction': self.position_type,
            'entry_bar': self.entry_bar,
            'entry_time': self.entry_time if hasattr(self, 'entry_time') else None,
            'entry_price': self.entry_price,
            'exit_bar': exit_bar,
            'exit_time': exit_time,
            'exit_price': exit_price,
            'exit_reason': exit_reason,
            'pnl': pnl,
            'bars_held': exit_bar - self.entry_bar
        })
        
        # Update daily state
        self.daily_pnl += pnl
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        # Reset position
        self.in_position = False
        self.position_type = None
    
    def _calculate_statistics(self) -> Dict:
        """Calculate backtest statistics"""
        if len(self.trades) == 0:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'total_pnl': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'avg_win_loss_ratio': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0,
                'trades': []
            }
        
        trades_df = pd.DataFrame(self.trades)
        
        # Basic metrics
        total_trades = len(trades_df)
        winners = trades_df[trades_df['pnl'] > 0]
        losers = trades_df[trades_df['pnl'] < 0]
        
        win_rate = (len(winners) / total_trades * 100) if total_trades > 0 else 0
        
        gross_profit = winners['pnl'].sum() if len(winners) > 0 else 0
        gross_loss = abs(losers['pnl'].sum()) if len(losers) > 0 else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        total_pnl = trades_df['pnl'].sum()
        avg_win = winners['pnl'].mean() if len(winners) > 0 else 0
        avg_loss = losers['pnl'].mean() if len(losers) > 0 else 0
        avg_win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        # Drawdown
        cumulative_pnl = trades_df['pnl'].cumsum()
        running_max = cumulative_pnl.expanding().max()
        drawdown = running_max - cumulative_pnl
        max_drawdown = drawdown.max()
        
        # Sharpe (simplified per-trade)
        sharpe_ratio = trades_df['pnl'].mean() / trades_df['pnl'].std() if trades_df['pnl'].std() > 0 else 0
        
        # Long/short breakdown
        long_trades = trades_df[trades_df['direction'] == 'LONG']
        short_trades = trades_df[trades_df['direction'] == 'SHORT']
        
        long_win_rate = (long_trades['pnl'] > 0).sum() / len(long_trades) * 100 if len(long_trades) > 0 else 0
        short_win_rate = (short_trades['pnl'] > 0).sum() / len(short_trades) * 100 if len(short_trades) > 0 else 0
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_win_loss_ratio': avg_win_loss_ratio,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'long_trades': len(long_trades),
            'short_trades': len(short_trades),
            'long_win_rate': long_win_rate,
            'short_win_rate': short_win_rate,
            'avg_bars_held': trades_df['bars_held'].mean(),
            'trades': self.trades
        }

if __name__ == '__main__':
    # Quick test
    print("Swing Reversal V1 - Simple baseline strategy")
    print("Uses swing highs/lows to fade peaks and troughs")
    print("Run with run_backtest_swing_v1.py for full validation")
