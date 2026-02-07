"""
Parameter Sensitivity Analysis for FRR Strategy

Tests each parameter at multiple levels to validate edge robustness.
If the edge is real, small parameter changes shouldn't destroy profitability.
"""
import pandas as pd
import numpy as np
from frr_strategy import FRRStrategy
import json
from datetime import datetime

def run_sensitivity_test(df: pd.DataFrame, 
                         param_name: str, 
                         base_value: float,
                         test_levels: list = [-0.4, -0.2, 0, 0.2, 0.4]) -> pd.DataFrame:
    """
    Test a single parameter at multiple levels
    
    Args:
        df: Price data
        param_name: Parameter to vary
        base_value: Baseline value
        test_levels: Multipliers to test (e.g., -0.2 = 20% decrease)
    
    Returns:
        DataFrame with results for each level
    """
    results = []
    
    for level in test_levels:
        # Calculate test value
        if param_name in ['swing_lookback', 'swing_proximity', 'ema_period', 'atr_period', 'max_hold_bars']:
            # Integer parameters - round to nearest int
            test_value = max(1, int(base_value * (1 + level)))
        else:
            # Float parameters
            test_value = base_value * (1 + level)
        
        # Special handling for thresholds that can't be negative
        if param_name in ['amp_threshold', 'chop_threshold', 'z_threshold', 'stop_atr_mult']:
            test_value = max(0.1, test_value)
        
        print(f"  Testing {param_name} = {test_value:.2f} ({level:+.0%} from baseline {base_value})")
        
        # Build params dict with test value
        params = {}
        if param_name == 'z_threshold':
            params['z_threshold'] = test_value
        elif param_name == 'swing_lookback':
            params['swing_strength'] = test_value
        elif param_name == 'swing_proximity':
            params['swing_proximity'] = test_value
        elif param_name == 'amp_threshold':
            params['amp_threshold'] = test_value
        elif param_name == 'chop_threshold':
            params['chop_threshold'] = test_value
        elif param_name == 'ema_period':
            params['ema_period'] = test_value
        elif param_name == 'atr_period':
            params['atr_period'] = test_value
        elif param_name == 'stop_atr_mult':
            params['stop_atr_mult'] = test_value
        elif param_name == 'max_hold_bars':
            params['max_hold_bars'] = test_value
        elif param_name == 'max_daily_loss':
            params['daily_loss_limit'] = -abs(test_value)
        
        # Run backtest
        strategy = FRRStrategy(params=params)
        backtest_results = strategy.backtest(df)
        
        # Extract metrics
        per_trade = backtest_results['total_pnl'] / backtest_results['total_trades'] if backtest_results['total_trades'] > 0 else 0
        
        results.append({
            'parameter': param_name,
            'level': f"{level:+.0%}",
            'value': test_value,
            'total_trades': backtest_results['total_trades'],
            'total_pnl': backtest_results['total_pnl'],
            'per_trade': per_trade,
            'win_rate': backtest_results['win_rate'],
            'profit_factor': backtest_results['profit_factor'],
            'max_drawdown': backtest_results['max_drawdown'],
            'avg_win': backtest_results['avg_win'],
            'avg_loss': backtest_results['avg_loss']
        })
    
    return pd.DataFrame(results)

def run_full_sensitivity_analysis(df: pd.DataFrame) -> dict:
    """
    Run sensitivity analysis on all parameters
    
    Returns:
        Dictionary with results for each parameter
    """
    # Baseline parameters (locked-in: Z=3.5, prox=2, no R1)
    baseline_params = {
        'z_threshold': 3.5,
        'swing_lookback': 2,
        'swing_proximity': 2,
        'ema_period': 50,
        'atr_period': 14,
        'stop_atr_mult': 1.0,
        'max_hold_bars': 20,
        'max_daily_loss': 200
    }
    
    all_results = {}
    
    print("="*60)
    print("PARAMETER SENSITIVITY ANALYSIS")
    print("="*60)
    print(f"Testing {len(baseline_params)} parameters at 5 levels each")
    print(f"Data: {len(df):,} bars ({df.index[0]} to {df.index[-1]})")
    print("="*60)
    
    for i, (param_name, base_value) in enumerate(baseline_params.items(), 1):
        print(f"\n[{i}/{len(baseline_params)}] Testing {param_name} (baseline: {base_value})")
        
        results_df = run_sensitivity_test(df, param_name, base_value)
        all_results[param_name] = results_df
        
        # Quick summary
        baseline_pf = results_df[results_df['level'] == '+0%']['profit_factor'].iloc[0]
        min_pf = results_df['profit_factor'].min()
        max_pf = results_df['profit_factor'].max()
        
        print(f"  → PF range: {min_pf:.2f} to {max_pf:.2f} (baseline: {baseline_pf:.2f})")
        
        # Flag if any test drops below 1.5 PF
        if min_pf < 1.5:
            print(f"  ⚠️  WARNING: PF drops below 1.5 threshold at some levels!")
    
    return all_results

def analyze_stability(results: dict) -> pd.DataFrame:
    """
    Analyze which parameters are most stable/sensitive
    
    Returns:
        Summary DataFrame with stability metrics
    """
    stability_summary = []
    
    for param_name, results_df in results.items():
        baseline_row = results_df[results_df['level'] == '+0%'].iloc[0]
        
        # Calculate ranges and variability
        pf_range = results_df['profit_factor'].max() - results_df['profit_factor'].min()
        pf_std = results_df['profit_factor'].std()
        
        # Check if any level fails threshold
        fails_threshold = (results_df['profit_factor'] < 1.5).any()
        
        # Trade count stability
        trade_range = results_df['total_trades'].max() - results_df['total_trades'].min()
        
        stability_summary.append({
            'parameter': param_name,
            'baseline_pf': baseline_row['profit_factor'],
            'pf_range': pf_range,
            'pf_std': pf_std,
            'fails_threshold': fails_threshold,
            'baseline_trades': baseline_row['total_trades'],
            'trade_range': trade_range,
            'baseline_per_trade': baseline_row['per_trade']
        })
    
    stability_df = pd.DataFrame(stability_summary)
    stability_df = stability_df.sort_values('pf_std', ascending=False)
    
    return stability_df

def main():
    """Run full sensitivity analysis"""
    from pathlib import Path

    # Load MNQ data
    print("\nLoading MNQ data...")
    data_path = Path.home() / '.openclaw' / 'workspace' / 'data' / 'MNQ_5min.csv'
    df = pd.read_csv(data_path, parse_dates=['time'], index_col='time')
    print(f"Loaded {len(df):,} bars\n")
    
    # Run sensitivity analysis
    results = run_full_sensitivity_analysis(df)
    
    # Analyze stability
    print("\n" + "="*60)
    print("STABILITY ANALYSIS")
    print("="*60)
    stability_df = analyze_stability(results)
    print(stability_df.to_string(index=False))
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save individual parameter results
    output_dir = Path.home() / '.openclaw' / 'workspace' / 'research' / 'analysis'
    output_dir.mkdir(exist_ok=True)
    for param_name, results_df in results.items():
        results_df.to_csv(output_dir / f'sensitivity_{param_name}.csv', index=False)

    # Save stability summary
    stability_df.to_csv(output_dir / 'sensitivity_summary.csv', index=False)

    # Save as JSON for programmatic access
    results_dict = {param: df.to_dict('records') for param, df in results.items()}
    with open(output_dir / 'sensitivity_full_results.json', 'w') as f:
        json.dump({
            'timestamp': timestamp,
            'data_bars': len(df),
            'parameter_results': results_dict,
            'stability_summary': stability_df.to_dict('records')
        }, f, indent=2, default=str)
    
    print("\n" + "="*60)
    print("CRITICAL FINDINGS")
    print("="*60)
    
    # Flag fragile parameters
    fragile = stability_df[stability_df['fails_threshold'] == True]
    if len(fragile) > 0:
        print("⚠️  FRAGILE PARAMETERS (drop below 1.5 PF):")
        for _, row in fragile.iterrows():
            print(f"  - {row['parameter']}: PF range {row['pf_range']:.2f}")
    else:
        print("✅ NO FRAGILE PARAMETERS - edge appears robust!")
    
    # Flag highly sensitive parameters
    high_variance = stability_df[stability_df['pf_std'] > 0.3]
    if len(high_variance) > 0:
        print("\n📊 HIGH VARIANCE PARAMETERS:")
        for _, row in high_variance.iterrows():
            print(f"  - {row['parameter']}: std={row['pf_std']:.2f}")
    
    print(f"\nResults saved to: {output_dir}/sensitivity_*.csv")
    print("="*60)

if __name__ == '__main__':
    main()
