# FRR Strategy Codebase — Bug Audit Report

**Date:** 2026-02-07
**Auditor:** Claude (Opus 4.6)
**Scope:** All 11 Python modules in `research/modules/` (2,182 lines)
**Commit:** 5f687a4 (V5 MAJOR BREAKTHROUGH)
**Status:** ALL 15 BUGS FIXED

---

## Executive Summary

A comprehensive audit of the FRR strategy codebase identified **15 bugs** across the core strategy engine, backtest runners, sensitivity analysis, and diagnostic scripts. Three are critical (including one script that will crash on execution and a circuit breaker flaw that allows unprotected losing positions), six are moderate (including a stop-loss exit price bias that makes backtest results look better than reality), and six are minor inconsistencies.

| Severity | Count |
|----------|-------|
| Critical | 3     |
| Moderate | 6     |
| Minor    | 6     |

---

## Critical Bugs

### BUG-01: `run_backtest_mes.py` — Three API mismatches, script will crash

**File:** `modules/run_backtest_mes.py`
**Lines:** 23, 26, 67

The MES validation script references an API that doesn't match `FRRStrategy.backtest()`:

| Line | Code | Problem |
|------|------|---------|
| 23 | `strategy.backtest(df, print_trades=False)` | `backtest()` has no `print_trades` parameter; only accepts `slippage` and `commission` |
| 26 | `results['summary']` | `backtest()` returns metrics at top level, not nested under `'summary'` — raises `KeyError` |
| 67 | `results['signals_df']` | Key is `'signals'`, not `'signals_df'` — raises `KeyError` |

**Impact:** Script is non-functional. MES cross-validation cannot run.

---

### BUG-02: `frr_strategy.py` — Circuit breaker blocks exit logic on open positions

**File:** `modules/frr_strategy.py`
**Lines:** 356–411

```python
# Circuit breaker check
if self.daily_pnl <= self.params['daily_loss_limit']:
    continue  # <-- skips EVERYTHING below, including exit logic
if self.consecutive_losses >= self.params['max_consecutive_losses']:
    continue  # <-- same

# Exit logic (if in position)  ← UNREACHABLE when circuit breaker fires
if self.in_position:
    ...
```

When the daily loss limit or consecutive loss limit is hit, `continue` skips **both entry and exit logic**. If a position is already open when the circuit breaker trips, it cannot be exited (no stop loss, no target, no time exit, no regime exit) until the next trading day when the circuit breaker resets.

**Impact:** Open positions are held without stop-loss protection for the remainder of the trading day. In real trading, this could cause unbounded intraday losses. In backtesting, this likely distorts P&L calculations and drawdown figures.

**Fix:** Move exit logic **above** the circuit breaker check, or make the circuit breaker only gate entry logic.

---

### BUG-03: `frr_strategy.py` — Return type annotation is incorrect

**File:** `modules/frr_strategy.py`
**Line:** 169

```python
def calculate_zscore(self, df: pd.DataFrame, period: int) -> pd.Series:
    ...
    return zscore, ema  # Actually returns Tuple[pd.Series, pd.Series]
```

The signature promises `pd.Series` but returns a tuple. Callers already unpack it correctly (`signals['zscore'], signals['ema'] = self.calculate_zscore(...)`), so this doesn't cause a runtime error, but it violates the declared contract and will mislead type checkers, IDEs, and developers.

**Impact:** Low runtime risk, high maintainability risk.

---

## Moderate Bugs

### BUG-04: `sensitivity_analysis.py` — Baseline parameters don't match actual strategy

**File:** `modules/sensitivity_analysis.py`
**Lines:** 100–111

| Parameter | Sensitivity Analysis | Actual (`FRRStrategy`) |
|-----------|---------------------|------------------------|
| `swing_lookback` | 5 | N/A — parameter is called `swing_strength`, value is 2 |
| All others | Match | Match |

The sensitivity analysis tests `swing_lookback=5` but the strategy uses `swing_strength=2`. When the test overrides via `FRRStrategy(params={'swing_strength': test_value})`, the test values are derived from baseline 5, not the actual baseline 2. Sensitivity results for this parameter are invalid.

**Impact:** Any sensitivity conclusions about swing strength are based on wrong baselines.

---

### BUG-05: `sensitivity_analysis.py` — Relative file paths, will fail from wrong directory

**File:** `modules/sensitivity_analysis.py`
**Lines:** 184, 204–211

```python
# Data loading — relative path
df = pd.read_csv('data/MNQ_5min.csv', ...)

# Output — relative paths
results_df.to_csv(f'research/analysis/sensitivity_{param_name}.csv', ...)
stability_df.to_csv('research/analysis/sensitivity_summary.csv', ...)
```

Every other script uses `Path.home() / '.openclaw' / 'workspace' / 'data' / 'MNQ_5min.csv'`. This script will fail unless executed from the exact workspace root directory.

**Impact:** Script portability broken. Will raise `FileNotFoundError` in most execution contexts.

---

### BUG-06: `sensitivity_analysis.py` — Column rename creates inconsistency

**File:** `modules/sensitivity_analysis.py`
**Lines:** 185–186

```python
df.rename(columns={'time': 'timestamp'}, inplace=True)
df.set_index('timestamp', inplace=True)
```

All other scripts use `parse_dates=['time'], index_col='time'`. This rename is unnecessary and inconsistent. While the strategy uses `current_bar.name.date()` (which works on any datetime index), this is a maintenance hazard.

---

### BUG-07: `frr_strategy.py` — Stop-loss exit price bias (backtest looks better than reality)

**File:** `modules/frr_strategy.py`
**Lines:** 368–390

| Exit Type | Condition | Exit Price Used | Actual Fill Would Be | Bias |
|-----------|-----------|-----------------|---------------------|------|
| TARGET (long) | `close >= ema` | `ema` | `close` (higher) | **Understates** wins |
| STOP (long) | `close <= stop_level` | `stop_level` | `close` (lower) | **Overstates** stop exits (losses look smaller) |
| TARGET (short) | `close <= ema` | `ema` | `close` (lower) | **Understates** wins |
| STOP (short) | `close >= stop_level` | `stop_level` | `close` (higher) | **Overstates** stop exits (losses look smaller) |

The stop-loss bias is the dangerous one: if price gaps through your stop, the backtest records the stop level as the fill price rather than the (worse) actual close. This systematically makes losses look smaller than they would be in live trading.

**Impact:** Reported P&L, win/loss ratio, and drawdown figures are optimistically biased. The actual edge may be narrower than reported.

---

### BUG-08: `frr_strategy.py` — Profit factor returns 0 when all trades win

**File:** `modules/frr_strategy.py`
**Line:** 547

```python
profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
```

If every trade is a winner, `gross_loss == 0` and profit factor reports 0.0. Semantically, a strategy with zero losses has infinite profit factor. Returning 0 could cause downstream logic (acceptance criteria checks) to incorrectly flag the strategy as failing.

---

### BUG-09: `frr_strategy.py` — `bars_since_swing` reports false proximity before first swing

**File:** `modules/frr_strategy.py`
**Lines:** 234–242

```python
swing_indices = swing_series.astype(int).cumsum()
bars_since = swing_series.groupby(swing_indices).cumcount()
```

Before the first swing point, all bars are in group 0 with `cumcount` starting from 0. The first `swing_proximity` (10) bars will incorrectly appear to be "near a swing" when no swing has ever occurred. In practice, other filters (Z-score, EMA) need warmup periods that overlap with this window, so false signals are unlikely — but the logic is wrong.

---

## Minor Bugs

### BUG-10: `diagnose_filters.py` — Uses wrong wave direction logic

**File:** `modules/diagnose_filters.py`
**Lines:** 61–66

The diagnostic checks `bullish_wave` for long signals and `bearish_wave` for short signals. But the actual strategy (`frr_strategy.py:288-302`) uses **inverted** logic: `bearish_wave` for longs, `bullish_wave` for shorts. The diagnostic funnel analysis produces misleading numbers.

---

### BUG-11: `diagnose_filters.py` — Hardcoded swing proximity of 2

**File:** `modules/diagnose_filters.py`
**Lines:** 73–74

```python
near_swing_low = (signals['bars_since_swing_low'] <= 2).sum()
```

The actual strategy uses `swing_proximity=10`. The diagnostic underreports how many bars pass the swing filter, making it look more restrictive than it is.

---

### BUG-12: `run_backtest_debug.py` — Doesn't reset `consecutive_losses` daily

**File:** `modules/run_backtest_debug.py`
**Lines:** 54–58

The debug script resets `daily_pnl` on new days but not `consecutive_losses`. The actual backtest (after fix in 5f687a4) resets both. The debug script's circuit breaker tracking won't match the real backtest, producing unreliable diagnostic output.

---

### BUG-13: `run_backtest_simple.py` — Population std vs sample std

**File:** `modules/run_backtest_simple.py`
**Line:** 77

```python
variance = sum((x - mean) ** 2 for x in window) / len(window)  # ddof=0
```

The main strategy uses `pd.Series.rolling().std()` which defaults to `ddof=1` (sample variance). Different divisors produce different Z-scores for the same data. If this script is meant as a fallback for the main strategy, results won't match.

---

### BUG-14: `run_backtest_simple.py` — Stale parameters

**File:** `modules/run_backtest_simple.py`
**Lines:** 204–217

Uses pre-aggressive-tuning values (`z_threshold: 5.0`, `amp_threshold: 1.5`, `chop_threshold: 0.6`) while the current strategy defaults are 3.0, 0.6, and 0.3. Results from this script are not comparable to the main backtest.

---

### BUG-15: `frr_strategy.py` — Sharpe ratio is non-standard

**File:** `modules/frr_strategy.py`
**Line:** 561

```python
sharpe_ratio = trades_df['pnl'].mean() / trades_df['pnl'].std()
```

This is a per-trade information ratio, not an annualized Sharpe ratio. The reported value (0.21) is not comparable to industry-standard Sharpe ratios. Could mislead during validation stage reviews.

---

## Recommended Fix Priority

| Priority | Bug | Rationale |
|----------|-----|-----------|
| 1 | BUG-02 | Circuit breaker blocking exits — affects live trading safety and backtest accuracy |
| 2 | BUG-07 | Stop-loss price bias — inflates reported performance |
| 3 | BUG-01 | MES script crashes — blocks cross-instrument validation |
| 4 | BUG-04 | Sensitivity baseline mismatch — invalidates robustness analysis |
| 5 | BUG-05 | Relative paths — blocks sensitivity analysis execution |
| 6 | BUG-08 | PF=0 edge case — could misfire on acceptance criteria |
| 7 | BUG-10 | Diagnostic wrong direction — produces misleading funnel analysis |
| 8 | BUG-12 | Debug script mismatch — unreliable diagnostic output |
| 9–15 | Rest | Lower priority cleanup |

---

## Notes

- No security vulnerabilities identified (no user input handling, no network calls, no file injection vectors).
- No malware indicators. All code is legitimate quantitative trading research.
- The codebase is well-structured overall, with good documentation and modular design. These bugs are typical of rapid iterative development.
