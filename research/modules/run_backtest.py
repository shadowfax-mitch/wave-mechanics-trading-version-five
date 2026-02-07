"""
FRR Strategy Backtest Runner
Executes full validation pipeline
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
from frr_strategy import FRRStrategy


def load_data(file_path: str) -> pd.DataFrame:
    """Load OHLCV data from CSV"""
    df = pd.read_csv(file_path, parse_dates=['time'], index_col='time')
    return df


def split_data(df: pd.DataFrame) -> tuple:
    """
    Split data into train/test/validate sets (60/20/20)
    
    Returns:
        train_df, test_df, validate_df
    """
    # Date ranges from V5_VALIDATION_PROTOCOL.md
    train_start = '2019-05-01'
    train_end = '2023-12-31'
    
    test_start = '2024-01-01'
    test_end = '2025-06-30'
    
    validate_start = '2025-07-01'
    validate_end = '2026-01-12'
    
    train_df = df.loc[train_start:train_end]
    test_df = df.loc[test_start:test_end]
    validate_df = df.loc[validate_start:validate_end]
    
    return train_df, test_df, validate_df


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
    print(f"  [{'✓' if results['total_trades'] >= 100 else '✗'}] 100+ trades: {results['total_trades']}")
    print(f"  [{'✓' if results['win_rate'] >= 55 else '✗'}] WR ≥ 55%: {results['win_rate']:.1f}%")
    print(f"  [{'✓' if results['profit_factor'] >= 1.5 else '✗'}] PF ≥ 1.5: {results['profit_factor']:.2f}")
    print(f"  [{'✓' if results['avg_win_loss_ratio'] >= 1.2 else '✗'}] Avg W/L ≥ 1.2: {results['avg_win_loss_ratio']:.2f}")
    
    avg_win = abs(results['avg_win'])
    max_dd_check = results['max_drawdown'] <= (3 * avg_win) if avg_win > 0 else False
    print(f"  [{'✓' if max_dd_check else '✗'}] Max DD ≤ 3× Avg Win: ${results['max_drawdown']:.2f} vs ${3*avg_win:.2f}")
    
    # Overall verdict
    passed = (
        results['total_trades'] >= 100 and
        results['win_rate'] >= 55 and
        results['profit_factor'] >= 1.5 and
        results['avg_win_loss_ratio'] >= 1.2 and
        max_dd_check
    )
    
    print(f"\n{'🎉 PASS' if passed else '❌ FAIL'}: {set_name} set {'meets' if passed else 'does not meet'} acceptance criteria")
    
    return passed


def save_results(results: dict, output_path: str):
    """Save results to JSON (excluding DataFrame)"""
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
    }
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"  📁 Results saved to: {output_path}")


def main():
    """Run full backtest pipeline"""
    print(f"\n{'='*60}")
    print(f"  FRR STRATEGY BACKTEST - PHASE 2")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # Load data
    print(f"\n📂 Loading data...")
    data_path = Path.home() / '.openclaw' / 'workspace' / 'data' / 'MNQ_5min.csv'
    df = load_data(str(data_path))
    print(f"  ✓ Loaded {len(df):,} bars from {df.index[0]} to {df.index[-1]}")
    
    # Split data
    print(f"\n✂️  Splitting data...")
    train_df, test_df, validate_df = split_data(df)
    print(f"  ✓ Train:    {len(train_df):,} bars ({train_df.index[0]} to {train_df.index[-1]})")
    print(f"  ✓ Test:     {len(test_df):,} bars ({test_df.index[0]} to {test_df.index[-1]})")
    print(f"  ✓ Validate: {len(validate_df):,} bars ({validate_df.index[0]} to {validate_df.index[-1]})")
    
    # Initialize strategy
    print(f"\n🎯 Initializing FRR strategy...")
    strategy = FRRStrategy()
    print(f"  ✓ Parameters: {strategy.params}")
    
    # Run train set backtest
    print(f"\n🔬 STAGE 2: BACKTEST TRAIN SET")
    print(f"  Running backtest on training data...")
    train_results = strategy.backtest(train_df, slippage=2.0, commission=1.0)
    train_passed = print_results(train_results, "TRAIN")
    
    # Save train results
    output_dir = Path.home() / '.openclaw' / 'workspace' / 'research' / 'analysis'
    output_dir.mkdir(exist_ok=True)
    save_results(train_results, str(output_dir / 'train_results.json'))
    
    # If train fails, stop here
    if not train_passed:
        print(f"\n❌ TRAIN SET FAILED - Stopping validation pipeline")
        print(f"   Strategy does not meet acceptance criteria on training data")
        print(f"   Review results and iterate strategy design")
        return
    
    # Run test set backtest
    print(f"\n🔬 STAGE 4: BACKTEST TEST SET (OOS)")
    print(f"  Running backtest on test data (untouched during development)...")
    strategy.reset_state()
    test_results = strategy.backtest(test_df, slippage=2.0, commission=1.0)
    test_passed = print_results(test_results, "TEST")
    save_results(test_results, str(output_dir / 'test_results.json'))
    
    # Check OOS performance (≥80% of IS)
    if train_results['total_trades'] > 0:
        oos_ratio = test_results['total_pnl'] / train_results['total_pnl'] if train_results['total_pnl'] > 0 else 0
        print(f"\n📊 OOS PERFORMANCE CHECK")
        print(f"  Test P&L / Train P&L: {oos_ratio:.2%}")
        print(f"  [{'✓' if oos_ratio >= 0.80 else '✗'}] OOS ≥ 80% of IS: {'PASS' if oos_ratio >= 0.80 else 'FAIL'}")
    
    # Run validate set backtest
    print(f"\n🔬 STAGE 5: BACKTEST VALIDATE SET (RECENT)")
    print(f"  Running backtest on validation data (most recent)...")
    strategy.reset_state()
    validate_results = strategy.backtest(validate_df, slippage=2.0, commission=1.0)
    validate_passed = print_results(validate_results, "VALIDATE")
    save_results(validate_results, str(output_dir / 'validate_results.json'))
    
    # Summary
    print(f"\n{'='*60}")
    print(f"  BACKTEST SUMMARY")
    print(f"{'='*60}")
    print(f"  Train Set:    {'✅ PASS' if train_passed else '❌ FAIL'}")
    print(f"  Test Set:     {'✅ PASS' if test_passed else '❌ FAIL'}")
    print(f"  Validate Set: {'✅ PASS' if validate_passed else '❌ FAIL'}")
    
    overall_pass = train_passed and test_passed and (validate_results['total_pnl'] > 0)
    print(f"\n  {'🎉 OVERALL: PASS' if overall_pass else '❌ OVERALL: FAIL'}")
    
    if overall_pass:
        print(f"\n  ✅ Strategy meets validation criteria")
        print(f"  ✅ Ready for Stage 3 (Walk-Forward Analysis)")
        print(f"  ✅ Ready for Stage 6 (Sensitivity Analysis)")
        print(f"  ✅ Ready for Stage 7 (NinjaTrader Validation)")
    else:
        print(f"\n  ❌ Strategy does not meet validation criteria")
        print(f"  ⚠️  Review results and iterate design")
    
    print(f"\n  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
