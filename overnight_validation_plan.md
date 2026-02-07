# Overnight Validation Plan - ZThreeNoFilter Multi-Year

## Objective
Validate V4's ZThreeNoFilter strategy on V3's multi-year dataset (2019-2024) to determine if the edge is robust across different market regimes.

## What Will Run
1. **Data preparation** (if needed):
   - Check if V3's 5-min RTH-only bars exist for 2019-2024
   - If not, generate from raw data
   
2. **Strategy backtest** (2019-2024):
   - Port ZThreeNoFilter logic to V3's backtesting framework
   - Run with identical parameters:
     - Entry: Z ≥ 3.75 (EMA 21, lookback 21)
     - Exit: PT=4.0pts, SL=3.5pts, max_hold=20 bars
     - RTH-only, bar-close exits, 2-bar minimum spacing
   
3. **Analysis outputs**:
   - Annual P&L breakdown (2019-2024)
   - Monthly profit factor distribution
   - Regime analysis (bear/bull/chop performance)
   - Drawdown periods identification
   - Train/test split validation (multiple folds)
   
4. **Comparison report**:
   - V4 results (Jan-Jul 2025): PF 2.28, $3,313
   - V3 results (2019-2024): [TBD]
   - Consistency check across years
   - Regime dependency assessment

## Expected Runtime
- Data prep: 10-30 minutes
- Backtest: 1-2 hours (depending on data size)
- Analysis: 5-10 minutes
- **Total: 2-3 hours max**

## Success Criteria
✅ **GO for paper trading if:**
- PF > 1.5 across all years (2019-2024)
- At least 4/6 years profitable
- Max drawdown < $1,000 (single contract)
- Performance doesn't degrade pre-2024

⚠️ **REVIEW if:**
- PF 1.2-1.5 (marginal edge)
- 3/6 years profitable (inconsistent)
- Large drawdowns in specific regimes

❌ **NO-GO if:**
- PF < 1.2 overall
- <3/6 years profitable
- 2020 COVID crash destroys it

## Outputs
All results written to:
- `/mnt/c/ninjatrader_ml_new/wave_signals_v3/results/zthree_validation_[timestamp]/`
  - `annual_summary.csv`
  - `monthly_breakdown.csv`
  - `regime_analysis.csv`
  - `equity_curve.png`
  - `validation_report.md`

## When to Start
Run command when ready:
```bash
cd /mnt/c/ninjatrader_ml_new/wave_signals_v3
python tools/validate_zthree_multiyear.py --start-year 2019 --end-year 2024 --output results/zthree_validation
```

I'll monitor progress and deliver the report when you wake up.

---

*Status: READY (not started)*
