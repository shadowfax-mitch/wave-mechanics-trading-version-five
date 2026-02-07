"""
Quick MES validation - same FRR strategy on MES data
"""
import pandas as pd
import numpy as np
from pathlib import Path
from frr_strategy import FRRStrategy
import json

# Load MES data
print("Loading MES data...")
data_path = Path.home() / '.openclaw' / 'workspace' / 'data' / 'MES_5min.csv'
df = pd.read_csv(data_path, parse_dates=['time'], index_col='time')
print(f"Loaded {len(df):,} bars ({df.index[0]} to {df.index[-1]})")

# Initialize strategy with same parameters as MNQ
strategy = FRRStrategy()

# Run backtest
print("\nRunning backtest...")
results = strategy.backtest(df, slippage=2.0, commission=1.0)

# Extract metrics
summary = {
    'total_trades': results['total_trades'],
    'total_pnl': results['total_pnl'],
    'win_rate': results['win_rate'],
    'profit_factor': results['profit_factor'],
    'avg_win': results['avg_win'],
    'avg_loss': results['avg_loss'],
    'max_drawdown': results['max_drawdown']
}

# Calculate per-trade
if summary['total_trades'] > 0:
    summary['per_trade'] = summary['total_pnl'] / summary['total_trades']
else:
    summary['per_trade'] = 0

# Print results
print("\n" + "="*60)
print("MES BACKTEST RESULTS (2019-2026)")
print("="*60)
print(f"Total Trades:     {summary['total_trades']:,}")
print(f"Total P&L:        ${summary['total_pnl']:,.2f}")
print(f"Per Trade:        ${summary['per_trade']:.2f}")
print(f"Win Rate:         {summary['win_rate']:.2f}%")
print(f"Profit Factor:    {summary['profit_factor']:.2f}")
print(f"Avg Win:          ${summary['avg_win']:.2f}")
print(f"Avg Loss:         ${summary['avg_loss']:.2f}")
print(f"Max Drawdown:     ${summary['max_drawdown']:.2f}")
print("="*60)

# Comparison with MNQ
print("\nCOMPARISON:")
print(f"MNQ: 2,412 trades, $7.27/trade, 2.03 PF, 55.7% WR")
print(f"MES: {summary['total_trades']:,} trades, ${summary['per_trade']:.2f}/trade, {summary['profit_factor']:.2f} PF, {summary['win_rate']:.1f}% WR")

# Save results
output_path = Path.home() / '.openclaw' / 'workspace' / 'research' / 'analysis' / 'mes_backtest_results.json'
with open(output_path, 'w') as f:
    json.dump({
        'summary': summary,
        'trades': results['trades'],
    }, f, indent=2, default=str)

print(f"\nResults saved to: {output_path}")
