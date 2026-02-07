# V5 CONSTITUTION - Founding Principles

**Created:** 2026-02-07  
**Mission:** $100/week profit ($5-6K/year) with ONE simple, validated strategy

---

## 🔒 IMMUTABLE CONSTRAINTS

These constraints are **LOCKED**. They cannot be violated without explicit user approval.

### 1. ONE Strategy Only
- Single approach, not ensemble
- No "backup strategies" or "fallback modes"
- If it doesn't work, we iterate or pivot — we don't add more strategies

### 2. Simplicity First
- **V1 had best per-trade quality ($18.38) with 8 strategies**
- **V2 had worst per-trade quality ($1.26) with 28 strategies**
- **V3 had enterprise infrastructure and worst results (96.7% failed)**
- Complexity decreases profitability. Simplicity is a feature, not a limitation.

### 3. Validation Before Deployment
- **100+ trades minimum** before considering live deployment
- Train/test/validate splits (60/20/20 or similar)
- Walk-forward analysis (V3's best methodology)
- Out-of-sample validation across regime changes
- Strategy Analyzer → Market Replay → Paper → Micro-live

### 4. Novel Approaches Only
- No VWAP, BB, RSI, ADX, ATR indicator cocktails
- These have been tried for 10 months — they don't work
- Focus on structural patterns: wave mechanics, fractals, regimes, entropy, volatility asymmetries

### 5. Evidence Over Theory
- Data decides, not opinions
- If backtests fail, strategy fails
- No "it should work because..." reasoning
- Small samples (8-21 trades) are not evidence

---

## 📊 LESSONS FROM V1-V4

### What Worked
| Component | Source | Why It Matters |
|-----------|--------|----------------|
| Swing Points (fractals) | V1 | Structural anchors, not indicators |
| Regime Classification | V1 | Context-aware trading |
| High-vol chop reversion (R1) | V2 | 86% WR in specific regime |
| Circuit breakers | V4 | Reduced losses 98.6% (-$1,539 → -$22) |
| Z-score extremes (Z≥5.0) | V4 | Novel, not rehashed wave mechanics |
| Walk-forward validation | V3 | Prevents curve-fitting |
| Alphalens IC analysis | V3 | Validates signal quality before trading |

### What Failed
| Anti-Pattern | Evidence | Lesson |
|--------------|----------|--------|
| More strategies → better | V2 (28 strategies) = 1.02 PF vs V1 (8 strategies) = 2.38 PF | Addition decreases edge |
| Enterprise infrastructure → profits | V3 (11 agents, 6 phases) = 96.7% failure rate | Process can't create edge |
| Small samples are evidence | V4 (8-21 trades) look great but unproven | Need 100+ trades for confidence |
| Scalping works for retail | V3 (1-min bars): 0% profitable across 1,440 tests | Transaction costs dominate |
| Mean reversion works | V3 (RSI/BB/Z-score IC ≈ 0) | Classic indicators don't work |
| Parameter optimization finds edge | V3 (23,520 tests, 96.7% failed) | Curve-fitting at scale |

---

## 🎯 V5 STRATEGIC APPROACH

### Phase 1: Strategy Design (Week 1)
**Goal:** ONE simple strategy with novel edge hypothesis

**Candidate Approaches** (choose ONE):
1. **Fractal Regime Reversion** - V1's fractals + V2's high-vol chop + V4's Z-score
2. **Volatility Asymmetry** - Implied vs realized volatility spread (user suggested)
3. **Entropy-Based** - Market uncertainty as edge signal (user suggested)
4. **Wave Direction + Circuit Breakers** - V1's wave mechanics + V4's risk management

**Selection Criteria:**
- Novel (not indicator cocktails)
- Falsifiable (can be proven wrong)
- Simple (≤5 core components)
- Testable (works with OHLCV + volume data)

### Phase 2: Validation Infrastructure (Week 1)
**Goal:** Professional validation without complexity bloat

**Tools:**
- Alphalens (IC analysis, factor validation) - from V3
- Walk-forward analysis (expanding window) - from V3
- Train/test/validate splits (60/20/20) - from V4
- Circuit breakers (daily loss limits) - from V4
- NinjaTrader Strategy Analyzer - mandatory

**Anti-Patterns to Avoid:**
- 11 AI agents (V3 overkill)
- 214 checkboxes (V3 bureaucracy)
- Parameter sweeps (23,520 tests = overfitting)

### Phase 3: Backtesting (Week 2)
**Goal:** 100+ trades with positive expectancy

**Acceptance Criteria:**
- Profit Factor ≥ 1.5 (V1: 2.38, V2: 1.02, V3: 1.05, V4: 2.97-3.23)
- Win Rate ≥ 55% (threshold for sustainability)
- Avg Win ≥ Avg Loss × 1.2 (risk/reward balance)
- Max Drawdown ≤ 3× Avg Win (recoverable)
- **100+ trades** (statistical significance)
- Information Coefficient > 0.05 (alphalens validation)
- OOS performance ≥ 80% of IS performance (no curve-fitting)

**If criteria not met:** Iterate or pivot. Do NOT add more strategies.

### Phase 4: Forward Testing (Weeks 3-4)
**Goal:** Validate on unseen data

1. Strategy Analyzer (NinjaTrader) - full historical validation
2. Market Replay - simulated live conditions
3. Paper trading - 2+ weeks minimum
4. Micro-live (1 contract) - 2+ weeks, daily loss limits

**Circuit Breakers** (mandatory):
- Daily loss limit: -$200 (20 avg trades × $10 risk)
- Max position: 1 contract (micro-live)
- Kill switch: 3 consecutive losing days

---

## 🧪 HYPOTHESIS-DRIVEN DEVELOPMENT

### V5 Core Hypothesis
**"Market structure at fractal extremes (Z≥5.0) in high-volatility regimes (R1) creates mean-reversion edge when filtered by wave direction."**

**Why This Might Work:**
- Combines V1's best components (fractals, regime, waves)
- Adds V4's novel Z-score extremes (not just wave mechanics)
- Targets V2's validated R1 high-vol chop (86% WR)
- Filtered by V4's circuit breakers (98.6% loss reduction)

**Falsification Criteria:**
- If IC < 0.05 (no signal quality) → hypothesis fails
- If PF < 1.5 over 100+ trades → hypothesis fails
- If OOS < 80% of IS performance → hypothesis fails

**If hypothesis fails:** We pivot, we don't patch. ONE strategy rule stands.

---

## 📏 RULES OF ENGAGEMENT

### Code Discipline
1. Modular architecture (separate signal, risk, execution)
2. Type hints + docstrings (mandatory)
3. Unit tests for core logic
4. Git commits at each milestone
5. NO premature optimization

### Parameter Discipline
1. **≤10 parameters total** (V1 had ~20, V3 had 100+)
2. Each parameter must have theoretical justification
3. Sensitivity analysis (±20% should not break strategy)
4. No "magic numbers" without documented rationale

### Development Discipline
1. Write code AFTER validation plan
2. Backtest BEFORE optimization
3. Validate BEFORE paper trading
4. Paper trade BEFORE live
5. Micro-live BEFORE scaling

---

## 🚫 ANTI-PATTERNS (DO NOT REPEAT)

### From V1
- ❌ Signal spam (133 signals → 13 trades, 10:1 ratio)
- ❌ Small sample hubris (13 trades is not validation)

### From V2
- ❌ Strategy creep (8 → 28 strategies decreased profitability)
- ❌ Governance theater (great principles, poor execution)

### From V3
- ❌ Complexity worship (11 agents ≠ better results)
- ❌ Parameter mining (23,520 tests = overfitting)
- ❌ Scalping delusion (0% profitable on 1-min bars)

### From V4
- ❌ Small sample deception (8-21 trades look promising but unproven)
- ❌ OOS > Train red flag (luck vs edge)

---

## 🎯 SUCCESS CRITERIA

### Minimum Viable Strategy (MVP)
- $100/week profit target ($5-6K/year)
- Validated over 100+ trades
- PF ≥ 1.5, WR ≥ 55%
- Max DD ≤ 3× Avg Win
- OOS ≥ 80% of IS performance

### Path to Production
1. ✅ Alphalens IC > 0.05 (signal quality)
2. ✅ Backtest 100+ trades, PF ≥ 1.5
3. ✅ Walk-forward validation (no curve-fitting)
4. ✅ Strategy Analyzer confirmation
5. ✅ Market Replay (2+ weeks)
6. ✅ Paper trading (2+ weeks)
7. ✅ Micro-live (2+ weeks, circuit breakers)
8. ✅ Scale to 2-3 contracts (if consistent)

**All checkboxes must pass. No shortcuts.**

---

## 💡 UNCONVENTIONAL APPROACHES (USER REQUESTED)

Mitch is open to:
- Quantum theory analogies (uncertainty principles)
- Entropy-based signals (market disorder)
- Heisenberg uncertainty (measurement affects outcome)
- Implied vs realized volatility spreads
- Fractal geometry (already in V1, worth revisiting)

**Constraint:** Must still be testable with OHLCV data. No untestable theories.

---

## 🔐 FOUNDING COMMITMENT

**This document locks in the approach.** Any changes require:
1. Explicit user approval
2. Documented rationale in RESEARCH_LOG.md
3. Updated commit in git

**Signed:** Sentinel (AI Operations Partner)  
**Date:** 2026-02-07  
**Status:** ACTIVE - Awaiting user approval to proceed

---

**Next Step:** User reviews and approves/modifies this constitution, then we design V5 strategy.
