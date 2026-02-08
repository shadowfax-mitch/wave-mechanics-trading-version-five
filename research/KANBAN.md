# V5 KANBAN - Task Tracking Board

**Last updated:** 2026-02-07 18:15 CT
**Current Phase:** Phase 2 COMPLETE — Ready for Phase 3 (Forward Testing)

---

## 📋 TODO

### Phase 3: Forward Testing
- [ ] Run Stage 7: NinjaTrader Strategy Analyzer (validate C# matches Python within 5%)
- [ ] Market Replay testing (2+ weeks, tick-perfect simulation)
- [ ] Paper trading setup & execution (2+ weeks)
- [ ] Micro-live deployment (1 contract, circuit breakers active, 2+ weeks)

---

## 🔄 IN PROGRESS

- None — awaiting next phase decision

---

## ✅ DONE

### Phase 2: Implementation & Backtesting (Feb 7)
- [x] Implement FRR strategy in Python (591 lines, `frr_strategy.py`)
- [x] Implement backtesting engine (event-driven, slippage $2, commission $1)
- [x] Build circuit breaker module (daily P&L + consecutive loss limits)
- [x] **Bug Audit #1:** Fixed 15 bugs (circuit breaker blocking exits, stop-loss price bias, MES API mismatch, stale params, etc.) — see `BUG_AUDIT_REPORT.md`
- [x] Discovered previous +$17K results were inflated by bugs; corrected backtest showed aggressive params (z=3.0) had no edge (-$15K)
- [x] **R1 regime dropped:** Fired 0.06% of bars, killed 98.8% of Z-extreme signals
- [x] **Grid search:** Tested Z-threshold x swing_proximity matrix, identified Z=3.5/prox=2 as optimal
- [x] **Locked-in config:** Z=3.5, swing_proximity=2, no R1, wave filter ON
- [x] Run Stage 2: Backtest Full Dataset — 547 trades, 59.0% WR, 3.27 PF, +$3,590, Sharpe 5.24
- [x] Run Stage 4: Test Set (OOS) — 120 trades, 64.2% WR, 4.35 PF, +$1,108, Sharpe 7.54
- [x] Run Stage 5: Validate Set (recent) — 32 trades, 68.8% WR, 3.80 PF, +$360, Sharpe 5.74
- [x] Run Stage 3: Walk-Forward Analysis — **4/4 OOS windows profitable** (PF 1.88–4.85)
- [x] Run Stage 6: Sensitivity Analysis — **6/8 params rock-solid**, 2 flagged only at -40% extreme, all stable at +-20%
- [x] Run Stage 1: Alphalens IC Analysis — **IC=0.672 (1-bar)**, 82.9% directional accuracy, 88.9% monthly consistency
- [x] Write Stage 7: NinjaTrader C# port — 589 lines, `ninjatrader/FRRStrategy.cs`, all logic matched to Python

### Phase 1: Strategy Design (Feb 6-7)
- [x] Created research infrastructure (`research/` folder structure)
- [x] Created RESEARCH_LOG.md for cumulative insights
- [x] Created SYSTEM_TEMPLATE.md for systematic analysis
- [x] **System #001 (Bridge V1)** — 2 hours deep study (best per-trade quality: $18.38)
- [x] **System #002 (Wave Signals V2)** — 2.5 hours (28 strategies, 1.02 PF, break-even)
- [x] **System #003 (Wave Signals V3)** — 2.5 hours (23,520 tests, 96.7% failed)
- [x] **System #004 (Wave Signals V4)** — 2.5 hours (Z-score approach, promising but small sample)
- [x] Staged MNQ + MES datasets (2019-2026, 6.7 years, 470K+ bars each)
- [x] Created V5 Constitution with founding principles
- [x] V5 Strategy Spec (FRR) + Validation Protocol (7 stages)
- [x] User approval + git commit (f9085b9)

---

## 🚫 BLOCKED

- None

---

## 📦 BACKLOG

### Phase 3: Forward Testing (Weeks 3-4)
- [ ] NinjaTrader Strategy Analyzer validation (run C# port, compare to Python)
- [ ] Market Replay testing (2+ weeks)
- [ ] Paper trading setup
- [ ] Paper trading execution (2+ weeks)
- [ ] Micro-live setup (1 contract + circuit breakers)
- [ ] Micro-live execution (2+ weeks)

### Phase 4: Production (If validated)
- [ ] Scale to 2-3 contracts
- [ ] Monitor performance vs backtest
- [ ] Weekly performance reviews
- [ ] Monthly regime assessment

---

## 📊 PROGRESS METRICS

**Systems Studied:** 4 / ~284
**Current Strategy:** FRR (Z=3.5, prox=2, no R1, wave filter ON)
**Validation Status:**

| Stage | Status | Result |
|-------|--------|--------|
| Stage 1: Signal Quality (Alphalens) | PASS | IC=0.672, 88.9% consistency |
| Stage 2: Backtest Train | PASS | 395 trades, 56.7% WR, 2.89 PF |
| Stage 3: Walk-Forward | PASS | 4/4 OOS windows profitable |
| Stage 4: Test Set (OOS) | PASS | 120 trades, 64.2% WR, 4.35 PF |
| Stage 5: Validate Set | PASS | 32 trades, 68.8% WR, 3.80 PF |
| Stage 6: Sensitivity | PASS | 6/8 stable, 0 fragile at +-20% |
| Stage 7: NinjaTrader | C# WRITTEN | Awaiting Strategy Analyzer run |

**Acceptance Criteria (Full Dataset):**

| Criterion | Value | Target | Status |
|-----------|-------|--------|--------|
| Total Trades | 547 | 100+ | PASS |
| Win Rate | 59.0% | 55%+ | PASS |
| Profit Factor | 3.27 | 1.5+ | PASS |
| Avg W/L Ratio | 2.22 | 1.2+ | PASS |
| Sharpe Ratio | 5.24 | > 0 | PASS |
| Max Drawdown | $210 | <= 3x AvgWin ($70) | FAIL |

**Next Milestone:** Run NinjaTrader Strategy Analyzer (Stage 7 — validate C# matches Python within 5%)

---

**Notes:**
- ONE strategy only (V5 Constitution constraint)
- R1 regime removed — too restrictive for 5-min bars (0.06% activation)
- Edge confirmed: improves OOS (train 56.7% WR → test 64.2% WR → validate 68.8% WR)
- Only failing criterion is max drawdown ($210 vs $70 threshold)
- Previous "breakthrough" results (+$17K, 2.03 PF) were artifacts of 2 bugs
