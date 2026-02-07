"""
FRR Strategy Backtest Runner - Full Dataset
Uses complete 2019-2026 dataset for comprehensive validation
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
from frr_strategy import FRRStrategy


def load_data(file_path: str) -> pd.DataFrame:
    """Load OHLCV data from CSV"""
    print(f"  Loading data from {file_path}...")
    df = pd.read_csv(file_path, parse_dates=['time'], index_col='time')
    return df


def print_results(results: dict, set_name: str):
    """Print backtest results in readable format"""
    print(f"\n{'='*60}")
    print(f"  {set_name} SET RESULTS")
    print(f"{'='*60}")
    
    print(f"\n📊 PERFORMANCE METRICS")
    print(f"  Total Trades:       {results['total_trades']}")
    print(f"  Win Rate:           {results['win_rate']:.2f}%")
    print(f"  Profit Factor:      {results['profit_factor']:.2f}")
    print(f"  Total P&L:          ${results['total_pnl']:.2f}")
    print(f"  Avg Win:            ${results['avg_win']:.2f}")
    print(f"  Avg Loss:           ${results['avg_loss']:.2f}")
    print(f"  Avg Win/Loss Ratio: {results['avg_win_loss_ratio']:.2f}")
    print(f"  Max Drawdown:       ${results['max_drawdown']:.2f}")
    print(f"  Sharpe Ratio:       {results['sharpe_ratio']:.2f}")
    
    print(f"\n📈 TRADE BREAKDOWN")
    print(f"  Long Trades:        {results['long_trades']} ({results['long_win_rate']:.1f}% WR)")
    print(f"  Short Trades:       {results['short_trades']} ({results['short_win_rate']:.1f}% WR)")
    print(f"  Avg Bars Held:      {results['avg_bars_held']:.1f}")
    
    # Acceptance criteria check
    print(f"\n✅ ACCEPTANCE CRITERIA")
    trades_check = results['total_trades'] >= 100  # Full 100+ for comprehensive test
    print(f"  [{'✓' if trades_check else '✗'}] 100+ trades: {results['total_trades']}")
    print(f"  [{'✓' if results['win_rate'] >= 55 else '✗'}] WR ≥ 55%: {results['win_rate']:.1f}%")
    print(f"  [{'✓' if results['profit_factor'] >= 1.5 else '✗'}] PF ≥ 1.5: {results['profit_factor']:.2f}")
    print(f"  [{'✓' if results['avg_win_loss_ratio'] >= 1.2 else '✗'}] Avg W/L ≥ 1.2: {results['avg_win_loss_ratio']:.2f}")
    
    avg_win = abs(results['avg_win'])
    max_dd_check = results['max_drawdown'] <= (3 * avg_win) if avg_win > 0 else False
    print(f"  [{'✓' if max_dd_check else '✗'}] Max DD ≤ 3× Avg Win: ${results['max_drawdown']:.2f} vs ${3*avg_win:.2f}")
    
    # Overall verdict
    passed = (
        trades_check and
        results['win_rate'] >= 55 and
        results['profit_factor'] >= 1.5 and
        results['avg_win_loss_ratio'] >= 1.2 and
        max_dd_check
    )
    
    print(f"\n{'🎉 PASS' if passed else '❌ FAIL'}: {set_name} set {'meets' if passed else 'does not meet'} acceptance criteria")
    
    return passed


def main():
    """Run full backtest on complete dataset"""
    print(f"\n{'='*60}")
    print(f"  FRR STRATEGY FULL BACKTEST (2019-2026)")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # Load data
    print(f"\n📂 Loading full dataset...")
    data_path = Path.home() / '.openclaw' / 'workspace' / 'data' / 'MNQ_5min.csv'
    df = load_data(str(data_path))
    print(f"  ✓ Loaded: {len(df):,} bars ({df.index[0]} to {df.index[-1]})")
    print(f"  ✓ Period: {(df.index[-1] - df.index[0]).days} days (~{(df.index[-1] - df.index[0]).days/365:.1f} years)")
    
    # Initialize strategy
    print(f"\n🎯 Initializing FRR strategy...")
    strategy = FRRStrategy()
    print(f"  ✓ Parameters:")
    print(f"     Z-threshold: {strategy.params['z_threshold']}")
    print(f"     Amplitude: {strategy.params['amp_threshold']}")
    print(f"     Chop: {strategy.params['chop_threshold']}")
    
    # Run backtest
    print(f"\n🔬 RUNNING BACKTEST...")
    print(f"  Processing {len(df):,} bars...")
    print(f"  (Estimated time: 30-90 seconds)")
    
    import time
    start_time = time.time()
    
    results = strategy.backtest(df, slippage=2.0, commission=1.0)
    
    elapsed = time.time() - start_time
    print(f"  ✓ Backtest complete in {elapsed:.1f} seconds")
    
    # Print results
    passed = print_results(results, "FULL DATASET (2019-2026)")
    
    # Save results
    output_dir = Path.home() / '.openclaw' / 'workspace' / 'research' / 'analysis'
    output_dir.mkdir(exist_ok=True)
    
    output = {
        'total_trades': results['total_trades'],
        'win_rate': results['win_rate'],
        'profit_factor': results['profit_factor'],
        'total_pnl': results['total_pnl'],
        'avg_win': results['avg_win'],
        'avg_loss': results['avg_loss'],
        'avg_win_loss_ratio': results['avg_win_loss_ratio'],
        'max_drawdown': results['max_drawdown'],
        'sharpe_ratio': results['sharpe_ratio'],
        'long_trades': results['long_trades'],
        'short_trades': results['short_trades'],
        'long_win_rate': results['long_win_rate'],
        'short_win_rate': results['short_win_rate'],
        'avg_bars_held': results['avg_bars_held'],
        'trades': results['trades'],
        'runtime_seconds': elapsed,
    }
    
    output_file = output_dir / 'full_backtest_results.json'
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\n  📁 Results saved to: {output_file}")
    
    # Trade frequency analysis
    if results['total_trades'] > 0:
        days_spanned = (df.index[-1] - df.index[0]).days
        trades_per_year = results['total_trades'] / (days_spanned / 365)
        trades_per_month = results['total_trades'] / (days_spanned / 30)
        
        print(f"\n📅 TRADE FREQUENCY")
        print(f"  Total period: {days_spanned} days ({days_spanned/365:.1f} years)")
        print(f"  Trades per year: {trades_per_year:.1f}")
        print(f"  Trades per month: {trades_per_month:.1f}")
        print(f"  Trades per week: {trades_per_month/4:.1f}")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"  FULL BACKTEST SUMMARY")
    print(f"{'='*60}")
    
    if passed:
        print(f"  ✅ Strategy meets ALL acceptance criteria")
        print(f"  ✅ Ready for Stage 3 (Walk-Forward Analysis)")
        print(f"  ✅ Ready for Stage 6 (Sensitivity Analysis)")
        print(f"  ✅ Ready for Stage 7 (NinjaTrader Validation)")
    elif results['total_trades'] >= 100:
        print(f"  ⚠️  Strategy has sufficient trades but fails other criteria")
        print(f"  💡 Recommendations:")
        if results['profit_factor'] < 1.5:
            print(f"     - Profit Factor too low ({results['profit_factor']:.2f}) - adjust exits")
        if results['win_rate'] < 55:
            print(f"     - Win Rate too low ({results['win_rate']:.1f}%) - tighten entries")
        if results['avg_win_loss_ratio'] < 1.2:
            print(f"     - Avg W/L too low ({results['avg_win_loss_ratio']:.2f}) - tighten stops or widen targets")
    else:
        print(f"  ❌ Insufficient trades: {results['total_trades']} (need 100+)")
        print(f"  💡 Recommendations:")
        print(f"     - Lower Z-threshold: 4.5 → 4.0")
        print(f"     - Increase swing proximity: 2 → 5 bars")
        print(f"     - Further relax R1 thresholds")
    
    print(f"\n  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
