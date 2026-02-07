# MEMORY.md - Long-Term Memory

*Last updated: 2026-02-07*

---

## 🧠 Core Context

**Human:** Mitch  
**Location:** Trussville, Alabama, US (Central Time)  
**Role:** Quantitative trader, algorithmic trading system developer  
**Markets:** Futures (MES, MNQ)  
**Approach:** Probability-based regime assessment, not prediction

---

## 🛠️ Technical Stack

- **Primary:** Python (trading systems, ML models, analysis)
- **Secondary:** C# (NinjaTrader 8 strategy integration)
- **Platform:** NinjaTrader 8
- **System:** Wave Signals Trading System (modular architecture)
- **Environment:** Windows 10, WSL2/Ubuntu available
- **AI Partner:** Claude (Anthropic) - primary assistant

---

## 📅 Key Events

### 2026-02-07 - Initial Setup
- **Identity established:** Sentinel (trading operations AI)
- **Memory system initialized:** MEMORY.md + daily logs
- **Model configuration:** Claude Sonnet 4.5 (default), Gemini available but unstable
- **Security audit:** Clean (0 critical, local-only setup)
- **Timezone:** America/Chicago (CT)

### 2026-02-07 - V5 Constitution Approved
- **Data staged:** MNQ + MES 5-min bars (2019-2026, 6.7 years, 470K+ bars each)
- **V5 Constitution created:** Founding principles locked (research/V5_CONSTITUTION.md)
- **Core constraints:** ONE strategy, simplicity first, 100+ trades validation, novel approaches only
- **Proposed strategy:** Fractal Regime Reversion (V1 fractals + V2 high-vol chop + V4 Z-score extremes)
- **Target:** $100/week profit, PF≥1.5, WR≥55%
- **Git commit:** f9085b9 (root commit with constitution + datasets)
- **Status:** APPROVED - Ready for Phase 1 (Strategy Design)

---

## 🎯 Trading System Components

**Wave Signals Trading System:**
- Wave mechanics analysis (amplitude, frequency, energy)
- Fractal geometry detection (swing points, divergence)
- Regime classification (multi-timeframe market structure)
- ML models (signal generation, trade management)
- NinjaTrader bridge (Python-to-C# file-based communication)
- Risk management (daily P&L limits, drawdown protection)

**Current Focus Areas:**
- Structure-aware position sizing
- Regime-aware risk management
- Comprehensive analysis tools
- Parameter tuning workflows
- Modular code architecture transition

---

## 💡 Lessons Learned

### Trading Strategy Development (CRITICAL)
- **2026-02-07 MISSION PIVOT:** Abandoned quick-fix approach (Range Extreme V3)
- **New approach:** Systematic study of ALL 284+ strategies from 10 months research
- **Commitment:** Go SLOW, be meticulous, one system at a time (2-4 hours each)
- **Goal:** Extract edge → Build regime-switching ensemble → Novel pattern recognition
- **Mitch's frustration:** Tried all standard indicator approaches (VWAP, BB, RSI, ADX, ATR) - they don't work
- **His strength:** Tenacity - never gives up
- **His expectation:** Novel approaches using AI's pattern recognition, not indicator cocktails
- **Infrastructure:** Research folder created (`~/.openclaw/workspace/research/`)
- **Workflow:** Study systems → Extract components → Test combinations overnight → Morning discoveries
- **Philosophy:** "Go slow to go fast. Build understanding that leads to genuine edge."

### System #001: Bridge V1 - Key Learnings (2026-02-07)
- **First serious system** - Wave Signals Trading System (Python + NinjaTrader bridge)
- **Novel approach confirmed:** Wave mechanics + fractal geometry (NOT indicator cocktails)
- **Profitable but tiny sample:** $238.94 over 13 trades (69% WR, 2.38 PF) - needs validation
- **Long bias strong:** 80% WR vs 62.5% shorts - asymmetry worth investigating
- **Signal spam issue:** 133 signals → 13 trades (10:1 ratio) - needs fixing
- **Salvageable components:** Swing Points (fractals), Regime Classifier, Wave Direction, Trade Management
- **Critical dependency:** System relies on regime classification accuracy (unvalidated)
- **Two-layer wave filtering:** May be over-filtering (strategy + trigger both apply wave penalties)
- **Configuration complexity:** 1500+ lines, 100+ parameters - need sensitivity analysis
- **Next:** Study more systems to find patterns and complementary approaches

### 🎯 V5 MISSION STATEMENT (2026-02-07) **LOCKED IN**

**After 9.5 hours of research across V1/V2/V3/V4, Mitch committed to:**

**GOAL:** $100/week profit ($5-6K/year) - achievable and realistic

**CONSTRAINTS ACCEPTED:**
1. ✅ **ONE strategy only** (no multi-strategy complexity)
2. ✅ **Any timeframe** (5-min, 10-min, 15-min, 2000-tick - whatever works)
3. ✅ **Any instrument** (MES, MNQ, whatever proves profitable)
4. ✅ **Patient if progress shown** (will wait for 100+ trades validation)
5. ✅ **Simple if it works** (no complexity for complexity's sake)
6. ✅ **ANY means to success** (evidence-driven, not theory-driven)

**CRITICAL LESSONS FROM V1-V4:**
- **V1's simplicity had best per-trade quality** ($18.38/trade, 2.38 PF)
- **Scalping doesn't work** (V3: 0% on 1-min, V4: Zone Scalper failed 10-week live test)
- **Complexity decreases profitability** (V2: 1.02 PF, V3: 96.7% failed)
- **Small samples deceive** (V4: +$4,966 backtest → failed live)
- **Large samples reveal truth** (V2: 2,006 trades = break-even)
- **Must validate 100+ trades minimum** before deployment

**V5 APPROACH:**
- Start with ONE simple strategy
- Test rigorously (100+ trades over 6-12 months)
- NinjaTrader Strategy Analyzer validation
- Paper trade 4+ weeks
- Micro-live only if validated
- Resist complexity creep (discipline required)

**FOUNDING PRINCIPLE:** Evidence > Theory. Data decides. Simplicity first.

---

### System #004: Wave Signals V4 - Key Learnings (2026-02-07) **PROMISING BUT UNPROVEN**
- **Practical pivot** - Learned from V3 (2 agents vs 11, sprint-based vs phases, NinjaTrader-first)
- **Novel Z-score approach** - EMA Z-Score mean reversion (different from V1/V2/V3 wave mechanics)
- **Two strategies with positive results:**
  1. Mean Reversion (Z=5.0): +$1,178 over 21 trades (65% WR, 3.23 PF)
  2. Zone Scalper (Z=4.0→4.5): +$4,966 over 8 trades (62% WR, 2.97 PF)
- **Circuit breakers validated:** Reduced losses from -$1,539 (334 trades) to -$22 (5 trades)
- **RED FLAGS:**
  - Sample sizes TOO SMALL (8-21 trades, not statistically significant)
  - Zone Scalper OOS > Train (OOS +$7K, Train -$2.9K) - luck vs edge?
  - ZThreeNoFilter unprofitable in all scenarios
  - No NinjaTrader Strategy Analyzer validation yet
- **Major lessons:**
  1. V4 learned from V3's mistakes (practical vs bureaucratic)
  2. Z-score approach is NOVEL (not just repeating failures)
  3. Circuit breakers prevent disasters but don't create edge
  4. Small samples look promising but need 100+ trades for confidence
  5. Mean reversion works at Z=5.0 extremes? (contradicts V3 research)
  6. Parameter sweeps still prevalent (49,091 tests, 31-100% success rates)
- **Recommendation for V5:** Validate V4's Z-score strategies over 100+ trades before deployment
- **Salvageable:** Circuit breakers, Z-score concept, train/test discipline, NinjaTrader C# code
- **Need:** Extended testing to prove edge is real, not lucky

### System #003: Wave Signals V3 - Key Learnings (2026-02-07) **PARADOX**
- **Enterprise-grade attempt** - 11 AI agents, 6 phases, 214 checkboxes, 902 estimated hours
- **CRITICAL FINDING: Professional Infrastructure ≠ Profitability**
  - Most sophisticated system (event-driven backtesting, alphalens, walk-forward analysis)
  - 23,520 parameter combinations tested
  - **96.7% of tests FAILED** (22,749 lost money, 771 profitable)
  - Best result: $687 profit, 1.05 PF (barely viable)
  - Scalping (1-min bars): **100% failure** (all 1,440 tests lost money)
- **Research findings:**
  - Mean reversion doesn't work (RSI/BB/Z-score IC ≈ 0) - CONFIRMED
  - Time patterns don't work (hour/day/session) - CONFIRMED
  - Selected factors ALL have negative IC (fade, don't follow) - CONTRARIAN INSIGHT
  - Opening Range had massive lookahead bias (-0.40 → -0.02 after fix)
- **Major lessons:**
  1. **V1 STILL has best per-trade quality** ($18.38 vs V2 $1.26 vs V3 $687 across thousands of tests)
  2. **As complexity increased, profitability DECREASED** (V1→V2→V3 trend)
  3. Process can validate edge but can't create it
  4. Curve-fitting at scale (1 in 34 combos profitable = overfitting)
  5. Scalping doesn't work for retail (transaction costs dominate)
  6. Fade classic indicators (breakouts, EMA crosses have negative IC)
  7. Agent system is management overhead (overkill for solo trader)
- **Salvageable:** Validation methodology (alphalens, walk-forward), backtesting architecture, negative knowledge
- **DISCARD:** All 23K parameter combinations, agent orchestration, scalping strategies

### System #002: Wave Signals V2 - Key Learnings (2026-02-07) **CRITICAL LESSON**
- **Major redesign attempt** - Complete V1 overhaul with formal governance (Constitution/Doctrine)
- **CRITICAL FINDING: Sophistication ≠ Profitability**
  - V1 (simple): 8 strategies → 2.38 PF, $18.38/trade
  - V2 (complex): 28 strategies + Bayesian/HMM/entropy → **1.02 PF**, $1.26/trade
  - **Despite MASSIVE sophistication, V2 barely profitable over 2,006 trades (statistically significant FAILURE)**
- **One validated winner:** High-vol chop reversion (86% WR in R1 regime) - edge from regime itself, not complexity
- **Major lessons:**
  1. More strategies ≠ better results (28 vs 8 = WORSE performance)
  2. Governance ≠ execution (wrote great principles, violated them by adding too much)
  3. Individual strategy edge ≠ ensemble edge (good strategies diluted by poor ones)
  4. Small edge ($1.26/trade) won't survive real costs (commissions + slippage)
  5. Huge drawdown ($8,403) for tiny profit ($2,537) = 3.3:1 ratio (unacceptable)
  6. Development time has diminishing returns (50+ sessions for break-even system)
  7. **V1's simplicity may have been undervalued** - simpler approach had better per-trade quality
- **Hypothesis:** V1 + signal spam fix + longer validation might OUTPERFORM V2
- **Salvageable:** Constitution/Doctrine framework, high-vol chop strategy, MTF structure
- **DISCARD:** 26 of 28 strategies, Bayesian/HMM complexity, multi-layer filtering

### OpenClaw Operations
- **Model stability:** Gemini Pro can hang during responses (45+ sec, multiple cycles). Claude Sonnet 4.5 is stable.
- **Model switching:** Use `/status model=<alias>` for instant switching (sonnet/gemini/flash)
- **Log access:** Use `openclaw logs` not `--tail` or `-n` flags

---

## 📝 Communication Preferences

- Direct, concise, no filler language
- Lead with conclusion, then supporting detail
- Use numbers and specifics over vague qualifiers
- Format data as tables or key-value pairs when appropriate
- Scannable messages (mobile-friendly)
- Use emoji signals: ⚠️ warnings, 🔴 critical, 🟢 all-clear, 📊 data

---

## ⏰ Operating Hours

**Market Hours (CT):**
- Pre-market: 7:00 - 8:30 AM
- Regular Trading Hours (RTH): 8:30 AM - 3:00 PM (cash session)
- Extended/Futures: Nearly 24h Sun-Fri (Mitch primarily trades RTH)

**Key Events:** FOMC, NFP (first Friday monthly), CPI releases

---

## 🔐 Security Context

- **Workspace:** `/home/shado/.openclaw/workspace`
- **Config:** `~/.openclaw/openclaw.json`
- **Gateway:** Local-only (loopback), systemd service running
- **Channels:** Telegram enabled (allowlist: 8242807772)

---

*This file is your curated long-term memory. Review and update periodically from daily logs (`memory/YYYY-MM-DD.md`).*
