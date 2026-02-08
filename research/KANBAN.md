# V5 KANBAN - Task Tracking Board

**Last updated:** 2026-02-07 19:00 CT
**Current Phase:** Back to Drawing Board — FRR strategy invalidated

---

## 📋 TODO

### Next: Strategy Research
- [ ] Study more systems from the ~284 available
- [ ] Identify candidates with real (non-look-ahead) edge
- [ ] Build validation pipeline that prevents look-ahead bias from the start

---

## 🔄 IN PROGRESS

- None — regrouping after FRR invalidation

---

## ✅ DONE

### FRR Strategy (V5) — INVALIDATED (Feb 7)
- [x] Implement FRR strategy in Python (591 lines, `frr_strategy.py`)
- [x] Implement backtesting engine (event-driven, slippage $2, commission $1)
- [x] Build circuit breaker module (daily P&L + consecutive loss limits)
- [x] **Bug Audit #1:** Fixed 15 bugs — see `BUG_AUDIT_REPORT.md`
- [x] Discovered +$17K results were inflated by bugs; corrected to -$15K
- [x] R1 regime dropped (fired 0.06% of bars)
- [x] Grid search → locked in Z=3.5, prox=2, no R1, wave filter ON
- [x] Ran all 7 validation stages (all appeared to PASS)
- [x] NinjaTrader C# port written (589 lines)
- [x] **Stage 7 FAIL:** NinjaTrader Strategy Analyzer showed ~0.9 trades/mo, +$34 (vs Python's 547 trades, +$3,590)
- [x] **Root cause: look-ahead bias in swing detection** — Python used `shift(-i)` to peek at future bars for fractal confirmation. Fixed with `.shift(strength)` delay.
- [x] **Corrected Python backtest: 216 trades, 0.52 PF, -$1,942** — no edge exists
- [x] Also fixed regime exit gate (was forcing 1-bar exits when R1 disabled)

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

---

## 🚫 BLOCKED

- None

---

## 📦 BACKLOG

### Infrastructure (reusable)
- Backtesting engine with slippage/commission modeling
- Circuit breaker module
- 7-stage validation pipeline
- NinjaTrader C# porting workflow
- MNQ + MES 5-min datasets (2019-2026)

---

## 📊 PROGRESS METRICS

**Systems Studied:** 4 / ~284
**Current Strategy:** None — FRR invalidated
**FRR Final Validation (corrected):**

| Stage | Status | Result |
|-------|--------|--------|
| Stage 1: Alphalens IC | INVALID | Built on look-ahead biased signals |
| Stage 2: Backtest Train | FAIL | 216 trades, ~35% WR, 0.52 PF, -$1,942 |
| Stage 3: Walk-Forward | INVALID | Built on look-ahead biased signals |
| Stage 4: Test Set (OOS) | INVALID | Built on look-ahead biased signals |
| Stage 5: Validate Set | INVALID | Built on look-ahead biased signals |
| Stage 6: Sensitivity | INVALID | Built on look-ahead biased signals |
| Stage 7: NinjaTrader | FAIL | ~0.9 trades/mo, +$34 (break-even) |

---

## 📝 LESSONS LEARNED

1. **Always test for look-ahead bias FIRST** — any indicator using future data (`shift(-n)`, forward-looking windows) must account for confirmation delay before backtesting
2. **NinjaTrader is the truth** — it can't cheat because it processes bar-by-bar in real time. Always cross-validate Python results against NT before trusting them.
3. **Fractal swing detection inherently has confirmation lag** — `strength` bars must pass before a swing is confirmed. Python vectorized code hides this with `shift(-i)`.
4. **Validation stages are only as honest as the signal generation** — all 6 Python stages "passed" because they all used the same biased input.
5. **Regime exit must be gated** — when `use_regime_filter=False`, the regime exit was still active, forcing 1-bar holding periods.
