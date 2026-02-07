# System Analysis: Wave Signals V4 (NinjaTrader Path)

**Study Start:** 2026-02-07 13:30 CST  
**Source Path:** `/mnt/c/ninjatrader_ml_new/wave_signals_v4`  
**Version:** V4.0 ("The final NinjaTrader trading path - rigorous testing ground")  
**Study Duration:** IN PROGRESS (Target: 2-4 hours)

---

## 📋 System Identity

- **System Name:** Wave Signals V4 - NinjaTrader Validation & Deployment Path
- **Evolution:** Focused, practical approach after V1/V2/V3 lessons
- **Philosophy:** "Find a tradeable edge; protect capital first" (COLLABORATION_PLAYBOOK.md)
- **Approach:** Build in Python, validate rigorously, transfer to C# NinjaTrader
- **Architecture:** Sprint-based with train/test splits, collaboration between Codex + Claude

---

## 🧠 Core Philosophy - LESSONS LEARNED APPROACH

### **Dramatic Shift from V3**

**V3 Approach:**
- 11 AI agents
- 6 phases, 214 checkboxes, 902 hours
- Enterprise infrastructure
- 23,520 parameter tests
- Result: 96.7% failed, best $687

**V4 Approach:**
- **2 AI agents** (Codex builder + Claude reviewer)
- **Sprint-based** (focused experiments, not multi-month phases)
- **Locked train/test splits** (prevent lookahead bias)
- **Production-first** (build for NinjaTrader from day one)
- **Rigorous validation** (circuit breakers, regime filtering)

**Philosophy (from COLLABORATION_PLAYBOOK.md):**
> "Primary goal: find a tradeable edge; protect capital first"
> "Research in Python must be transferable to C# / NinjaTrader"
> "Prefer robustness over brilliance; test across regimes"
> "No step is 'done' without at least one review pass"

---

## 📊 Data Scope

**Available datasets:**
- **MES tick data:** 104 CSV files (2025-01-01 to 2025-07-01, 6 months)
- **MNQ tick data:** 124 CSV files (2024-03-12 to 2026-01-14, ~22 months)
- **MNQ 233-tick bars:** Pre-aggregated tick bars

**Sprint split (locked):**
- Train: 2025-01-01 to 2025-02-28 (2 months)
- Test (OOS): 2025-03-01 to 2025-03-13 (13 days)

---

## 🏗️ Strategies Developed & Results

### **Strategy 1: EMA Z-Score Mean Reversion**

**Concept:** Enter when price is 5+ standard deviations from EMA (extreme oversold/overbought)

**Parameters:**
- EMA Period: 21
- Z-Score Lookback: 21
- Entry Threshold: ±5.0 (very extreme)
- Exit Threshold: ±1.0 (revert to mean)
- Max Hold: 48 bars (4 hours on 5-min chart)
- RTH Only: 9 AM - 4 PM

**Logic:**
- Long: Z-Score < -5.0 (price 5 std devs BELOW EMA)
- Short: Z-Score > +5.0 (price 5 std devs ABOVE EMA)
- Exit: Z-Score returns to ±1.0 OR crosses zero OR 48 bars

**Performance (from README.md):**
- OOS P&L: +$1,178
- Trades: 21
- Win Rate: ~65%
- Max DD: ~$300
- Profit Factor: 3.23
- **Frequency:** ~3 trades/month (rare but high quality)

**Assessment:** PROFITABLE on small sample, conservative entry (Z=5.0 is extreme)

---

### **Strategy 2: Zone Scalper (Trend Following)**

**Concept:** Enter at Z=4.0 and ride momentum to Z=4.5 (trend-following, not mean reversion)

**Parameters:**
- Entry Threshold: 4.0
- Target Threshold: 4.5
- Stop Threshold: 2.0
- Min Z Velocity: 0.3 (momentum confirmation)
- Max Hold: 15 bars (~75 min on 5-min)
- RTH Only: 9 AM - 4 PM

**Logic:**
- Long: Z crosses ABOVE +4.0 AND velocity >= 0.3
- Short: Z crosses BELOW -4.0 AND velocity <= -0.3
- Target: Z reaches ±4.5
- Stop: Z reverts to ±2.0

**Performance (from README.md):**
- OOS P&L: +$4,966
- Trades: 8
- Win Rate: 62%
- Max DD: $1,257
- Profit Factor: 2.97

**Parameter Grid Results (87 combinations tested):**
- **100% of configurations profitable** (all 87 had positive total_pnl)
- Best: +$8,578.70 total P/L
- Train period: LOST money (40.5% WR)
- OOS period: MADE money (53.5% WR)

**⚠️ WARNING:** OOS better than train is suspicious - could indicate:
1. Lucky OOS period (trending market favored strategy)
2. Accidental optimization for OOS
3. Different market regimes (train choppy, OOS trending)

**Assessment:** PROFITABLE but small sample (8 trades), need more validation

---

### **Strategy 3: ZThreeNoFilter (Tested with Circuit Breakers)**

**Recent Validation (Feb 7, 2026):**

| Scenario | Trades | P&L | Win Rate | Assessment |
|----------|--------|-----|----------|------------|
| **Baseline** (no protection) | 334 | **-$1,539.05** | 40.7% | ❌ UNPROFITABLE |
| **Circuit Breaker** (daily/weekly limits) | 3 | **-$71.35** | 33.3% | ❌ Still losing |
| **Full Protection** (CB + regime filter) | 5 | **-$22.25** | 40.0% | ❌ Least bad |

**Circuit Breaker Settings:**
- Daily loss limit: -$80
- Weekly loss limit: -$150
- Consecutive losses: 2 trades

**Result:** Circuit breakers REDUCED losses from -$1,539 to -$22, but strategy is fundamentally unprofitable

**Implication:** Protection systems work to limit damage, but don't create edge where none exists

---

## 📈 Parameter Sweep Analysis

**Analyzed multiple parameter sweeps:**

| Sweep File | Total Tests | Profitable | % Success | Best P/L |
|------------|-------------|------------|-----------|----------|
| backtest_1s_bars | 42,082 | 13,056 | 31.0% | $129.55 |
| backtest_ofi | 3,670 | 1,333 | 36.3% | $135.80 |
| backtest_results | 3,008 | 1,274 | 42.4% | $110.80 |
| **zone_scalper_grid** | **87** | **87** | **100%** | **$8,578.70** |
| zscore_runner_grid | 144 | 6 | 4.2% | $813.20 |

**Total parameter tests:** 49,091

**Key Findings:**

1. **Zone Scalper anomaly:** 100% profitable configurations
   - Highest success rate of any V4 strategy
   - But only 87 combinations (much smaller sweep than others)
   - OOS better than train (red flag for luck vs edge)

2. **Most sweeps still majority failures:**
   - 1-second bars: 69% failed
   - OFI: 63.7% failed
   - General backtest: 57.6% failed
   - Z-score runner: 95.8% failed

3. **Best results are MUCH smaller than V3:**
   - V3 best: $687 from 23,520 tests
   - V4 best: $8,578 from 49,091 tests
   - But V4 best is from Zone Scalper (small sample, 8 trades)

---

## ⚠️ Weaknesses & Failure Modes - CRITICAL OBSERVATIONS

### **1. Small Sample Sizes Throughout**

**Mean Reversion:** 21 trades (6+ months)
- 3-4 trades/month = too rare
- Not enough data for statistical significance
- One bad month could wipe out edge

**Zone Scalper:** 8 trades (OOS period)
- 0.6 trades/month in OOS
- Extremely rare signals
- High profitability (+$4,966) on 8 trades = HIGH RISK

**Assessment:** Neither strategy has sufficient trade count for confidence

### **2. OOS Better Than Train (Zone Scalper)**

**Normal expectation:** Train >= OOS performance  
**Zone Scalper reality:**
- Train: LOST $2,898 (40.5% WR)
- OOS: MADE $7,012 (53.5% WR)

**Possible explanations:**
1. **Lucky OOS period** - market trended strongly, favored momentum
2. **Overfitting to avoid train** - parameters tuned to work in OOS (data leakage)
3. **Regime mismatch** - train choppy, OOS trending

**Without seeing market conditions in both periods, this is a RED FLAG.**

### **3. Circuit Breaker Lesson**

ZThreeNoFilter validation:
- Without protection: -$1,539 (334 trades)
- With protection: -$22 (5 trades)

**Insight:** Circuit breakers prevent catastrophic losses but don't create profitability

**Same lesson as V1/V2/V3:** You can't protect your way to profits

### **4. Most Parameter Sweeps Still Fail**

49,091 parameter tests across 5 sweeps:
- Zone Scalper: 100% success (anomaly, small sample)
- All others: 31-42% success

**Pattern consistent with V3:** Most parameter combinations lose money

### **5. Strategy Descriptions vs Validation Results**

**README.md claims:**
- Mean Reversion: +$1,178, 65% WR
- Zone Scalper: +$4,966, 62% WR

**But ZThreeNoFilter validation shows:**
- Baseline: -$1,539, 40.7% WR

**Which strategy is ZThreeNoFilter?** Unclear from documentation.

**Potential issue:** Different strategies with different results, unclear which is actually viable

### **6. Transfer to NinjaTrader Not Yet Validated**

**README.md shows C# implementations exist:**
- EmaZScoreMeanReversion.cs
- ZoneScalper.cs
- ZThreeNoFilter.cs

**But:** No evidence of Strategy Analyzer backtesting in NinjaTrader itself

**Gap:** Python backtests ≠ NinjaTrader backtests (execution logic may differ)

### **7. Tick Data Complexity**

**V4 uses tick data:**
- 104 CSV files for MES (6 months)
- 124 CSV files for MNQ (22 months)

**Challenges:**
1. Data storage (~6.7GB mentioned in docs)
2. Resampling to 1-second or 5-minute bars
3. Tick-by-tick execution complexity
4. More opportunity for bugs

**Question:** Is tick data necessary, or would bar data suffice?

---

## ✅ Salvageable Components - WHAT'S WORTH PRESERVING

### **HIGH VALUE:**

**1. EMA Z-Score Mean Reversion Strategy (Conditional)**
- Entry at Z=5.0 is conservative (rare extremes only)
- 65% WR, 3.23 PF looks good
- **BUT:** Only 21 trades (small sample)
- **Extract if:** Can validate over 100+ trades with similar results

**2. Circuit Breaker Implementation**
- Daily loss: -$80
- Weekly loss: -$150
- Consecutive losses: 2 trades
- **Proven:** Reduced losses from -$1,539 to -$22
- **Extract as:** Risk management module

**3. Train/Test Split Discipline**
- Locked dates before testing
- Prevents lookahead bias
- **Extract as:** Validation methodology

**4. Collaboration Playbook (Process)**
- Builder (Codex) + Reviewer (Claude)
- Handoff protocol
- Review checklist (bias controls, cost realism, etc.)
- **Extract as:** Development workflow template

**5. Python → C# Transfer Focus**
- Research in Python
- Production in NinjaTrader C#
- **Extract as:** Development pipeline approach

### **MEDIUM VALUE:**

**6. Zone Scalper Concept (Needs More Testing)**
- Trend-following at Z=4.0 → 4.5
- 62% WR, 2.97 PF on 8 trades
- **Test rigorously** before deployment
- OOS > Train is concerning

**7. Regime Filtering Approach**
- Identifies favorable/unfavorable conditions
- Reduces trade count to 5 (from 334)
- **Extract as:** Pre-trade filter concept

### **LOW VALUE:**

**8. Massive Parameter Sweeps (Again)**
- 49,091 tests across V4
- Consistent with V3's overfitting risk
- **Do NOT reuse** - find robust parameters, not sweep everything

**9. Tick Data Infrastructure**
- Complex, storage-heavy
- **Question:** Is it necessary vs. bar data?

---

## 💡 Key Lessons - CRITICAL INSIGHTS

### **Lesson 1: V4 Learned from V3's Mistakes**

**V3 Problems:**
- 11 agents (overhead)
- 214 checkboxes (bureaucracy)
- 902 hour estimate (unrealistic)
- 23,520 tests (overfitting)

**V4 Solutions:**
- 2 agents (Codex + Claude)
- Sprint-based (focused experiments)
- Locked train/test splits (rigorous)
- NinjaTrader-first (production focus)

**Result:** V4 is MORE practical than V3

### **Lesson 2: Small Sample Problem Persists**

**V1:** 13 trades  
**V2:** 2,006 trades (but 1.02 PF = break-even)  
**V3:** 23,520 tests (but 96.7% failed)  
**V4:** 21-334 trades depending on strategy

**Best V4 result (Zone Scalper):** 8 trades, +$4,966

**Issue:** Can't have confidence in 8-trade result, even if profitable

### **Lesson 3: Circuit Breakers Are Insurance, Not Alpha**

**Proven in V4:**
- Without CB: -$1,539 (disaster)
- With CB: -$22 (damage control)

**But:** Still lost money

**Conclusion:** Circuit breakers essential for risk management, but don't create edge

### **Lesson 4: OOS Better Than Train = Red Flag**

**Zone Scalper:**
- Train: -$2,898
- OOS: +$7,012

**This should NOT happen unless:**
1. Lucky period (not edge)
2. Data leakage (accidental optimization for OOS)
3. Regime mismatch (train/OOS different markets)

**Need:** Market regime analysis for both periods

### **Lesson 5: Parameter Sweeps Still Prevalent**

V4 tested 49,091 parameter combinations.

**Same risk as V3:** Finding needles in haystacks (overfitting)

**Better approach:** Find ONE robust strategy, not 49K variations

### **Lesson 6: Transfer to NinjaTrader Critical Step**

**V4 has C# implementations** (good!)

**But:** No evidence of Strategy Analyzer validation

**Gap:** Python backtest ≠ NinjaTrader reality
- Execution differences
- Order handling
- Slippage modeling

**Essential:** Validate in NT Strategy Analyzer before claiming profitability

### **Lesson 7: Z-Score Approach is NOVEL**

**Unlike V1/V2/V3:**
- V1/V2/V3: Wave mechanics, fractals, regimes
- V4: EMA Z-Score (statistical distance from mean)

**This is DIFFERENT,** which is valuable (not just repeating failed approaches)

**Z=5.0 entry** is conservative (rare extremes only)

### **Lesson 8: Mean Reversion Research Contradiction**

**V3 research:** "Mean reversion doesn't work on MES 5-min"

**V4:** EMA Z-Score MEAN REVERSION strategy (+$1,178, 65% WR)

**Two possibilities:**
1. Z=5.0 is SO extreme it's different from classic mean reversion (RSI/BB)
2. V3 research was wrong (or context-dependent)

**Need to reconcile this contradiction**

---

---

## 🔗 Integration Ideas - Cross-System Synthesis

### **Idea 1: V1 Architecture + V4 Z-Score Strategy**
- V1's simple modular framework
- V4's EMA Z-Score mean reversion (Z=5.0)
- **Result:** Simple system with novel strategy
- **Test:** Z-score on V1's larger sample

### **Idea 2: V4 Circuit Breakers + Any System**
- V4's proven circuit breaker module
- Apply to V1, V2, or any future strategy
- **Result:** Risk protection without complexity
- **Universal:** Works with any trading logic

### **Idea 3: V2 High-Vol Chop + V4 Validation Rigor**
- V2's validated high-vol chop strategy (86% WR in R1)
- V4's train/test discipline + circuit breakers
- **Result:** Proven strategy with rigorous validation

### **Idea 4: Zone Scalper + Extended Testing**
- V4's Zone Scalper showed best results ($8,578)
- Test over 6-12 months (not just 13 days OOS)
- Analyze train vs OOS market conditions
- **Result:** Determine if edge is real or lucky

### **Idea 5: V1 Timeframe + V4 Strategies**
- V1: 5-min bars worked (2.38 PF)
- V3: 1-sec/1-min bars failed (0% profitable)
- V4: Uses tick data → 1-sec → 5-min resampling
- **Test:** V4 strategies on 5-min bars directly (simpler)

---

## ⭐ Overall Assessment - COMPREHENSIVE

**Edge Score:** 5/10 (2 strategies show promise, but small samples)  
**Novelty Score:** 7/10 (Z-score approach is different from V1/V2/V3)  
**Robustness Score:** 4/10 (small samples, OOS > train concern)  
**Salvage Value:** 7/10 (circuit breakers, Z-score concept, process improvements)  
**Practical Focus:** 8/10 (NinjaTrader-first, sprint-based - best of all versions)  
**Validation Rigor:** 7/10 (train/test splits, circuit breaker testing)  
**Results Quality:** 4/10 (promising but unproven at scale)

### **Final Verdict:**

**STRENGTHS:**
1. ✅ **Learned from V3** - 2 agents vs 11, sprint vs phases, practical vs bureaucratic
2. ✅ **Novel approach** - Z-score strategies different from V1/V2/V3 wave mechanics
3. ✅ **Circuit breakers proven** - reduced losses from -$1,539 to -$22
4. ✅ **Train/test discipline** - locked splits prevent lookahead
5. ✅ **NinjaTrader C# implementations** - production-ready code
6. ✅ **Small parameter space** - Zone Scalper: 87 tests (not 23,520)
7. ✅ **Positive results** - Mean Reversion: +$1,178, Zone Scalper: +$4,966
8. ✅ **Collaboration playbook** - builder + reviewer process

**WEAKNESSES:**
1. ⚠️ **Tiny sample sizes** - 8-21 trades (not statistically significant)
2. ⚠️ **OOS > Train red flag** - Zone Scalper OOS +$7K vs Train -$2.9K
3. ⚠️ **ZThreeNoFilter unprofitable** - lost money in all scenarios
4. ⚠️ **Strategy identity confusion** - multiple strategies, unclear which is which
5. ⚠️ **No NT Strategy Analyzer validation** - Python backtest ≠ NinjaTrader reality
6. ⚠️ **Tick data complexity** - 6.7GB storage, resampling challenges
7. ⚠️ **Most sweeps still fail** - 49,091 tests, 31-42% success (except Zone Scalper)
8. ⚠️ **Mean reversion contradiction** - V3 said it doesn't work, V4 uses it successfully?

**CRITICAL PATTERN ACROSS ALL 4 SYSTEMS:**

| Version | Approach | Best Result | Sample Size | Status |
|---------|----------|-------------|-------------|--------|
| **V1** | Simple (8 strategies) | $18.38/trade, 2.38 PF | 13 trades | Small sample, best quality |
| **V2** | Complex (28 strategies) | $1.26/trade, 1.02 PF | 2,006 trades | Large sample, break-even |
| **V3** | Enterprise (11 agents) | $687 best, 1.05 PF | 23,520 tests | Massive testing, 96.7% failed |
| **V4** | Practical (Z-score) | $4,966 best, 2.97 PF | 8 trades | Small sample, uncertain |

**Observations:**
1. **V1 still has best per-trade quality** ($18.38 vs V2 $1.26 vs V3 $0.03 vs V4 $621/trade)
2. **V4 has best total result** ($4,966) but SMALLEST sample (8 trades)
3. **V2 has best statistical significance** (2,006 trades) but WORST profitability (1.02 PF)
4. **V3 had most testing** (23,520) but WORST results (96.7% failed)

**The Dilemma:**
- Large samples → break-even or unprofitable
- Small samples → looks good but unproven
- Massive testing → overfitting and failure

**WHAT TO PRESERVE:**
1. **Circuit breaker module** (proven risk reduction)
2. **EMA Z-Score strategy concept** (novel, different from failed approaches)
3. **Train/test split discipline** (rigorous validation)
4. **Collaboration playbook** (practical development process)
5. **NinjaTrader-first approach** (production focus)
6. **Regime filtering concept** (reduced trades from 334 to 5)

**WHAT TO TEST BEFORE ACCEPTING:**
1. **Zone Scalper over 100+ trades** (current 8 is too small)
2. **Mean Reversion over 100+ trades** (current 21 is marginal)
3. **Strategy Analyzer validation in NinjaTrader** (not just Python)
4. **Market regime analysis** (why OOS > Train? Was it luck?)
5. **Both strategies in SAME market conditions** (compare apples to apples)

**WHAT TO DISCARD:**
1. **ZThreeNoFilter** (unprofitable in all scenarios)
2. **Most parameter sweep results** (49,091 tests, overfitting risk)
3. **Tick data complexity** (if bar data suffices)
4. **Strategies with <50 trades** (insufficient confidence)

**PRIORITY FOR V5:** **MEDIUM-HIGH**

V4 has PROMISING strategies (Z-score approach is novel), PRACTICAL process (learned from V3), and PROVEN risk management (circuit breakers).

BUT samples are TOO SMALL to declare victory.

**RECOMMENDATION FOR V5:**

**Phase 1: Validate V4's Best Strategies (Weeks 1-4)**
1. Test EMA Z-Score Mean Reversion over 6-12 months (target 100+ trades)
2. Test Zone Scalper over 6-12 months (target 100+ trades)
3. Analyze market regimes during train vs OOS (explain the discrepancy)
4. Validate in NinjaTrader Strategy Analyzer (not just Python)

**Phase 2: If Validation Passes (Weeks 5-8)**
1. Integrate circuit breakers into C# strategies
2. Add regime filtering
3. Paper trade for 4 weeks
4. Compare paper vs backtest

**Phase 3: If Paper Trading Passes (Weeks 9-12)**
1. Micro-live with 1 contract
2. $3K account
3. Target $30-60/week
4. Track execution quality

**IF VALIDATION FAILS:**
- Fall back to V1's approach
- V1 + signal spam fix + circuit breakers
- Test over 100+ trades
- V1's simple approach may be the answer

---

**CROSS-SYSTEM INSIGHT:**

After studying all 4 systems:
1. **V1's simplicity had better per-trade quality** than all others
2. **Complexity did NOT create profitability** (V2/V3 worse than V1)
3. **Small samples look good, large samples reveal truth** (V4 vs V2)
4. **Novel approaches are valuable** (V4's Z-score vs repeated wave mechanics)
5. **Risk management is essential** (circuit breakers work)

**V5 should be:**
- **Simple** (like V1, not complex like V2/V3)
- **Novel** (like V4's Z-score, not repeated failures)
- **Validated** (100+ trades minimum, like V2's sample size)
- **Protected** (circuit breakers, like V4)
- **Practical** (NinjaTrader-ready, like V4)

---

*Study completed: 2026-02-07 14:45 CST*  
**Total study time:** ~2.5 hours (foundation docs, strategy analysis, parameter sweeps, lessons synthesis)

**Next:** Prepare phased plan for V5 based on insights from all 4 systems.

