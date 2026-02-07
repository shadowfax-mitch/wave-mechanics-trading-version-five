# V5 STRATEGY PROPOSAL - The ONE Strategy

**Date:** 2026-02-07  
**Version:** 1.0  
**Status:** PROPOSED (pending Mitch approval)

---

## SELECTION RATIONALE

**After studying V1-V4 (9.5 hours, 4 systems), the data says:**

| System | Approach | Per-Trade Profit | Sample Size | Status |
|--------|----------|------------------|-------------|--------|
| **V1** | Simple (8 strategies) | **$18.38/trade** | 13 trades | **BEST quality, small sample** |
| V2 | Complex (28 strategies) | $1.26/trade | 2,006 trades | Large sample, break-even |
| V3 | Enterprise (scalping) | $0.03/test avg | 23,520 tests | 96.7% failed |
| V4 | Z-score (scalping) | $621/trade | 8 trades | Failed 10-week live test |

**V1 had best per-trade quality but was never validated at scale (only 13 trades).**

**V5's mission: Validate V1's approach over 100+ trades.**

---

## THE ONE STRATEGY: V1 SIMPLIFIED

### **Core Concept**

**V1 used:** Wave mechanics + fractal geometry (swing points)

**V5 will use:** **Swing Point Pullback** (simplest profitable pattern from V1)

**Why this specific strategy:**
1. V1's longs had 80% win rate, 3.47 PF (very strong)
2. Swing points (fractals) are objective structure (not lagging indicators)
3. Pullback logic is simple and explainable
4. Already has NinjaTrader implementation foundation (from V1)

---

## STRATEGY SPECIFICATION

### **Entry Logic**

**LONG Entry:**
1. Identify swing low (trough) using 5-bar lookback
2. Price must be in uptrend (higher highs, higher lows on higher timeframe)
3. Wait for pullback to swing low support
4. Enter when price bounces off support (confirmation bar)
5. Swing low must be "fresh" (within last 10 bars)

**SHORT Entry:**
1. Identify swing high (peak) using 5-bar lookback
2. Price must be in downtrend (lower highs, lower lows on higher timeframe)
3. Wait for pullback to swing high resistance
4. Enter when price rejects resistance (confirmation bar)
5. Swing high must be "fresh" (within last 10 bars)

### **Exit Logic**

**Profit Target:**
- 3x ATR from entry (dynamic based on volatility)
- Example: ATR=2.0 points → target = 6.0 points

**Stop Loss:**
- 2x ATR from entry
- Example: ATR=2.0 points → stop = 4.0 points
- Risk:Reward = 1:1.5 minimum

**Time-Based Exit:**
- Max hold time: 48 bars (4 hours on 5-min chart)
- If target/stop not hit, exit at end of session (3:45 PM)

### **Filters**

**Session Filter:**
- Trade only 9:00 AM - 3:45 PM CT (RTH)
- No overnight positions

**Cooldown Filter:**
- Minimum 10 bars between trades (50 minutes on 5-min)
- Prevents overtrading (lesson from V1's signal spam)

**Regime Filter (Optional for Phase 2):**
- Initially: trade all conditions
- If unprofitable: add trending vs ranging filter
- Keep it SIMPLE

---

## PARAMETERS (Fixed, Not Optimized)

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Timeframe** | 5-minute bars | V1's timeframe, proven better than scalping |
| **Swing Lookback** | 5 bars | Standard fractal definition |
| **ATR Period** | 14 bars | Industry standard |
| **Target** | 3x ATR | Reasonable profit objective |
| **Stop** | 2x ATR | Reasonable risk management |
| **Max Hold** | 48 bars | 4 hours max (avoid overnight) |
| **Cooldown** | 10 bars | Prevent overtrading |
| **Session** | 9:00-15:45 CT | Regular trading hours only |

**NO PARAMETER OPTIMIZATION.** These are fixed.

---

## EXPECTED PERFORMANCE

**Based on V1's results:**
- Trades per month: 10-15
- Win rate: 60-70% (conservative estimate)
- Profit factor: 2.0+ (target)
- Average trade: $10-20 (after costs)
- Monthly profit: $100-300
- Weekly average: $25-75

**If we can achieve V1's quality ($18.38/trade) over 100+ trades:**
- 100 trades × $18.38 = $1,838 profit
- Over 6-12 months
- Annualized: $3,000-4,000 (achievable $100/week goal)

---

## IMPLEMENTATION PLAN

### **Week 1: Python Implementation**
- Code the strategy in Python
- Use V1's swing point detection as foundation
- Add simple pullback logic
- Include transaction costs ($2 commission, $2.50 slippage)

### **Week 2: Historical Backtest**
- Test on 12 months MNQ 5-minute data
- Target: 100+ trades
- Generate backtest report with all metrics

### **Week 3: Walk-Forward Analysis**
- Split into 3 periods: Train (7 mo), Test (2.5 mo), Validate (2.5 mo)
- Verify consistency across periods

### **Week 4: C# NinjaTrader Implementation**
- Port to NinjaScript strategy
- Match Python logic exactly
- Include circuit breakers

### **Week 5: Strategy Analyzer Validation**
- Run in NinjaTrader Strategy Analyzer
- Compare to Python results
- Debug any discrepancies

### **Week 6: Paper Trading Setup**
- Deploy to NinjaTrader simulation
- Begin 4-week paper trading period

### **Weeks 7-10: Paper Trading**
- Monitor daily
- Compare to backtest expectations
- Track any execution issues

### **Decision Point (Week 10):**
- If paper trading successful → Proceed to live
- If paper trading fails → Diagnose and fix

### **Weeks 11-22: Micro-Live (1 contract)**
- $3K account
- Circuit breakers active
- Weekly reviews
- Target: $100/week average

---

## ALTERNATIVE STRATEGY (If V1 Fails)

**Only if V1 pullback fails 100+ trade validation:**

**Backup Option: V4 EMA Z-Score Mean Reversion**
- Entry at Z=5.0 (extreme oversold/overbought)
- V4 showed +$1,178 over 21 trades
- More conservative than V1 (fewer trades)
- But NOT tested at scale yet

**Test V4 Z-score ONLY IF:**
1. V1 pullback fails Phase 1 (100+ backtest trades unprofitable)
2. OR V1 fails Phase 4 (paper trading)

**Do NOT test both simultaneously.** One strategy at a time.

---

## WHY THIS WILL WORK (When V2/V3/V4 Didn't)

**1. Simplicity**
- ONE strategy (not 8, not 28)
- Fixed parameters (not optimized)
- Explainable logic (not black box)

**2. V1's Proven Quality**
- $18.38/trade (best of all systems)
- 80% WR on longs (strong directional edge)
- 5-min timeframe worked (scalping didn't)

**3. Rigorous Validation**
- 100+ trades before deployment
- Walk-forward analysis
- NT Strategy Analyzer validation
- 4 weeks paper trading
- 12 weeks micro-live

**4. Realistic Expectations**
- $100/week goal (not $1,000/day dreams)
- 1 contract only (prove it first)
- Patience (100+ trades takes time)

**5. Circuit Breakers**
- Proven to work (V4: -$1,539 → -$22)
- Automatic protection
- Prevents catastrophic losses

---

## SUCCESS METRICS

**Phase 1 (Backtest) Success:**
- 100+ trades over 6-12 months
- Profit factor > 2.0
- Net profit > $500 after costs

**Phase 4 (Paper) Success:**
- 4 weeks averaging $100/week
- Execution quality acceptable
- No system reliability issues

**Phase 5 (Live) Success:**
- 12 weeks profitable
- Average $100/week
- Max drawdown < $800

**If ALL phases pass: V5 is VALIDATED and can scale.**

---

## RISKS & MITIGATION

**Risk 1: V1's 13-trade sample was lucky**
- *Mitigation:* 100+ trade validation will reveal truth

**Risk 2: Market conditions changed since V1**
- *Mitigation:* Walk-forward analysis tests recent data

**Risk 3: Python ≠ NinjaTrader execution**
- *Mitigation:* Strategy Analyzer validation before live

**Risk 4: Paper trading ≠ live trading**
- *Mitigation:* Micro-live with 1 contract, circuit breakers

**Risk 5: Strategy stops working after deployment**
- *Mitigation:* Weekly reviews, emergency stop protocol

---

## APPROVAL REQUIRED

**Mitch, do you approve this as V5's ONE strategy?**

**If yes:**
- I'll start Week 1 (Python implementation)
- We follow V5_VALIDATION_PROTOCOL.md strictly
- No additions/changes without Constitutional review

**If no:**
- Tell me what concerns you
- We'll adjust the proposal
- Or you propose an alternative strategy

**Either way: ONE strategy. Simple. Validated rigorously.**

---

**Next Steps (If Approved):**
1. I'll code the Python backtest
2. You provide 12 months MNQ 5-minute bar data
3. We run Phase 1 validation
4. Report results back with recommendation

**Timeline to live trading: 10-12 weeks if all validations pass.**

---

*"Start simple. Prove it works. Then and only then, deploy."*

**Awaiting your approval to proceed...**
