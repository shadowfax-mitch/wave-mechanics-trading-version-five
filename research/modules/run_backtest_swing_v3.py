"""
Run backtest for Swing Reversal V3 strategy (RTH + EMA trend filter)
"""
import pandas as pd
from swing_reversal_v3 import SwingReversalV3
import json

# Load MNQ data
print("Loading MNQ data...")
df = pd.read_csv('data/MNQ_5min.csv', parse_dates=['time'])
df.rename(columns={'time': 'timestamp'}, inplace=True)
df.set_index('timestamp', inplace=True)
print(f"Loaded {len(df):,} bars ({df.index[0]} to {df.index[-1]})")

# Initialize strategy
strategy = SwingReversalV3()

# Run backtest
print("\nRunning backtest with RTH + EMA(21) trend filter...")
results = strategy.backtest(df)

# Display results
print("\n" + "="*60)
print("SWING REVERSAL V3 - RTH + EMA TREND FILTER")
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

# Load previous results for comparison
try:
    with open('research/analysis/swing_v2_results.json', 'r') as f:
        v2_results = json.load(f)
    
    print("\nCOMPARISON vs V2 (RTH Only):")
    print(f"Trades:   {v2_results['total_trades']:,} → {results['total_trades']:,} ({(results['total_trades']/v2_results['total_trades']-1)*100:+.1f}%)")
    print(f"P&L:      ${v2_results['total_pnl']:,.0f} → ${results['total_pnl']:,.0f} ({results['total_pnl']-v2_results['total_pnl']:+.0f})")
    print(f"Win Rate: {v2_results['win_rate']:.1f}% → {results['win_rate']:.1f}% ({results['win_rate']-v2_results['win_rate']:+.1f}%)")
    print(f"PF:       {v2_results['profit_factor']:.2f} → {results['profit_factor']:.2f} ({results['profit_factor']-v2_results['profit_factor']:+.2f})")
    print(f"Per Day:  {v2_results['total_trades']/(years*252):.1f} → {trades_per_year/252:.1f}")
    
    # Show progression
    with open('research/analysis/swing_v1_results.json', 'r') as f:
        v1_results = json.load(f)
    
    print("\nPROGRESSION (V1 → V2 → V3):")
    print(f"Trades:   {v1_results['total_trades']:,} → {v2_results['total_trades']:,} → {results['total_trades']:,}")
    print(f"Win Rate: {v1_results['win_rate']:.1f}% → {v2_results['win_rate']:.1f}% → {results['win_rate']:.1f}%")
    print(f"PF:       {v1_results['profit_factor']:.2f} → {v2_results['profit_factor']:.2f} → {results['profit_factor']:.2f}")
    print(f"P&L:      ${v1_results['total_pnl']:,.0f} → ${v2_results['total_pnl']:,.0f} → ${results['total_pnl']:,.0f}")
    print("="*60)
except Exception as e:
    print(f"\n(Previous results not found: {e})")

# Save results
with open('research/analysis/swing_v3_results.json', 'w') as f:
    json.dump(results, f, indent=2, default=str)

print("\nResults saved to: research/analysis/swing_v3_results.json")

# Decision point
if results['profit_factor'] >= 1.5 and results['win_rate'] >= 55:
    print("\n🎉 SUCCESS! Strategy meets criteria (PF≥1.5, WR≥55%)")
    print("Ready for further validation (walk-forward, sensitivity, etc.)")
elif results['profit_factor'] > v2_results['profit_factor'] + 0.2:
    print("\n✅ IMPROVED! EMA filter helped significantly.")
    print("Consider Layer 3 filters or parameter tuning.")
else:
    print("\n⚠️  EMA filter didn't help much.")
    print("Need matrix testing of multiple filter combinations.")
