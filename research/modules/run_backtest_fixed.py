#!/usr/bin/env python3
"""Run FRR backtest with look-ahead bias fix and compare results."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from frr_strategy import FRRStrategy

# Load data
data_path = Path.home() / '.openclaw' / 'workspace' / 'data' / 'MNQ_5min.csv'
df = pd.read_csv(data_path, parse_dates=['time'], index_col='time')
df.index.name = 'timestamp'
print(f'Loaded {len(df):,} bars')

# Run with locked-in params (look-ahead bias now fixed)
strategy = FRRStrategy()
results = strategy.backtest(df)

print()
print('=' * 60)
print('BACKTEST RESULTS (LOOK-AHEAD BIAS FIXED)')
print('=' * 60)
for k, v in sorted(results.items()):
    if isinstance(v, float):
        print(f"  {k:25s} {v:.4f}")
    else:
        print(f"  {k:25s} {v}")

# Compare
months = 81  # ~6.7 years
print()
print('=' * 60)
print('COMPARISON TO PREVIOUS (WITH LOOK-AHEAD BIAS)')
print('=' * 60)
print(f'Previous: 547 trades, 59.0% WR, 3.27 PF, +$3,590, 6.75 trades/mo')
t = results['total_trades']
wr = results['win_rate']
pf = results['profit_factor']
pnl = results['total_pnl']
print(f'Now:      {t} trades, {wr:.1f}% WR, {pf:.2f} PF, ${pnl:.2f}, {t/months:.1f} trades/mo')
print()
print(f'NinjaTrader reference: ~0.9 trades/mo, 66.67% WR, +$34')
