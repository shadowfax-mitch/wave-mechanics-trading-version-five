"""
FRR Strategy Backtest Runner (Pure Python, no pandas)
Simplified implementation for environments without pandas
"""

import csv
from datetime import datetime
from collections import defaultdict
import json
from pathlib import Path


def load_csv(file_path):
    """Load CSV data into list of dicts"""
    data = []
    with open(file_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append({
                'time': row['time'],
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume']),
            })
    return data


def split_data_by_date(data, train_end, test_end):
    """Split data into train/test/validate sets"""
    train = []
    test = []
    validate = []
    
    for bar in data:
        date_str = bar['time'][:10]  # YYYY-MM-DD
        
        if date_str <= train_end:
            train.append(bar)
        elif date_str <= test_end:
            test.append(bar)
        else:
            validate.append(bar)
    
    return train, test, validate


def calculate_ema(values, period):
    """Calculate Exponential Moving Average"""
    if len(values) < period:
        return [None] * len(values)
    
    ema = [None] * len(values)
    multiplier = 2 / (period + 1)
    
    # Start with SMA
    ema[period - 1] = sum(values[:period]) / period
    
    # Calculate EMA
    for i in range(period, len(values)):
        ema[i] = (values[i] - ema[i-1]) * multiplier + ema[i-1]
    
    return ema


def calculate_std(values, period):
    """Calculate rolling standard deviation"""
    if len(values) < period:
        return [None] * len(values)
    
    std = [None] * len(values)
    
    for i in range(period - 1, len(values)):
        window = values[i - period + 1:i + 1]
        mean = sum(window) / len(window)
        variance = sum((x - mean) ** 2 for x in window) / (len(window) - 1)
        std[i] = variance ** 0.5
    
    return std


def detect_swing_highs(bars, strength=2):
    """Detect swing high fractals"""
    swing_highs = [False] * len(bars)
    
    for i in range(strength, len(bars) - strength):
        is_swing = True
        for j in range(1, strength + 1):
            if bars[i]['high'] <= bars[i - j]['high'] or bars[i]['high'] <= bars[i + j]['high']:
                is_swing = False
                break
        swing_highs[i] = is_swing
    
    return swing_highs


def detect_swing_lows(bars, strength=2):
    """Detect swing low fractals"""
    swing_lows = [False] * len(bars)
    
    for i in range(strength, len(bars) - strength):
        is_swing = True
        for j in range(1, strength + 1):
            if bars[i]['low'] >= bars[i - j]['low'] or bars[i]['low'] >= bars[i + j]['low']:
                is_swing = False
                break
        swing_lows[i] = is_swing
    
    return swing_lows


def calculate_atr(bars, period=14):
    """Calculate Average True Range"""
    if len(bars) < period + 1:
        return [None] * len(bars)
    
    tr_values = [None]  # First bar has no prior close
    
    for i in range(1, len(bars)):
        tr1 = bars[i]['high'] - bars[i]['low']
        tr2 = abs(bars[i]['high'] - bars[i-1]['close'])
        tr3 = abs(bars[i]['low'] - bars[i-1]['close'])
        tr = max(tr1, tr2, tr3)
        tr_values.append(tr)
    
    # Calculate ATR (simple moving average of TR)
    atr = [None] * len(bars)
    for i in range(period, len(bars)):
        atr[i] = sum(tr_values[i - period + 1:i + 1]) / period
    
    return atr


def simple_backtest(bars, params):
    """
    Simplified backtest - checks signal generation only
    Full backtest would require pandas for proper vectorization
    """
    print(f"\n  Analyzing {len(bars):,} bars...")
    
    # Extract close prices
    closes = [bar['close'] for bar in bars]
    
    # Calculate EMA and std
    ema = calculate_ema(closes, params['ema_period'])
    std = calculate_std(closes, params['ema_period'])
    
    # Calculate Z-scores
    z_scores = []
    for i in range(len(closes)):
        if ema[i] is not None and std[i] is not None and std[i] > 0:
            z = (closes[i] - ema[i]) / std[i]
            z_scores.append(z)
        else:
            z_scores.append(None)
    
    # Detect swings
    swing_highs = detect_swing_highs(bars, params['swing_strength'])
    swing_lows = detect_swing_lows(bars, params['swing_strength'])
    
    # Calculate ATR
    atr = calculate_atr(bars, params['atr_period'])
    
    # Count potential signals
    long_signals = 0
    short_signals = 0
    
    for i in range(len(bars)):
        if z_scores[i] is not None:
            if z_scores[i] <= -params['z_threshold']:
                long_signals += 1
            elif z_scores[i] >= params['z_threshold']:
                short_signals += 1
    
    # Count swings
    total_swing_highs = sum(swing_highs)
    total_swing_lows = sum(swing_lows)
    
    print(f"  ✓ Z-score extremes detected:")
    print(f"    - Oversold (Z ≤ -{params['z_threshold']}): {long_signals}")
    print(f"    - Overbought (Z ≥ {params['z_threshold']}): {short_signals}")
    print(f"  ✓ Swing points detected:")
    print(f"    - Swing Highs: {total_swing_highs}")
    print(f"    - Swing Lows: {total_swing_lows}")
    
    return {
        'bars': len(bars),
        'long_signals': long_signals,
        'short_signals': short_signals,
        'swing_highs': total_swing_highs,
        'swing_lows': total_swing_lows,
    }


def main():
    """Run simplified backtest"""
    print(f"\n{'='*60}")
    print(f"  FRR STRATEGY ANALYSIS (Simplified)")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # Parameters
    params = {
        'swing_strength': 2,
        'regime_window': 20,
        'amp_threshold': 0.6,
        'chop_threshold': 0.3,
        'energy_threshold': 50,
        'ema_period': 50,
        'z_threshold': 3.0,
        'atr_period': 14,
        'stop_atr_mult': 1.0,
        'max_hold_bars': 20,
        'daily_loss_limit': -200,
        'max_consecutive_losses': 3,
    }
    
    # Load data
    print(f"\n📂 Loading data...")
    data_path = Path.home() / '.openclaw' / 'workspace' / 'data' / 'MNQ_5min.csv'
    data = load_csv(str(data_path))
    print(f"  ✓ Loaded {len(data):,} bars from {data[0]['time']} to {data[-1]['time']}")
    
    # Split data
    print(f"\n✂️  Splitting data...")
    train, test, validate = split_data_by_date(data, '2023-12-31', '2025-06-30')
    print(f"  ✓ Train:    {len(train):,} bars")
    print(f"  ✓ Test:     {len(test):,} bars")
    print(f"  ✓ Validate: {len(validate):,} bars")
    
    # Analyze train set
    print(f"\n🔬 ANALYZING TRAIN SET")
    train_stats = simple_backtest(train, params)
    
    print(f"\n⚠️  LIMITATION: Full backtest requires pandas/numpy")
    print(f"  This simplified version only counts signals, not actual trades")
    print(f"  ")
    print(f"  To run full backtest with proper trade simulation:")
    print(f"  1. Install dependencies: sudo apt install python3-pip python3-venv")
    print(f"  2. Create venv: python3 -m venv .venv")
    print(f"  3. Install packages: .venv/bin/pip install pandas numpy")
    print(f"  4. Run: .venv/bin/python research/modules/run_backtest.py")
    
    print(f"\n{'='*60}\n")


if __name__ == '__main__':
    main()
