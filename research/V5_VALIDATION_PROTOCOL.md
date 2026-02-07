# V5 VALIDATION PROTOCOL

**Created:** 2026-02-07 12:35 CT  
**Purpose:** Professional validation without V3's complexity bloat  
**Status:** DESIGN PHASE

---

## 🎯 VALIDATION PHILOSOPHY

**From V5 Constitution:**
- "Process can validate edge but can't create it" (V3 lesson)
- "100+ trades minimum" (statistical significance)
- "Evidence over theory" (data decides)

**Anti-Patterns to Avoid:**
- ❌ 11 AI agents (V3 overkill)
- ❌ 214 checkboxes (V3 bureaucracy)
- ❌ 23,520 parameter tests (V3 overfitting)

**What We Keep:**
- ✅ Alphalens IC analysis (signal quality validation)
- ✅ Walk-forward analysis (prevents curve-fitting)
- ✅ Train/test/validate splits (OOS validation)
- ✅ Circuit breakers (risk management)

---

## 📊 VALIDATION PIPELINE

### Stage 1: Signal Quality (Alphalens) - 30 min
**Purpose:** Validate signal quality BEFORE backtesting

**Process:**
1. Calculate all entry signals (LONG/SHORT) over full dataset
2. Label forward returns (1-bar, 5-bar, 10-bar, 20-bar)
3. Compute Information Coefficient (IC) per timeframe
4. Analyze IC distribution and consistency

**Acceptance Criteria:**
- IC > 0.05 (any forward return period)
- IC consistency > 50% (% of periods with positive IC)
- No lookahead bias detected (future data leaking)

**Output:**
- Alphalens tearsheet (IC, quantile analysis, turnover)
- Signal quality report (pass/fail)

**If FAIL:** Strategy hypothesis rejected, return to design phase.

---

### Stage 2: Backtesting (Train Set) - 1-2 hours
**Purpose:** Validate strategy over historical data

**Data Split:**
- **Train:** 2019-05-01 to 2023-12-31 (4.7 years, ~60%)
- **Test:** 2024-01-01 to 2025-06-30 (1.5 years, ~20%)
- **Validate:** 2025-07-01 to 2026-01-12 (0.6 years, ~20%)

**Backtesting Engine:**
- Event-driven (bar-by-bar processing, no lookahead)
- Slippage: $2 per contract per trade (realistic for MNQ/MES)
- Commission: $0.50 per contract per side ($1.00 round-trip)
- Execution: Market orders (no limit order assumptions)

**Metrics to Track:**
- Total Trades
- Win Rate (%)
- Profit Factor (Gross Profit / Gross Loss)
- Avg Win / Avg Loss ratio
- Max Drawdown ($)
- Sharpe Ratio
- Total P&L ($)

**Acceptance Criteria (Train Set):**
- Trades ≥ 100 (statistical significance)
- Win Rate ≥ 55%
- Profit Factor ≥ 1.5
- Avg Win ≥ Avg Loss × 1.2
- Max DD ≤ 3× Avg Win

**If FAIL:** Iterate strategy parameters (within ±20% ranges) OR pivot strategy.

---

### Stage 3: Walk-Forward Analysis - 2-3 hours
**Purpose:** Prevent curve-fitting, validate adaptability

**Process:**
1. **Expanding Window Approach:**
   - Period 1: Train on 2019-2021 (2 years), test on 2022 (1 year)
   - Period 2: Train on 2019-2022 (3 years), test on 2023 (1 year)
   - Period 3: Train on 2019-2023 (4 years), test on 2024 (1 year)
   - Period 4: Train on 2019-2024 (5 years), test on 2025-2026 (1 year)

2. **Fixed Parameters:**
   - Use SAME parameters across all periods (no re-optimization)
   - Validate parameter stability

3. **Regime Analysis:**
   - Classify each test period regime (bull/bear/chop)
   - Validate performance across different regimes

**Acceptance Criteria:**
- OOS performance ≥ 80% of IS performance (each period)
- Profitable in ≥3 out of 4 test periods
- No single period accounts for >60% of total profit (no single regime dependency)

**If FAIL:** Strategy overfit to specific regime or period. Reject hypothesis.

---

### Stage 4: Test Set Validation - 30 min
**Purpose:** Final OOS validation before forward testing

**Data:** 2024-01-01 to 2025-06-30 (1.5 years, untouched during development)

**Process:**
1. Run backtest with LOCKED parameters (no changes allowed)
2. Compare metrics to train set
3. Validate acceptance criteria still met

**Acceptance Criteria:**
- All Stage 2 criteria still met
- Performance ≥ 80% of train set
- No anomalies or unexpected behavior

**If FAIL:** Strategy does not generalize. Major red flag.

---

### Stage 5: Validate Set (Final Check) - 30 min
**Purpose:** Most recent data validation

**Data:** 2025-07-01 to 2026-01-12 (0.6 years, most recent market conditions)

**Process:**
1. Run backtest with LOCKED parameters
2. Validate performance in current regime
3. Check for regime drift or degradation

**Acceptance Criteria:**
- Profitable (positive P&L)
- Win rate ≥ 50% (slightly lower bar for small sample)
- No catastrophic losses (circuit breakers functional)

**If FAIL:** Strategy may not work in current market. Reevaluate.

---

### Stage 6: Sensitivity Analysis - 1-2 hours
**Purpose:** Validate parameter robustness (V5 Constitution requirement)

**Process:**
1. For each parameter, vary by ±10% and ±20%
2. Re-run backtest on train set
3. Measure performance degradation

**Parameters to Test:**
- `regime_window`: 15, 18, 20, 22, 25, 30
- `amp_threshold`: 1.2, 1.35, 1.5, 1.65, 1.8, 2.0
- `z_threshold`: 4.0, 4.5, 5.0, 5.5, 6.0
- `ema_period`: 30, 40, 50, 60, 80, 100
- `max_hold_bars`: 10, 15, 20, 25, 30

**Acceptance Criteria:**
- ±20% parameter change should NOT:
  - Turn profitable strategy unprofitable
  - Reduce profit factor below 1.3
  - Reduce win rate below 50%

**If FAIL:** Strategy is fragile (overfit to specific parameters). Redesign needed.

---

### Stage 7: NinjaTrader Strategy Analyzer - 1 hour
**Purpose:** Validate in production platform (mandatory per V5 Constitution)

**Process:**
1. Convert Python strategy to NinjaTrader C#
2. Run Strategy Analyzer on MNQ/MES historical data
3. Verify results match Python backtest (within 5% tolerance)

**Acceptance Criteria:**
- Results consistent with Python backtest
- No C# implementation bugs
- Performance metrics align

**If FAIL:** Implementation error or platform-specific issue. Debug and fix.

---

## 📋 CIRCUIT BREAKER VALIDATION

**Purpose:** Prove V4's circuit breakers work as expected

**Test Scenarios:**
1. **Daily Loss Limit:**
   - Simulate day with 5 consecutive losses
   - Verify trading stops at -$200 limit
   
2. **Consecutive Loss Limit:**
   - Simulate 3 consecutive losses
   - Verify trading pauses for rest of session
   
3. **Max Position:**
   - Verify only 1 contract traded at a time
   - No double entries

**Acceptance:** All circuit breakers trigger correctly, no exceptions.

---

## 📊 REPORTING STANDARDS

### Backtest Report Template
```markdown
# FRR Backtest Report - [Train/Test/Validate]

**Period:** YYYY-MM-DD to YYYY-MM-DD  
**Bars:** [count]  
**Parameters:** [list]

## Performance Metrics
- Total Trades: [count]
- Win Rate: [%]
- Profit Factor: [ratio]
- Avg Win / Avg Loss: [ratio]
- Max Drawdown: $[amount]
- Sharpe Ratio: [ratio]
- Total P&L: $[amount]

## Trade Distribution
- Long Trades: [count] ([win rate]%)
- Short Trades: [count] ([win rate]%)
- Avg Hold Time: [bars]

## Regime Analysis
- R1 Occurrences: [%] of bars
- Trades in R1: [%]
- Win Rate in R1: [%]

## Monthly P&L
[table of monthly results]

## Top 5 Wins / Losses
[table]

## Acceptance Criteria Status
- [x] / [ ] 100+ trades
- [x] / [ ] WR ≥ 55%
- [x] / [ ] PF ≥ 1.5
- [x] / [ ] Avg Win/Loss ≥ 1.2
- [x] / [ ] Max DD ≤ 3× Avg Win

**VERDICT:** PASS / FAIL
```

---

## 🚨 FAILURE PROTOCOLS

### If Signal Quality Fails (Alphalens IC < 0.05)
**Action:** Hypothesis rejected, return to strategy design
**Options:**
1. Modify entry conditions (different Z-threshold, regime, etc.)
2. Pivot to different V5 candidate strategy
3. Return to system research (study more systems)

### If Backtest Fails (< 100 trades OR PF < 1.5)
**Action:** Parameter tuning within documented ranges
**Constraints:**
- Only adjust parameters within ±20% of base values
- No more than 3 tuning iterations
- If still fails after 3 iterations → hypothesis rejected

### If Walk-Forward Fails (OOS < 80% IS)
**Action:** Overfitting detected, strategy rejected
**Options:**
1. Simplify strategy (remove filters)
2. Increase parameter constraints
3. Pivot to different strategy

### If Sensitivity Analysis Fails
**Action:** Strategy too fragile, redesign required
**Options:**
1. Reduce number of parameters
2. Use more robust indicators/metrics
3. Simplify entry/exit logic

---

## ✅ VALIDATION CHECKLIST

### Phase 1: Pre-Backtest
- [ ] Alphalens setup complete
- [ ] IC analysis run and documented
- [ ] Signal quality validated (IC > 0.05)

### Phase 2: Backtest Validation
- [ ] Train set: 100+ trades, PF ≥ 1.5
- [ ] Test set: OOS ≥ 80% of IS
- [ ] Validate set: Positive P&L
- [ ] Walk-forward: 3/4 periods profitable

### Phase 3: Robustness
- [ ] Sensitivity analysis: ±20% parameters stable
- [ ] Circuit breakers: All scenarios tested
- [ ] NinjaTrader: Results match Python

### Phase 4: Ready for Forward Testing
- [ ] All acceptance criteria met
- [ ] Documentation complete
- [ ] Git committed with full report

---

## 📅 ESTIMATED TIMELINE

| Stage | Duration | Cumulative |
|-------|----------|------------|
| 1. Signal Quality (Alphalens) | 30 min | 0.5h |
| 2. Backtest (Train) | 1-2h | 2.5h |
| 3. Walk-Forward | 2-3h | 5.5h |
| 4. Test Set | 30 min | 6h |
| 5. Validate Set | 30 min | 6.5h |
| 6. Sensitivity | 1-2h | 8.5h |
| 7. NinjaTrader | 1h | 9.5h |

**Total Estimated Time:** 9-10 hours (Phase 2 complete)

---

## 🎯 SUCCESS DEFINITION

**Validation is complete when:**
1. ✅ Alphalens IC > 0.05 (signal quality proven)
2. ✅ Train set: 100+ trades, PF ≥ 1.5, WR ≥ 55%
3. ✅ Walk-forward: OOS ≥ 80% of IS across 4 periods
4. ✅ Test set: Metrics maintained (untouched during dev)
5. ✅ Validate set: Positive P&L in recent data
6. ✅ Sensitivity: Robust to ±20% parameter changes
7. ✅ NinjaTrader: Results match Python implementation
8. ✅ Circuit breakers: All safety nets functional

**If ALL checkboxes pass → Proceed to Phase 3 (Forward Testing)**

**If ANY checkbox fails → Iterate or pivot per failure protocols**

---

**Status:** PROTOCOL DEFINED - Ready for implementation
