"""
Run Al Brooks V2 Strategy on full MNQ dataset with yearly breakdowns
"""
import pandas as pd
import numpy as np
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from al_brooks_v2_strategy import AlBrooksV2Strategy


def calculate_metrics(trades_df: pd.DataFrame) -> dict:
    if len(trades_df) == 0:
        return {'total_trades': 0}

    total = len(trades_df)
    winners = trades_df[trades_df['pnl_dollars'] > 0]
    losers = trades_df[trades_df['pnl_dollars'] <= 0]

    win_rate = len(winners) / total
    gross_profit = winners['pnl_dollars'].sum() if len(winners) > 0 else 0
    gross_loss = abs(losers['pnl_dollars'].sum()) if len(losers) > 0 else 0
    pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    avg_win = winners['pnl_dollars'].mean() if len(winners) > 0 else 0
    avg_loss = losers['pnl_dollars'].mean() if len(losers) > 0 else 0
    total_pnl = trades_df['pnl_dollars'].sum()

    # Sharpe
    daily_pnl = trades_df.groupby(pd.to_datetime(trades_df['entry_time']).dt.date)['pnl_dollars'].sum()
    sharpe = (daily_pnl.mean() / daily_pnl.std()) * np.sqrt(252) if daily_pnl.std() > 0 else 0

    # Max DD
    cum = trades_df['pnl_dollars'].cumsum()
    dd = cum - cum.expanding().max()
    max_dd = dd.min()

    # Trading days
    trading_days = pd.to_datetime(trades_df['entry_time']).dt.date.nunique()
    trades_per_day = total / trading_days if trading_days > 0 else 0

    return {
        'total_trades': total,
        'winners': len(winners),
        'losers': len(losers),
        'win_rate': round(win_rate * 100, 1),
        'profit_factor': round(pf, 2),
        'sharpe': round(sharpe, 2),
        'total_pnl': round(total_pnl, 2),
        'avg_pnl': round(total_pnl / total, 2),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'max_dd': round(max_dd, 2),
        'trading_days': trading_days,
        'trades_per_day': round(trades_per_day, 2),
    }


def print_metrics(label: str, m: dict):
    if m.get('total_trades', 0) == 0:
        print(f"  {label}: No trades")
        return
    print(f"  {label}: {m['total_trades']} trades | "
          f"WR={m['win_rate']}% | PF={m['profit_factor']} | "
          f"P&L=${m['total_pnl']:.0f} | "
          f"AvgW=${m['avg_win']:.2f} AvgL=${m['avg_loss']:.2f} | "
          f"DD=${m['max_dd']:.0f} | "
          f"{m['trades_per_day']:.2f}/day")


def main():
    workspace = Path("/home/shado/.openclaw/workspace")
    data_file = workspace / "data" / "MNQ_5min.csv"
    output_dir = workspace / "research" / "al_brooks_system" / "backtests" / "v2"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading MNQ data...")
    df = pd.read_csv(data_file)
    df['time'] = pd.to_datetime(df['time'])
    print(f"Loaded {len(df):,} bars: {df['time'].min()} to {df['time'].max()}")

    # V2 parameters
    params = {
        'tick_size': 0.25,
        'tick_value': 0.50,
        'rth_only': True,
        'rth_start': '08:30',
        'rth_end': '15:00',

        # Trend
        'trend_ema_period': 20,
        'trend_slope_threshold': 0.03,
        'trend_slope_lookback': 10,

        # S/R
        'sr_lookback': 100,
        'sr_proximity_ticks': 8,
        'sr_min_touches': 2,

        # Pattern
        'pullback_min_size': 0.3,
        'pattern_timeout': 30,
        'pattern_validity': 3,
        'ema_pullback_proximity': 1.0,

        # Signal bar
        'min_signal_quality': 40,
        'min_body_ratio': 0.3,

        # Risk
        'max_stop_atr': 1.5,
        'reward_risk_ratio': 1.5,
        'min_target_ticks': 6,
        'max_hold_bars': 40,
        'use_breakeven_trail': True,

        # Entry modes
        'with_trend_needs_sr': False,
        'counter_trend_allowed': True,
        'ema_pullback_enabled': True,

        # Circuit breakers
        'daily_loss_limit': -200,
        'max_consecutive_losses': 4,
    }

    # Run full backtest
    print("\nRunning V2 backtest on full MNQ dataset...")
    strategy = AlBrooksV2Strategy(params)
    all_trades = strategy.run_backtest(df, verbose=True)

    if len(all_trades) == 0:
        print("NO TRADES GENERATED!")
        return

    # Save all trades
    all_trades.to_csv(output_dir / "mnq_v2_all_trades.csv", index=False)

    # Overall metrics
    print("\n" + "=" * 80)
    print("OVERALL RESULTS")
    print("=" * 80)
    overall = calculate_metrics(all_trades)
    print_metrics("ALL", overall)

    # Yearly breakdown
    all_trades['year'] = pd.to_datetime(all_trades['entry_time']).dt.year
    print("\n" + "-" * 80)
    print("YEARLY BREAKDOWN")
    print("-" * 80)

    yearly_results = {}
    for year in sorted(all_trades['year'].unique()):
        year_trades = all_trades[all_trades['year'] == year]
        m = calculate_metrics(year_trades)
        yearly_results[str(year)] = m
        print_metrics(str(year), m)

    # Pattern breakdown
    print("\n" + "-" * 80)
    print("PATTERN BREAKDOWN")
    print("-" * 80)
    for pattern in all_trades['pattern'].unique():
        pt = all_trades[all_trades['pattern'] == pattern]
        m = calculate_metrics(pt)
        print_metrics(pattern, m)

    # Trend breakdown
    print("\n" + "-" * 80)
    print("TREND BREAKDOWN")
    print("-" * 80)
    for trend in all_trades['trend'].unique():
        tt = all_trades[all_trades['trend'] == trend]
        m = calculate_metrics(tt)
        print_metrics(trend, m)

    # Exit reason breakdown
    print("\n" + "-" * 80)
    print("EXIT REASON BREAKDOWN")
    print("-" * 80)
    for reason in all_trades['exit_reason'].unique():
        rt = all_trades[all_trades['exit_reason'] == reason]
        m = calculate_metrics(rt)
        print_metrics(reason, m)

    # S/R vs no S/R
    print("\n" + "-" * 80)
    print("WITH S/R vs WITHOUT S/R")
    print("-" * 80)
    sr_trades = all_trades[all_trades['key_level'] != 'NONE']
    no_sr_trades = all_trades[all_trades['key_level'] == 'NONE']
    if len(sr_trades) > 0:
        print_metrics("AT S/R", calculate_metrics(sr_trades))
    if len(no_sr_trades) > 0:
        print_metrics("NO S/R", calculate_metrics(no_sr_trades))

    # Save summary
    summary = {
        'params': {k: v for k, v in params.items()},
        'overall': overall,
        'yearly': yearly_results,
        'timestamp': datetime.now().isoformat(),
    }
    with open(output_dir / "mnq_v2_summary.json", 'w') as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\nResults saved to {output_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()
