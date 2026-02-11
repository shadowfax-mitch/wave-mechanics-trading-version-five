"""
Al Brooks V2 Strategy — Fixed and Enhanced

Changes from V1:
1. FIXED trend detection (V1 classified everything as SIDEWAYS due to broken threshold)
2. With-trend entries don't require S/R — only counter-trend/sideways need S/R
3. ATR-capped stops — prevents 30+ tick catastrophic losses
4. R:R-based targets — target = risk × reward_ratio (minimum 1.5:1)
5. Breakeven trailing stop — move stop to entry after reaching 1R profit
6. Wider pattern recognition — 30-bar timeout, 3-bar validity window
7. EMA pullback entries — additional entry type for with-trend frequency
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional, Dict, List, Literal
from dataclasses import dataclass, field
from enum import Enum


class Trend(Enum):
    UP = "UP"
    DOWN = "DOWN"
    SIDEWAYS = "SIDEWAYS"


class PatternType(Enum):
    SECOND_ENTRY_LONG = "H2"
    SECOND_ENTRY_SHORT = "L2"
    EMA_PULLBACK_LONG = "EMA_PB_LONG"
    EMA_PULLBACK_SHORT = "EMA_PB_SHORT"


@dataclass
class SignalBar:
    bar_idx: int
    bar_range: float
    body_size: float
    upper_wick: float
    lower_wick: float
    is_bullish: bool
    quality_score: float


@dataclass
class KeyLevel:
    price: float
    level_type: Literal["SUPPORT", "RESISTANCE"]
    strength: int
    first_touch_idx: int
    last_touch_idx: int


@dataclass
class SecondEntryState:
    new_extreme_idx: Optional[int] = None
    new_extreme_price: Optional[float] = None
    is_tracking_high: bool = False
    pullback_idx: Optional[int] = None
    pullback_price: Optional[float] = None
    first_entry_idx: Optional[int] = None
    entry_count: int = 0
    second_entry_bar: Optional[int] = None  # bar where count hit 2


class AlBrooksV2Strategy:
    """Al Brooks V2 — Fixed trend detection, ATR-capped stops, R:R targets"""

    def __init__(self, params: Optional[Dict] = None):
        self.params = {
            # Trend
            'trend_ema_period': 20,
            'trend_slope_threshold': 0.03,   # normalized EMA slope for UP/DOWN
            'trend_slope_lookback': 10,       # bars to measure slope over

            # S/R
            'sr_lookback': 100,
            'sr_proximity_ticks': 8,
            'sr_min_touches': 2,
            'sr_swing_strength': 2,          # bars on each side for swing point

            # Pattern
            'pullback_min_size': 0.3,        # min pullback in ATR multiples
            'pattern_timeout': 30,           # bars before pattern expires
            'pattern_validity': 3,           # bars that count=2 stays valid
            'ema_pullback_proximity': 1.0,   # ATR distance to EMA for pullback entry

            # Signal bar
            'min_bar_size_atr': 0.2,
            'max_bar_size_atr': 3.0,
            'min_body_ratio': 0.3,
            'max_wick_ratio': 0.7,
            'min_signal_quality': 40,

            # Risk management
            'atr_period': 14,
            'stop_offset_ticks': 1,
            'tick_size': 0.25,
            'tick_value': 0.50,              # MNQ default
            'max_stop_atr': 1.5,             # cap stop at this × ATR
            'reward_risk_ratio': 1.5,        # target = risk × this
            'min_target_ticks': 6,           # minimum target in ticks
            'max_hold_bars': 40,
            'use_breakeven_trail': True,
            'min_bars_before_stop': 0,       # grace period: don't check stop for N bars
            'use_atr_trail': False,          # ATR trailing stop (replaces fixed target)
            'atr_trail_activation': 1.0,     # start trailing after this × risk in profit
            'atr_trail_distance': 1.0,       # trail distance in ATR multiples

            # Circuit breakers
            'daily_loss_limit': -200,
            'max_consecutive_losses': 4,

            # Session
            'rth_only': True,
            'rth_start': '08:30',
            'rth_end': '15:00',

            # Entry modes
            'with_trend_needs_sr': False,     # with-trend entries need S/R?
            'counter_trend_allowed': True,    # allow counter-trend at S/R?
            'ema_pullback_enabled': True,     # enable EMA pullback entries?
            'sideways_entries_allowed': True,  # allow entries in sideways trend?
            'allow_shorts': True,             # allow short entries?
            'min_stop_ticks': 0,              # minimum stop distance in ticks
        }

        if params:
            self.params.update(params)

        self.reset_state()

    def reset_state(self):
        self.in_position = False
        self.position_type = None
        self.entry_bar = None
        self.entry_price = None
        self.stop_price = None
        self.original_stop = None  # for trailing stop reference
        self.target_price = None
        self.daily_pnl = 0
        self.consecutive_losses = 0
        self.last_rth_date = None  # Track last RTH date for proper daily reset
        self.trades = []
        self.current_trade = None
        self.h2_state = SecondEntryState()
        self.l2_state = SecondEntryState()
        self.key_levels: List[KeyLevel] = []

    # ==================== TREND DETECTION (FIXED) ====================

    def detect_trend(self, df: pd.DataFrame, idx: int) -> Trend:
        lookback = self.params['trend_slope_lookback']
        if idx < max(self.params['trend_ema_period'], lookback):
            return Trend.SIDEWAYS

        ema = df['ema'].iloc[idx]
        close = df['close'].iloc[idx]
        atr = df['atr'].iloc[idx]

        if atr <= 0:
            return Trend.SIDEWAYS

        # Normalized EMA slope: change per bar / ATR
        ema_now = df['ema'].iloc[idx]
        ema_prev = df['ema'].iloc[idx - lookback]
        slope = (ema_now - ema_prev) / (lookback * atr)

        threshold = self.params['trend_slope_threshold']

        if close > ema and slope > threshold:
            return Trend.UP
        elif close < ema and slope < -threshold:
            return Trend.DOWN
        else:
            return Trend.SIDEWAYS

    # ==================== SUPPORT/RESISTANCE ====================

    def identify_key_levels(self, df: pd.DataFrame, idx: int) -> List[KeyLevel]:
        levels = []
        lookback = min(self.params['sr_lookback'], idx)
        strength = self.params['sr_swing_strength']

        if lookback < 10 or idx < strength * 2 + 1:
            return levels

        start_idx = max(strength, idx - lookback)
        end_idx = idx - strength

        if start_idx >= end_idx:
            return levels

        highs = df['high'].values
        lows = df['low'].values

        swing_highs = []
        swing_lows = []

        for i in range(start_idx, end_idx + 1):
            # Swing high: higher than `strength` bars on each side
            is_swing_high = True
            for j in range(1, strength + 1):
                if i - j < 0 or i + j >= len(df):
                    is_swing_high = False
                    break
                if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                    is_swing_high = False
                    break
            if is_swing_high:
                swing_highs.append((i, highs[i]))

            # Swing low: lower than `strength` bars on each side
            is_swing_low = True
            for j in range(1, strength + 1):
                if i - j < 0 or i + j >= len(df):
                    is_swing_low = False
                    break
                if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                    is_swing_low = False
                    break
            if is_swing_low:
                swing_lows.append((i, lows[i]))

        proximity = self.params['sr_proximity_ticks'] * self.params['tick_size']

        # Cluster swing highs into resistance levels
        for cluster_price, indices in self._cluster_swings(swing_highs, proximity):
            if len(indices) >= self.params['sr_min_touches']:
                levels.append(KeyLevel(
                    price=cluster_price,
                    level_type="RESISTANCE",
                    strength=len(indices),
                    first_touch_idx=min(indices),
                    last_touch_idx=max(indices),
                ))

        # Cluster swing lows into support levels
        for cluster_price, indices in self._cluster_swings(swing_lows, proximity):
            if len(indices) >= self.params['sr_min_touches']:
                levels.append(KeyLevel(
                    price=cluster_price,
                    level_type="SUPPORT",
                    strength=len(indices),
                    first_touch_idx=min(indices),
                    last_touch_idx=max(indices),
                ))

        return levels

    def _cluster_swings(self, swings: list, proximity: float):
        if not swings:
            return []

        sorted_swings = sorted(swings, key=lambda x: x[1])
        clusters = []
        current_indices = [sorted_swings[0][0]]
        current_prices = [sorted_swings[0][1]]

        for bar_idx, price in sorted_swings[1:]:
            if abs(price - current_prices[0]) <= proximity:
                current_indices.append(bar_idx)
                current_prices.append(price)
            else:
                avg = round(np.mean(current_prices) / self.params['tick_size']) * self.params['tick_size']
                clusters.append((avg, current_indices))
                current_indices = [bar_idx]
                current_prices = [price]

        avg = round(np.mean(current_prices) / self.params['tick_size']) * self.params['tick_size']
        clusters.append((avg, current_indices))

        return clusters

    def is_at_key_level(self, df: pd.DataFrame, idx: int, levels: List[KeyLevel]) -> Optional[KeyLevel]:
        close = df['close'].iloc[idx]
        high = df['high'].iloc[idx]
        low = df['low'].iloc[idx]
        proximity = self.params['sr_proximity_ticks'] * self.params['tick_size']

        best_level = None
        best_dist = float('inf')

        for level in levels:
            if level.level_type == "RESISTANCE":
                dist = abs(high - level.price)
                if dist <= proximity or (low < level.price < high):
                    if dist < best_dist:
                        best_dist = dist
                        best_level = level
            elif level.level_type == "SUPPORT":
                dist = abs(low - level.price)
                if dist <= proximity or (low < level.price < high):
                    if dist < best_dist:
                        best_dist = dist
                        best_level = level

        return best_level

    # ==================== PATTERN DETECTION (IMPROVED) ====================

    def update_pattern_states(self, df: pd.DataFrame, idx: int):
        """Update both H2 and L2 pattern state machines independently"""
        if idx < 3:
            return

        trend = self.detect_trend(df, idx)
        atr = df['atr'].iloc[idx]
        if atr <= 0:
            return

        high = df['high'].iloc[idx]
        low = df['low'].iloc[idx]

        # Update H2 state (tracking longs after pullback from high)
        if trend != Trend.DOWN:  # Only track H2 in UP or SIDEWAYS
            self._update_h2_state(df, idx, atr)

        # Update L2 state (tracking shorts after pullback from low)
        if trend != Trend.UP:  # Only track L2 in DOWN or SIDEWAYS
            self._update_l2_state(df, idx, atr)

    def _update_h2_state(self, df: pd.DataFrame, idx: int, atr: float):
        state = self.h2_state
        high = df['high'].iloc[idx]
        low = df['low'].iloc[idx]
        timeout = self.params['pattern_timeout']

        # Check if second_entry_bar validity has expired
        if state.second_entry_bar is not None:
            if idx - state.second_entry_bar >= self.params['pattern_validity']:
                state.second_entry_bar = None
                state.entry_count = 0

        # New 20-bar high resets tracking
        lookback_start = max(0, idx - 20)
        recent_high = df['high'].iloc[lookback_start:idx].max() if idx > lookback_start else 0
        if high > recent_high:
            state.new_extreme_idx = idx
            state.new_extreme_price = high
            state.is_tracking_high = True
            state.pullback_idx = None
            state.pullback_price = None
            state.first_entry_idx = None
            state.entry_count = 0
            state.second_entry_bar = None
            return

        # Need a new extreme to start tracking
        if state.new_extreme_idx is None:
            return

        # Timeout
        if idx - state.new_extreme_idx > timeout:
            state.new_extreme_idx = None
            return

        # Detect pullback from the high
        if state.pullback_idx is None:
            # Look for a bar that dips (pullback from the high)
            pullback_size = state.new_extreme_price - low
            if pullback_size >= self.params['pullback_min_size'] * atr:
                state.pullback_idx = idx
                state.pullback_price = low
            return

        # Detect first entry (first bounce after pullback)
        if state.entry_count == 0 and state.first_entry_idx is None:
            if idx > state.pullback_idx:
                prev_high = df['high'].iloc[idx - 1]
                if high > prev_high:
                    state.first_entry_idx = idx
                    state.entry_count = 1
            return

        # Detect second entry
        if state.entry_count == 1:
            if idx - state.first_entry_idx > timeout:
                # Reset — took too long
                state.entry_count = 0
                state.first_entry_idx = None
                return

            prev_high = df['high'].iloc[idx - 1]
            if high > prev_high and idx > state.first_entry_idx:
                # Verify we haven't made a new high beyond the original extreme
                max_since_first = df['high'].iloc[state.first_entry_idx:idx].max()
                if max_since_first <= state.new_extreme_price:
                    state.entry_count = 2
                    state.second_entry_bar = idx

    def _update_l2_state(self, df: pd.DataFrame, idx: int, atr: float):
        state = self.l2_state
        high = df['high'].iloc[idx]
        low = df['low'].iloc[idx]
        timeout = self.params['pattern_timeout']

        # Check if second_entry_bar validity has expired
        if state.second_entry_bar is not None:
            if idx - state.second_entry_bar >= self.params['pattern_validity']:
                state.second_entry_bar = None
                state.entry_count = 0

        # New 20-bar low resets tracking
        lookback_start = max(0, idx - 20)
        recent_low = df['low'].iloc[lookback_start:idx].min() if idx > lookback_start else float('inf')
        if low < recent_low:
            state.new_extreme_idx = idx
            state.new_extreme_price = low
            state.is_tracking_high = False
            state.pullback_idx = None
            state.pullback_price = None
            state.first_entry_idx = None
            state.entry_count = 0
            state.second_entry_bar = None
            return

        if state.new_extreme_idx is None:
            return

        if idx - state.new_extreme_idx > timeout:
            state.new_extreme_idx = None
            return

        # Detect pullback from the low
        if state.pullback_idx is None:
            pullback_size = high - state.new_extreme_price
            if pullback_size >= self.params['pullback_min_size'] * atr:
                state.pullback_idx = idx
                state.pullback_price = high
            return

        # First entry (first drop after pullback)
        if state.entry_count == 0 and state.first_entry_idx is None:
            if idx > state.pullback_idx:
                prev_low = df['low'].iloc[idx - 1]
                if low < prev_low:
                    state.first_entry_idx = idx
                    state.entry_count = 1
            return

        # Second entry
        if state.entry_count == 1:
            if idx - state.first_entry_idx > timeout:
                state.entry_count = 0
                state.first_entry_idx = None
                return

            prev_low = df['low'].iloc[idx - 1]
            if low < prev_low and idx > state.first_entry_idx:
                min_since_first = df['low'].iloc[state.first_entry_idx:idx].min()
                if min_since_first >= state.new_extreme_price:
                    state.entry_count = 2
                    state.second_entry_bar = idx

    def detect_patterns(self, df: pd.DataFrame, idx: int, trend: Trend) -> List[PatternType]:
        """Return all currently active patterns"""
        patterns = []

        # H2 (second entry long)
        if self.h2_state.entry_count == 2 and self.h2_state.second_entry_bar is not None:
            bars_since = idx - self.h2_state.second_entry_bar
            if bars_since < self.params['pattern_validity']:
                if trend == Trend.UP or trend == Trend.SIDEWAYS:
                    patterns.append(PatternType.SECOND_ENTRY_LONG)

        # L2 (second entry short)
        if self.l2_state.entry_count == 2 and self.l2_state.second_entry_bar is not None:
            bars_since = idx - self.l2_state.second_entry_bar
            if bars_since < self.params['pattern_validity']:
                if trend == Trend.DOWN or trend == Trend.SIDEWAYS:
                    patterns.append(PatternType.SECOND_ENTRY_SHORT)

        # EMA pullback entries (additional frequency)
        if self.params['ema_pullback_enabled']:
            ema = df['ema'].iloc[idx]
            atr = df['atr'].iloc[idx]
            close = df['close'].iloc[idx]
            low = df['low'].iloc[idx]
            high = df['high'].iloc[idx]
            proximity = self.params['ema_pullback_proximity'] * atr

            if trend == Trend.UP:
                # Price pulled back to touch EMA and bouncing
                if low <= ema + proximity and close > ema:
                    # Confirm bounce: current close > prev close
                    if idx > 0 and close > df['close'].iloc[idx - 1]:
                        patterns.append(PatternType.EMA_PULLBACK_LONG)

            elif trend == Trend.DOWN:
                # Price rallied to touch EMA and rejecting
                if high >= ema - proximity and close < ema:
                    if idx > 0 and close < df['close'].iloc[idx - 1]:
                        patterns.append(PatternType.EMA_PULLBACK_SHORT)

        return patterns

    # ==================== SIGNAL BAR QUALITY ====================

    def analyze_signal_bar(self, df: pd.DataFrame, idx: int, pattern: PatternType) -> SignalBar:
        open_price = df['open'].iloc[idx]
        high = df['high'].iloc[idx]
        low = df['low'].iloc[idx]
        close = df['close'].iloc[idx]
        atr = df['atr'].iloc[idx]

        bar_range = high - low
        body_size = abs(close - open_price)
        upper_wick = high - max(open_price, close)
        lower_wick = min(open_price, close) - low
        is_bullish = close > open_price

        score = 100.0

        # Bar size check
        if bar_range < self.params['min_bar_size_atr'] * atr:
            score -= 40
        elif bar_range > self.params['max_bar_size_atr'] * atr:
            score -= 30

        # Body ratio
        body_ratio = body_size / bar_range if bar_range > 0 else 0
        if body_ratio < self.params['min_body_ratio']:
            score -= 30
        else:
            score += min(20, body_ratio * 20)

        # Wick alignment
        is_long = pattern in [PatternType.SECOND_ENTRY_LONG, PatternType.EMA_PULLBACK_LONG]
        is_short = pattern in [PatternType.SECOND_ENTRY_SHORT, PatternType.EMA_PULLBACK_SHORT]

        if is_long:
            if bar_range > 0 and upper_wick > bar_range * self.params['max_wick_ratio']:
                score -= 25
        elif is_short:
            if bar_range > 0 and lower_wick > bar_range * self.params['max_wick_ratio']:
                score -= 25

        # Direction alignment
        if is_long and not is_bullish:
            score -= 35
        elif is_short and is_bullish:
            score -= 35

        score = max(0, min(120, score))

        return SignalBar(
            bar_idx=idx,
            bar_range=bar_range,
            body_size=body_size,
            upper_wick=upper_wick,
            lower_wick=lower_wick,
            is_bullish=is_bullish,
            quality_score=score,
        )

    # ==================== TRADE MANAGEMENT ====================

    def calculate_entry_stop_target(self, df: pd.DataFrame, idx: int,
                                    pattern: PatternType) -> Tuple[float, float, float]:
        high = df['high'].iloc[idx]
        low = df['low'].iloc[idx]
        close = df['close'].iloc[idx]
        atr = df['atr'].iloc[idx]
        tick = self.params['tick_size']
        offset = self.params['stop_offset_ticks'] * tick
        max_stop = self.params['max_stop_atr'] * atr

        is_long = pattern in [PatternType.SECOND_ENTRY_LONG, PatternType.EMA_PULLBACK_LONG]

        if is_long:
            entry = close
            raw_stop = low - offset
            stop_dist = entry - raw_stop

            # Cap the stop
            if stop_dist > max_stop:
                stop = entry - max_stop
                stop_dist = max_stop
            else:
                stop = raw_stop

            # R:R target
            target = entry + stop_dist * self.params['reward_risk_ratio']

            # Enforce minimum target
            min_target_dist = self.params['min_target_ticks'] * tick
            if target - entry < min_target_dist:
                target = entry + min_target_dist

        else:  # SHORT
            entry = close
            raw_stop = high + offset
            stop_dist = raw_stop - entry

            if stop_dist > max_stop:
                stop = entry + max_stop
                stop_dist = max_stop
            else:
                stop = raw_stop

            target = entry - stop_dist * self.params['reward_risk_ratio']

            min_target_dist = self.params['min_target_ticks'] * tick
            if entry - target < min_target_dist:
                target = entry - min_target_dist

        # Round to tick size
        stop = round(stop / tick) * tick
        target = round(target / tick) * tick

        return (entry, stop, target)

    # ==================== BACKTEST ENGINE ====================

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)

        # ATR
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(window=self.params['atr_period']).mean()

        # EMA
        df['ema'] = df['close'].ewm(span=self.params['trend_ema_period'], adjust=False).mean()

        # RTH filter
        if self.params['rth_only']:
            start_h, start_m = map(int, self.params['rth_start'].split(':'))
            end_h, end_m = map(int, self.params['rth_end'].split(':'))
            hour = df.index.hour
            minute = df.index.minute
            df['is_rth'] = (
                ((hour > start_h) | ((hour == start_h) & (minute >= start_m))) &
                ((hour < end_h) | ((hour == end_h) & (minute < end_m)))
            )
        else:
            df['is_rth'] = True

        return df

    def run_backtest(self, df: pd.DataFrame, verbose: bool = False) -> pd.DataFrame:
        self.reset_state()
        df = self.prepare_data(df)

        total_bars = len(df)
        progress_interval = max(1, total_bars // 20)

        for idx in range(len(df)):
            if verbose and idx % progress_interval == 0 and idx > 0:
                pct = (idx / total_bars) * 100
                print(f"  {pct:.0f}% ({len(self.trades)} trades)")

            if not df['is_rth'].iloc[idx]:
                continue

            if pd.isna(df['atr'].iloc[idx]) or df['atr'].iloc[idx] <= 0:
                continue

            current_date = df.index[idx].date()

            # New day reset — compare against last RTH bar's date, not raw idx-1
            if self.last_rth_date is not None and current_date != self.last_rth_date:
                self.daily_pnl = 0
                self.consecutive_losses = 0
                # Close any overnight position
                if self.in_position:
                    self._exit_trade(df, idx, df['open'].iloc[idx], 'NEW_DAY')
            self.last_rth_date = current_date

            # Update S/R every 20 bars
            if idx % 20 == 0:
                self.key_levels = self.identify_key_levels(df, idx)

            # Update pattern states
            self.update_pattern_states(df, idx)

            # Manage position or look for entries
            if self.in_position:
                self._manage_position(df, idx)
            else:
                if self.daily_pnl <= self.params['daily_loss_limit']:
                    continue
                if self.consecutive_losses >= self.params['max_consecutive_losses']:
                    continue
                self._check_entry_signals(df, idx)

        if verbose:
            print(f"  100% ({len(self.trades)} trades)")

        if self.trades:
            return pd.DataFrame(self.trades)
        return pd.DataFrame()

    def _check_entry_signals(self, df: pd.DataFrame, idx: int):
        trend = self.detect_trend(df, idx)

        # Block sideways entries if disabled
        if trend == Trend.SIDEWAYS and not self.params.get('sideways_entries_allowed', True):
            return

        patterns = self.detect_patterns(df, idx, trend)

        if not patterns:
            return

        # Filter out shorts if disabled
        if not self.params.get('allow_shorts', True):
            patterns = [p for p in patterns if p in
                       [PatternType.SECOND_ENTRY_LONG, PatternType.EMA_PULLBACK_LONG]]
            if not patterns:
                return

        # Pick the best pattern (prefer H2/L2 over EMA pullback)
        pattern = patterns[0]  # Already prioritized

        # Signal bar quality
        signal_bar = self.analyze_signal_bar(df, idx, pattern)
        if signal_bar.quality_score < self.params['min_signal_quality']:
            return

        # Determine if S/R is needed
        is_long = pattern in [PatternType.SECOND_ENTRY_LONG, PatternType.EMA_PULLBACK_LONG]
        is_with_trend = (is_long and trend == Trend.UP) or (not is_long and trend == Trend.DOWN)
        is_counter_trend = (is_long and trend == Trend.DOWN) or (not is_long and trend == Trend.UP)

        key_level = None

        if is_counter_trend:
            if not self.params['counter_trend_allowed']:
                return
            # Counter-trend ALWAYS needs S/R
            key_level = self.is_at_key_level(df, idx, self.key_levels)
            if key_level is None:
                return
        elif is_with_trend:
            if self.params['with_trend_needs_sr']:
                key_level = self.is_at_key_level(df, idx, self.key_levels)
                if key_level is None:
                    return
            else:
                # Optional: check S/R for bonus confidence (not required)
                key_level = self.is_at_key_level(df, idx, self.key_levels)
        else:
            # Sideways — need S/R
            key_level = self.is_at_key_level(df, idx, self.key_levels)
            if key_level is None:
                return

        # Calculate entry/stop/target
        entry, stop, target = self.calculate_entry_stop_target(df, idx, pattern)

        # Minimum stop distance check
        min_stop = self.params.get('min_stop_ticks', 0) * self.params['tick_size']
        if min_stop > 0 and abs(entry - stop) < min_stop:
            return

        # Enter
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

        # Reset pattern state after entry to prevent re-entry
        if pattern == PatternType.SECOND_ENTRY_LONG:
            self.h2_state = SecondEntryState()
        elif pattern == PatternType.SECOND_ENTRY_SHORT:
            self.l2_state = SecondEntryState()

    def _manage_position(self, df: pd.DataFrame, idx: int):
        high = df['high'].iloc[idx]
        low = df['low'].iloc[idx]
        close = df['close'].iloc[idx]
        atr = df['atr'].iloc[idx] if not pd.isna(df['atr'].iloc[idx]) else 0

        is_long = self.position_type == 'LONG'
        bars_held = idx - self.entry_bar
        grace = self.params.get('min_bars_before_stop', 0)

        # Check stop (respecting grace period)
        if bars_held >= grace:
            if is_long and low <= self.stop_price:
                self._exit_trade(df, idx, self.stop_price, 'STOP')
                return
            elif not is_long and high >= self.stop_price:
                self._exit_trade(df, idx, self.stop_price, 'STOP')
                return

        # Check target (always, even during grace period)
        if not self.params.get('use_atr_trail', False):
            # Fixed target mode
            if is_long and high >= self.target_price:
                self._exit_trade(df, idx, self.target_price, 'TARGET')
                return
            elif not is_long and low <= self.target_price:
                self._exit_trade(df, idx, self.target_price, 'TARGET')
                return

        # Time exit
        if bars_held >= self.params['max_hold_bars']:
            self._exit_trade(df, idx, close, 'TIME')
            return

        # ATR trailing stop (replaces fixed target)
        if self.params.get('use_atr_trail', False) and atr > 0:
            risk = abs(self.entry_price - self.original_stop)
            activation = self.params.get('atr_trail_activation', 1.0) * risk
            trail_dist = self.params.get('atr_trail_distance', 1.0) * atr

            if is_long:
                unrealized = high - self.entry_price
                if unrealized >= activation:
                    new_stop = high - trail_dist
                    if new_stop > self.stop_price:
                        self.stop_price = round(new_stop / self.params['tick_size']) * self.params['tick_size']
            else:
                unrealized = self.entry_price - low
                if unrealized >= activation:
                    new_stop = low + trail_dist
                    if new_stop < self.stop_price:
                        self.stop_price = round(new_stop / self.params['tick_size']) * self.params['tick_size']

        # Breakeven trailing stop (simpler alternative)
        elif self.params.get('use_breakeven_trail', False):
            risk = abs(self.entry_price - self.original_stop)
            if risk > 0:
                if is_long:
                    unrealized = high - self.entry_price
                    if unrealized >= risk and self.stop_price < self.entry_price:
                        self.stop_price = self.entry_price
                else:
                    unrealized = self.entry_price - low
                    if unrealized >= risk and self.stop_price > self.entry_price:
                        self.stop_price = self.entry_price

    def _exit_trade(self, df: pd.DataFrame, idx: int, exit_price: float, reason: str):
        is_long = self.position_type == 'LONG'
        pnl_ticks = (exit_price - self.entry_price) / self.params['tick_size'] if is_long else \
                    (self.entry_price - exit_price) / self.params['tick_size']
        pnl_dollars = pnl_ticks * self.params['tick_value']

        self.daily_pnl += pnl_dollars
        if pnl_dollars < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        self.current_trade.update({
            'exit_time': df.index[idx],
            'exit_idx': idx,
            'exit_price': exit_price,
            'exit_reason': reason,
            'pnl_ticks': round(pnl_ticks, 2),
            'pnl_dollars': round(pnl_dollars, 2),
            'bars_held': idx - self.entry_bar,
        })
        self.trades.append(self.current_trade.copy())

        self.in_position = False
        self.position_type = None
        self.entry_bar = None
        self.entry_price = None
        self.stop_price = None
        self.original_stop = None
        self.target_price = None
        self.current_trade = None
