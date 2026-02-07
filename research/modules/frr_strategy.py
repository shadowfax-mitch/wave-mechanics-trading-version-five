"""
Fractal Regime Reversion (FRR) Strategy
V5 Implementation

Strategy combines:
- V1: Swing points (fractals) + wave direction
- V2: R1 high-vol chop regime (86% WR)
- V4: Z-score extremes (Z≥5.0) + circuit breakers
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional, Dict, List


class FRRStrategy:
    """Fractal Regime Reversion strategy implementation"""
    
    def __init__(self, params: Optional[Dict] = None):
        """
        Initialize strategy with parameters
        
        Args:
            params: Dictionary of strategy parameters
        """
        # Default parameters (AGGRESSIVE OVERTRADE MODE - tune for frequency first)
        self.params = {
            'swing_strength': 2,
            'regime_window': 20,
            'amp_threshold': 0.6,      # AGGRESSIVE: way more R1 bars
            'chop_threshold': 0.3,     # AGGRESSIVE: way more R1 bars
            'energy_threshold': 50,    # percentile
            'ema_period': 50,
            'z_threshold': 3.0,        # AGGRESSIVE: many more Z-extremes
            'atr_period': 14,
            'stop_atr_mult': 1.0,
            'max_hold_bars': 20,
            'swing_proximity': 10,     # AGGRESSIVE: very flexible entry timing
            'daily_loss_limit': -200,
            'max_consecutive_losses': 3,
            'use_wave_filter': True,   # Re-enabled (it creates edge)
        }
        
        if params:
            self.params.update(params)
        
        # State variables
        self.reset_state()
    
    def reset_state(self):
        """Reset strategy state (for new trading session)"""
        self.in_position = False
        self.position_type = None  # 'LONG' or 'SHORT'
        self.entry_bar = None
        self.entry_price = None
        self.daily_pnl = 0
        self.consecutive_losses = 0
        self.trades = []
        self.current_trade = None
    
    def detect_swing_highs(self, df: pd.DataFrame, strength: int = 2) -> pd.Series:
        """
        Detect swing high fractal points (VECTORIZED)
        
        Args:
            df: DataFrame with OHLCV data
            strength: Number of bars on each side for comparison
        
        Returns:
            Boolean series indicating swing highs
        """
        highs = df['high']
        
        # Initialize as True, then eliminate non-swings
        is_swing = pd.Series(True, index=df.index)
        
        # Check all bars on left and right sides
        for i in range(1, strength + 1):
            # Current high must be > all prior bars in range
            is_swing &= highs > highs.shift(i)
            # Current high must be > all future bars in range
            is_swing &= highs > highs.shift(-i)
        
        # First and last 'strength' bars cannot be swings
        is_swing.iloc[:strength] = False
        is_swing.iloc[-strength:] = False
        
        return is_swing
    
    def detect_swing_lows(self, df: pd.DataFrame, strength: int = 2) -> pd.Series:
        """
        Detect swing low fractal points (VECTORIZED)
        
        Args:
            df: DataFrame with OHLCV data
            strength: Number of bars on each side for comparison
        
        Returns:
            Boolean series indicating swing lows
        """
        lows = df['low']
        
        # Initialize as True, then eliminate non-swings
        is_swing = pd.Series(True, index=df.index)
        
        # Check all bars on left and right sides
        for i in range(1, strength + 1):
            # Current low must be < all prior bars in range
            is_swing &= lows < lows.shift(i)
            # Current low must be < all future bars in range
            is_swing &= lows < lows.shift(-i)
        
        # First and last 'strength' bars cannot be swings
        is_swing.iloc[:strength] = False
        is_swing.iloc[-strength:] = False
        
        return is_swing
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    def calculate_regime(self, df: pd.DataFrame, window: int) -> pd.Series:
        """
        Calculate R1 regime (high-vol chop)
        
        Returns boolean series indicating R1 regime
        """
        # Calculate ATR for amplitude normalization
        atr = self.calculate_atr(df, self.params['atr_period'])
        
        # Amplitude: (High - Low) / ATR
        amplitude = (df['high'] - df['low']) / atr
        amplitude_rolling = amplitude.rolling(window=window).mean()
        
        # Chop: 1 - |Trend| where Trend = (Close - Open) / (High - Low)
        range_hl = df['high'] - df['low']
        range_hl = range_hl.replace(0, np.nan)  # Avoid division by zero
        trend = (df['close'] - df['open']) / range_hl
        chop = 1 - abs(trend)
        chop_rolling = chop.rolling(window=window).mean()
        
        # Energy: Volume × |Close - Open|
        energy = df['volume'] * abs(df['close'] - df['open'])
        energy_threshold = energy.rolling(window=window * 5).quantile(
            self.params['energy_threshold'] / 100.0
        )
        
        # R1 criteria
        is_R1 = (
            (amplitude_rolling > self.params['amp_threshold']) &
            (chop_rolling > self.params['chop_threshold']) &
            (energy > energy_threshold)
        )
        
        return is_R1
    
    def calculate_zscore(self, df: pd.DataFrame, period: int) -> pd.Series:
        """
        Calculate Z-score: (Close - EMA) / StdDev
        """
        ema = df['close'].ewm(span=period, adjust=False).mean()
        std = df['close'].rolling(window=period).std()
        
        zscore = (df['close'] - ema) / std
        
        return zscore, ema
    
    def calculate_wave_direction(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """
        Calculate wave direction from swing points (PROPERLY FIXED)
        
        Wave direction is determined by comparing consecutive swing points:
        - Bullish wave: When a new swing low is HIGHER than the previous swing low
        - Bearish wave: When a new swing high is LOWER than the previous swing high
        
        Direction is forward-filled until a new swing point changes it.
        
        Returns:
            bullish_wave: Boolean series (higher swing lows trend)
            bearish_wave: Boolean series (lower swing highs trend)
        """
        swing_highs = self.detect_swing_highs(df, self.params['swing_strength'])
        swing_lows = self.detect_swing_lows(df, self.params['swing_strength'])
        
        # Get just the swing point values (NaN elsewhere)
        swing_high_values = df['high'].where(swing_highs)
        swing_low_values = df['low'].where(swing_lows)
        
        # Identify when swing levels CHANGE (new swing point detected)
        # Compare each swing to the previous swing
        bullish_wave = pd.Series(False, index=df.index)
        bearish_wave = pd.Series(False, index=df.index)
        
        last_swing_low = None
        last_swing_high = None
        current_bullish = False
        current_bearish = False
        
        for i in range(len(df)):
            # Check for new swing low
            if not pd.isna(swing_low_values.iloc[i]):
                new_low = swing_low_values.iloc[i]
                if last_swing_low is not None:
                    # Compare to previous swing low
                    current_bullish = new_low > last_swing_low
                last_swing_low = new_low
            
            # Check for new swing high
            if not pd.isna(swing_high_values.iloc[i]):
                new_high = swing_high_values.iloc[i]
                if last_swing_high is not None:
                    # Compare to previous swing high
                    current_bearish = new_high < last_swing_high
                last_swing_high = new_high
            
            # Set current wave direction (carries forward until next swing)
            bullish_wave.iloc[i] = current_bullish
            bearish_wave.iloc[i] = current_bearish
        
        return bullish_wave, bearish_wave
    
    def bars_since_swing(self, df: pd.DataFrame, swing_series: pd.Series) -> pd.Series:
        """Calculate bars since last swing point (VECTORIZED)"""
        # Create cumulative counter that resets at each swing
        swing_indices = swing_series.astype(int).cumsum()
        
        # Group by swing index and count bars within each group
        bars_since = swing_series.groupby(swing_indices).cumcount()
        
        return bars_since
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate entry/exit signals for strategy
        
        Returns:
            DataFrame with signal columns added
        """
        signals = df.copy()
        
        # Calculate indicators
        signals['atr'] = self.calculate_atr(signals, self.params['atr_period'])
        signals['is_R1'] = self.calculate_regime(signals, self.params['regime_window'])
        signals['zscore'], signals['ema'] = self.calculate_zscore(
            signals, self.params['ema_period']
        )
        
        signals['swing_high'] = self.detect_swing_highs(
            signals, self.params['swing_strength']
        )
        signals['swing_low'] = self.detect_swing_lows(
            signals, self.params['swing_strength']
        )
        
        signals['bullish_wave'], signals['bearish_wave'] = self.calculate_wave_direction(
            signals
        )
        
        signals['bars_since_swing_high'] = self.bars_since_swing(
            signals, signals['swing_high']
        )
        signals['bars_since_swing_low'] = self.bars_since_swing(
            signals, signals['swing_low']
        )
        
        # Get most recent swing levels for stops
        swing_high_values = signals['high'].where(signals['swing_high'])
        swing_low_values = signals['low'].where(signals['swing_low'])
        
        signals['last_swing_high'] = swing_high_values.ffill()
        signals['last_swing_low'] = swing_low_values.ffill()
        
        # Entry signals - Wave filter conditionally applied
        if self.params.get('use_wave_filter', True):
            # INVERTED wave logic for mean reversion
            # LONG when oversold in BEARISH wave (catch bottom in downtrend)
            # SHORT when overbought in BULLISH wave (catch top in uptrend)
            signals['long_entry'] = (
                signals['is_R1'] &
                (signals['zscore'] <= -self.params['z_threshold']) &
                signals['bearish_wave'] &
                (signals['bars_since_swing_low'] <= self.params['swing_proximity'])
            )
            
            signals['short_entry'] = (
                signals['is_R1'] &
                (signals['zscore'] >= self.params['z_threshold']) &
                signals['bullish_wave'] &
                (signals['bars_since_swing_high'] <= self.params['swing_proximity'])
            )
        else:
            # NO wave filter - just Z + R1 + swing proximity
            signals['long_entry'] = (
                signals['is_R1'] &
                (signals['zscore'] <= -self.params['z_threshold']) &
                (signals['bars_since_swing_low'] <= self.params['swing_proximity'])
            )
            
            signals['short_entry'] = (
                signals['is_R1'] &
                (signals['zscore'] >= self.params['z_threshold']) &
                (signals['bars_since_swing_high'] <= self.params['swing_proximity'])
            )
        
        return signals
    
    def backtest(self, df: pd.DataFrame, 
                 slippage: float = 2.0, 
                 commission: float = 1.0) -> Dict:
        """
        Run backtest on historical data
        
        Args:
            df: DataFrame with OHLCV data
            slippage: Dollars per trade (execution slippage)
            commission: Dollars per round-trip
        
        Returns:
            Dictionary with backtest results
        """
        # Generate signals
        signals = self.generate_signals(df)
        
        # Reset state
        self.reset_state()
        
        # Iterate through bars
        current_date = None
        for i in range(len(signals)):
            if i == 0:
                continue
            
            current_bar = signals.iloc[i]
            prev_bar = signals.iloc[i - 1]
            
            # Reset daily P&L and consecutive losses at start of new trading day
            bar_date = current_bar.name.date()
            if current_date != bar_date:
                current_date = bar_date
                self.daily_pnl = 0  # Reset for new day
                self.consecutive_losses = 0  # Reset for new day
            
            # Circuit breaker check
            if self.daily_pnl <= self.params['daily_loss_limit']:
                continue
            if self.consecutive_losses >= self.params['max_consecutive_losses']:
                continue
            
            # Exit logic (if in position)
            if self.in_position:
                bars_held = i - self.entry_bar
                exit_signal = None
                exit_price = None
                
                # Profit target: EMA reversion
                if self.position_type == 'LONG' and current_bar['close'] >= current_bar['ema']:
                    exit_signal = 'TARGET'
                    exit_price = current_bar['ema']
                elif self.position_type == 'SHORT' and current_bar['close'] <= current_bar['ema']:
                    exit_signal = 'TARGET'
                    exit_price = current_bar['ema']
                
                # Stop loss
                elif self.position_type == 'LONG':
                    stop_level = current_bar['last_swing_low'] - (
                        self.params['stop_atr_mult'] * current_bar['atr']
                    )
                    if current_bar['close'] <= stop_level:
                        exit_signal = 'STOP'
                        exit_price = stop_level
                
                elif self.position_type == 'SHORT':
                    stop_level = current_bar['last_swing_high'] + (
                        self.params['stop_atr_mult'] * current_bar['atr']
                    )
                    if current_bar['close'] >= stop_level:
                        exit_signal = 'STOP'
                        exit_price = stop_level
                
                # Time-based exit
                if exit_signal is None and bars_held >= self.params['max_hold_bars']:
                    exit_signal = 'TIME'
                    exit_price = current_bar['close']
                
                # Regime exit
                if exit_signal is None and not current_bar['is_R1']:
                    exit_signal = 'REGIME'
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
            
            # Entry logic (if not in position)
            else:
                # LONG entry
                if bool(prev_bar['long_entry']):  # Explicit bool() cast
                    self._enter_trade(
                        direction='LONG',
                        entry_bar=i,
                        entry_time=current_bar.name,
                        entry_price=current_bar['open'],  # Market order at open
                        slippage=slippage
                    )
                
                # SHORT entry
                elif bool(prev_bar['short_entry']):  # Explicit bool() cast
                    self._enter_trade(
                        direction='SHORT',
                        entry_bar=i,
                        entry_time=current_bar.name,
                        entry_price=current_bar['open'],  # Market order at open
                        slippage=slippage
                    )
        
        # Close any open position at end
        if self.in_position:
            final_bar = signals.iloc[-1]
            self._exit_trade(
                exit_bar=len(signals) - 1,
                exit_time=final_bar.name,
                exit_price=final_bar['close'],
                exit_reason='END',
                slippage=slippage,
                commission=commission
            )
        
        # Calculate statistics
        results = self._calculate_statistics()
        results['signals'] = signals
        
        return results
    
    def _enter_trade(self, direction: str, entry_bar: int, entry_time, 
                     entry_price: float, slippage: float):
        """Execute trade entry"""
        # Apply slippage
        if direction == 'LONG':
            entry_price += slippage
        else:
            entry_price -= slippage
        
        self.in_position = True
        self.position_type = direction
        self.entry_bar = entry_bar
        self.entry_price = entry_price
        
        self.current_trade = {
            'direction': direction,
            'entry_bar': entry_bar,
            'entry_time': entry_time,
            'entry_price': entry_price,
        }
    
    def _exit_trade(self, exit_bar: int, exit_time, exit_price: float, 
                    exit_reason: str, slippage: float, commission: float):
        """Execute trade exit"""
        if not self.in_position:
            return
        
        # Apply slippage
        if self.position_type == 'LONG':
            exit_price -= slippage
        else:
            exit_price += slippage
        
        # Calculate P&L
        if self.position_type == 'LONG':
            pnl = (exit_price - self.entry_price) * 1  # 1 contract
        else:
            pnl = (self.entry_price - exit_price) * 1  # 1 contract
        
        pnl -= commission  # Round-trip commission
        
        # Update state
        self.daily_pnl += pnl
        
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        # Record trade
        self.current_trade.update({
            'exit_bar': exit_bar,
            'exit_time': exit_time,
            'exit_price': exit_price,
            'exit_reason': exit_reason,
            'pnl': pnl,
            'bars_held': exit_bar - self.entry_bar,
        })
        
        self.trades.append(self.current_trade)
        
        # Reset position state
        self.in_position = False
        self.position_type = None
        self.entry_bar = None
        self.entry_price = None
        self.current_trade = None
    
    def _calculate_statistics(self) -> Dict:
        """Calculate backtest statistics"""
        if not self.trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'total_pnl': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0,
                'trades': []
            }
        
        trades_df = pd.DataFrame(self.trades)
        
        # Basic stats
        total_trades = len(trades_df)
        winners = trades_df[trades_df['pnl'] > 0]
        losers = trades_df[trades_df['pnl'] < 0]
        
        win_rate = len(winners) / total_trades * 100 if total_trades > 0 else 0
        
        gross_profit = winners['pnl'].sum() if len(winners) > 0 else 0
        gross_loss = abs(losers['pnl'].sum()) if len(losers) > 0 else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        total_pnl = trades_df['pnl'].sum()
        avg_win = winners['pnl'].mean() if len(winners) > 0 else 0
        avg_loss = losers['pnl'].mean() if len(losers) > 0 else 0
        
        # Drawdown
        cumulative_pnl = trades_df['pnl'].cumsum()
        running_max = cumulative_pnl.cummax()
        drawdown = running_max - cumulative_pnl
        max_drawdown = drawdown.max()
        
        # Sharpe (simplified: returns / std)
        if len(trades_df) > 1:
            sharpe_ratio = trades_df['pnl'].mean() / trades_df['pnl'].std()
        else:
            sharpe_ratio = 0
        
        # Long vs Short stats
        long_trades = trades_df[trades_df['direction'] == 'LONG']
        short_trades = trades_df[trades_df['direction'] == 'SHORT']
        
        long_wr = len(long_trades[long_trades['pnl'] > 0]) / len(long_trades) * 100 if len(long_trades) > 0 else 0
        short_wr = len(short_trades[short_trades['pnl'] > 0]) / len(short_trades) * 100 if len(short_trades) > 0 else 0
        
        avg_bars_held = trades_df['bars_held'].mean() if len(trades_df) > 0 else 0
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_win_loss_ratio': abs(avg_win / avg_loss) if avg_loss != 0 else 0,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'long_trades': len(long_trades),
            'short_trades': len(short_trades),
            'long_win_rate': long_wr,
            'short_win_rate': short_wr,
            'avg_bars_held': avg_bars_held,
            'trades': self.trades,
            'trades_df': trades_df,
        }
