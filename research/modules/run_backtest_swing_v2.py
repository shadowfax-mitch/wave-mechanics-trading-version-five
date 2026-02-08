"""
Run backtest for Swing Reversal V2 strategy (RTH filter)
"""
import pandas as pd
from swing_reversal_v2 import SwingReversalV2
import json

# Load MNQ data
print("Loading MNQ data...")
df = pd.read_csv('data/MNQ_5min.csv', parse_dates=['time'])
df.rename(columns={'time': 'timestamp'}, inplace=True)
df.set_index('timestamp', inplace=True)
print(f"Loaded {len(df):,} bars ({df.index[0]} to {df.index[-1]})")

# Initialize strategy
strategy = SwingReversalV2()

# Run backtest
print("\nRunning backtest with RTH filter...")
results = strategy.backtest(df)

# Display results
print("\n" + "="*60)
print("SWING REVERSAL V2 - RTH FILTER RESULTS")
print("="*60)
print(f"Total Trades:     {results['total_trades']:,}")
print(f"Total P&L:        ${results['total_pnl']:,.2f}")
print(f"Per Trade:        ${results['total_pnl']/results['total_trades']:.2f}" if results['total_trades'] > 0 else "N/A")
print(f"Win Rate:         {results['win_rate']:.2f}%")
print(f"Profit Factor:    {results['profit_factor']:.2f}")
print(f"Avg Win:          ${results['avg_win']:.2f}")
print(f"Avg Loss:         ${results['avg_loss']:.2f}")
print(f"Avg W/L Ratio:    {results['avg_win_loss_ratio']:.2f}")
print(f"Max Drawdown:     ${results['max_drawdown']:,.2f}")
print(f"Sharpe Ratio:     {results['sharpe_ratio']:.2f}")
print(f"Avg Bars Held:    {results['avg_bars_held']:.1f}")
print("="*60)
print("\nLONG vs SHORT:")
print(f"Long Trades:      {results['long_trades']:,} ({results['long_win_rate']:.1f}% WR)")
print(f"Short Trades:     {results['short_trades']:,} ({results['short_win_rate']:.1f}% WR)")
print("="*60)

# Calculate annualized metrics
years = (df.index[-1] - df.index[0]).days / 365.25
trades_per_year = results['total_trades'] / years
pnl_per_year = results['total_pnl'] / years

print(f"\nANNUALIZED:")
print(f"Years:            {years:.1f}")
print(f"Trades/Year:      {trades_per_year:.0f} ({trades_per_year/12:.1f}/month, {trades_per_year/252:.1f}/day)")
print(f"P&L/Year:         ${pnl_per_year:,.0f}")
print("="*60)

# Load V1 results for comparison
try:
    with open('research/analysis/swing_v1_results.json', 'r') as f:
        v1_results = json.load(f)
    
    print("\nCOMPARISON vs V1 (No Filters):")
    print(f"Trades:   {v1_results['total_trades']:,} → {results['total_trades']:,} ({(results['total_trades']/v1_results['total_trades']-1)*100:+.1f}%)")
    print(f"P&L:      ${v1_results['total_pnl']:,.0f} → ${results['total_pnl']:,.0f} ({results['total_pnl']-v1_results['total_pnl']:+.0f})")
    print(f"Win Rate: {v1_results['win_rate']:.1f}% → {results['win_rate']:.1f}% ({results['win_rate']-v1_results['win_rate']:+.1f}%)")
    print(f"PF:       {v1_results['profit_factor']:.2f} → {results['profit_factor']:.2f} ({results['profit_factor']-v1_results['profit_factor']:+.2f})")
    print("="*60)
except:
    print("\n(V1 results not found for comparison)")

# Save results
with open('research/analysis/swing_v2_results.json', 'w') as f:
    json.dump(results, f, indent=2, default=str)

print("\nResults saved to: research/analysis/swing_v2_results.json")
print("\nFilter Layer 1 (RTH Only) applied.")
print("Next: Add Layer 2 (EMA trend filter) if results improved.")
