#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    /// <summary>
    /// Fractal Regime Reversion (FRR) Strategy — V5
    ///
    /// Mean-reversion strategy that enters at Z-score extremes near fractal
    /// swing points, filtered by wave direction. Validated edge:
    /// 547 trades, 59% WR, 3.27 PF, Sharpe 5.24 (2019-2026 MNQ 5-min).
    ///
    /// Entry: Z-extreme + swing proximity + wave direction (inverted)
    /// Exit:  EMA target / stop loss / time / regime
    /// Risk:  Circuit breakers (daily P&L + consecutive losses)
    ///
    /// Python backtest reference: research/modules/frr_strategy.py
    /// </summary>
    public class FRRStrategy : Strategy
    {
        #region Private Fields

        // Indicators
        private EMA ema;
        private ATR atr;
        private StdDev stdDev;

        // Wave direction state
        private double lastSwingLowValue;
        private double lastSwingHighValue;
        private bool lastSwingLowValid;
        private bool lastSwingHighValid;
        private bool currentBullishWave;
        private bool currentBearishWave;

        // Swing tracking
        private int barsSinceSwingHigh;
        private int barsSinceSwingLow;
        private double lastSwingHighLevel;   // For stop loss
        private double lastSwingLowLevel;    // For stop loss
        private bool firstSwingHighSeen;
        private bool firstSwingLowSeen;

        // R1 regime (calculated but only used for exits)
        private Series<double> amplitudeRolling;
        private Series<double> chopRolling;
        private Series<double> energySeries;

        // Circuit breaker state
        private double dailyPnl;
        private int consecutiveLosses;
        private DateTime lastTradeDate;

        // Position tracking
        private int entryBar;
        private string exitReason;

        #endregion

        #region OnStateChange

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Fractal Regime Reversion (FRR) V5 — Z-extreme mean reversion at swing fractals";
                Name = "FRRStrategy";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = false;
                ExitOnSessionCloseSeconds = 30;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                Slippage = 2;
                StartBehavior = StartBehavior.WaitUntilFlat;
                TimeInForce = TimeInForce.Gtc;
                TraceOrders = false;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 100;

                // === STRATEGY PARAMETERS (locked-in, validated) ===
                SwingStrength = 2;
                EmaPeriod = 50;
                ZThreshold = 3.5;
                AtrPeriod = 14;
                StopAtrMult = 1.0;
                MaxHoldBars = 20;
                SwingProximity = 2;
                DailyLossLimit = -200;
                MaxConsecutiveLosses = 3;
                UseWaveFilter = true;
                UseRegimeFilter = false;

                // R1 regime params (used for regime exit even when entry filter off)
                RegimeWindow = 20;
                AmpThreshold = 1.5;
                ChopThreshold = 0.6;
                EnergyThreshold = 50;
            }
            else if (State == State.Configure)
            {
            }
            else if (State == State.DataLoaded)
            {
                ema = EMA(Close, EmaPeriod);
                atr = ATR(AtrPeriod);
                stdDev = StdDev(Close, EmaPeriod);

                amplitudeRolling = new Series<double>(this);
                chopRolling = new Series<double>(this);
                energySeries = new Series<double>(this);

                // Reset state
                lastSwingLowValue = 0;
                lastSwingHighValue = 0;
                lastSwingLowValid = false;
                lastSwingHighValid = false;
                currentBullishWave = false;
                currentBearishWave = false;
                barsSinceSwingHigh = int.MaxValue;
                barsSinceSwingLow = int.MaxValue;
                lastSwingHighLevel = double.NaN;
                lastSwingLowLevel = double.NaN;
                firstSwingHighSeen = false;
                firstSwingLowSeen = false;
                dailyPnl = 0;
                consecutiveLosses = 0;
                lastTradeDate = DateTime.MinValue;
                entryBar = 0;
                exitReason = "";
            }
        }

        #endregion

        #region OnBarUpdate

        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade)
                return;

            // ── DAILY RESET ──
            DateTime barDate = Time[0].Date;
            if (barDate != lastTradeDate)
            {
                lastTradeDate = barDate;
                dailyPnl = 0;
                consecutiveLosses = 0;
            }

            // ── COMPUTE INDICATORS ──
            double zScore = CalculateZScore();
            UpdateSwingPoints();
            UpdateWaveDirection();
            bool isR1 = CalculateR1Regime();

            // ── EXIT LOGIC (always runs, even during circuit breaker) ──
            if (Position.MarketPosition != MarketPosition.Flat)
            {
                int barsHeld = CurrentBar - entryBar;
                bool exitTriggered = false;

                // Priority 1: Profit target — EMA reversion
                if (Position.MarketPosition == MarketPosition.Long && Close[0] >= ema[0])
                {
                    ExitLong("TARGET", "LongEntry");
                    exitReason = "TARGET";
                    exitTriggered = true;
                }
                else if (Position.MarketPosition == MarketPosition.Short && Close[0] <= ema[0])
                {
                    ExitShort("TARGET", "ShortEntry");
                    exitReason = "TARGET";
                    exitTriggered = true;
                }
                // Priority 2: Stop loss
                else if (Position.MarketPosition == MarketPosition.Long && !double.IsNaN(lastSwingLowLevel))
                {
                    double stopLevel = lastSwingLowLevel - (StopAtrMult * atr[0]);
                    if (Close[0] <= stopLevel)
                    {
                        ExitLong("STOP", "LongEntry");
                        exitReason = "STOP";
                        exitTriggered = true;
                    }
                }
                else if (Position.MarketPosition == MarketPosition.Short && !double.IsNaN(lastSwingHighLevel))
                {
                    double stopLevel = lastSwingHighLevel + (StopAtrMult * atr[0]);
                    if (Close[0] >= stopLevel)
                    {
                        ExitShort("STOP", "ShortEntry");
                        exitReason = "STOP";
                        exitTriggered = true;
                    }
                }

                // Priority 3: Time-based exit
                if (!exitTriggered && barsHeld >= MaxHoldBars)
                {
                    if (Position.MarketPosition == MarketPosition.Long)
                        ExitLong("TIME", "LongEntry");
                    else
                        ExitShort("TIME", "ShortEntry");
                    exitReason = "TIME";
                    exitTriggered = true;
                }

                // Priority 4: Regime exit
                if (!exitTriggered && !isR1)
                {
                    if (Position.MarketPosition == MarketPosition.Long)
                        ExitLong("REGIME", "LongEntry");
                    else
                        ExitShort("REGIME", "ShortEntry");
                    exitReason = "REGIME";
                    exitTriggered = true;
                }

                if (exitTriggered)
                    return;
            }

            // ── CIRCUIT BREAKER (only gates new entries) ──
            if (dailyPnl <= DailyLossLimit)
                return;
            if (consecutiveLosses >= MaxConsecutiveLosses)
                return;

            // ── ENTRY LOGIC (signal on previous bar, enter on current open) ──
            if (Position.MarketPosition == MarketPosition.Flat && CurrentBar > 0)
            {
                bool prevLongEntry = CheckLongSignal(1);
                bool prevShortEntry = CheckShortSignal(1);

                if (prevLongEntry)
                {
                    EnterLong(1, "LongEntry");
                    entryBar = CurrentBar;
                }
                else if (prevShortEntry)
                {
                    EnterShort(1, "ShortEntry");
                    entryBar = CurrentBar;
                }
            }
        }

        #endregion

        #region Signal Checks

        private bool CheckLongSignal(int barsAgo)
        {
            if (CurrentBar < barsAgo + EmaPeriod)
                return false;

            // Z-score extreme (oversold)
            double z = CalculateZScoreAt(barsAgo);
            if (z > -ZThreshold)
                return false;

            // Swing proximity
            if (barsSinceSwingLow > SwingProximity + barsAgo)
                return false;

            // R1 regime filter (optional)
            if (UseRegimeFilter && !CalculateR1RegimeAt(barsAgo))
                return false;

            // Wave filter: bearish wave for longs (inverted mean-reversion logic)
            if (UseWaveFilter && !currentBearishWave)
                return false;

            return true;
        }

        private bool CheckShortSignal(int barsAgo)
        {
            if (CurrentBar < barsAgo + EmaPeriod)
                return false;

            // Z-score extreme (overbought)
            double z = CalculateZScoreAt(barsAgo);
            if (z < ZThreshold)
                return false;

            // Swing proximity
            if (barsSinceSwingHigh > SwingProximity + barsAgo)
                return false;

            // R1 regime filter (optional)
            if (UseRegimeFilter && !CalculateR1RegimeAt(barsAgo))
                return false;

            // Wave filter: bullish wave for shorts (inverted mean-reversion logic)
            if (UseWaveFilter && !currentBullishWave)
                return false;

            return true;
        }

        #endregion

        #region Indicator Calculations

        private double CalculateZScore()
        {
            return CalculateZScoreAt(0);
        }

        private double CalculateZScoreAt(int barsAgo)
        {
            if (stdDev[barsAgo] == 0)
                return 0;
            return (Close[barsAgo] - ema[barsAgo]) / stdDev[barsAgo];
        }

        /// <summary>
        /// Detect swing highs/lows using fractal logic: bar must have
        /// high > all highs within SwingStrength bars on both sides
        /// (or low < all lows for swing lows).
        /// Updates bars-since counters and last-swing levels.
        /// </summary>
        private void UpdateSwingPoints()
        {
            int s = SwingStrength;

            if (CurrentBar < s)
                return;

            // Increment bars-since counters
            barsSinceSwingHigh++;
            barsSinceSwingLow++;

            // Check bar at [s] (need s future bars to confirm the fractal)
            // The bar we're confirming is SwingStrength bars ago
            int checkBar = s;

            if (CurrentBar < 2 * s)
                return;

            // --- Swing High detection at bar [checkBar] ---
            bool isSwingHigh = true;
            for (int i = 1; i <= s; i++)
            {
                if (High[checkBar] <= High[checkBar + i] || High[checkBar] <= High[checkBar - i])
                {
                    isSwingHigh = false;
                    break;
                }
            }

            if (isSwingHigh)
            {
                double newHigh = High[checkBar];

                // Update wave direction
                if (lastSwingHighValid)
                    currentBearishWave = newHigh < lastSwingHighValue;

                lastSwingHighValue = newHigh;
                lastSwingHighValid = true;

                // Update stop level and bars-since (offset by confirmation delay)
                lastSwingHighLevel = newHigh;
                barsSinceSwingHigh = s;  // It was s bars ago
                firstSwingHighSeen = true;
            }

            // --- Swing Low detection at bar [checkBar] ---
            bool isSwingLow = true;
            for (int i = 1; i <= s; i++)
            {
                if (Low[checkBar] >= Low[checkBar + i] || Low[checkBar] >= Low[checkBar - i])
                {
                    isSwingLow = false;
                    break;
                }
            }

            if (isSwingLow)
            {
                double newLow = Low[checkBar];

                // Update wave direction
                if (lastSwingLowValid)
                    currentBullishWave = newLow > lastSwingLowValue;

                lastSwingLowValue = newLow;
                lastSwingLowValid = true;

                // Update stop level and bars-since (offset by confirmation delay)
                lastSwingLowLevel = newLow;
                barsSinceSwingLow = s;  // It was s bars ago
                firstSwingLowSeen = true;
            }
        }

        private void UpdateWaveDirection()
        {
            // Wave direction is updated within UpdateSwingPoints
            // This method exists for clarity — wave state persists
            // (forward-filled) until next swing point changes it.
        }

        /// <summary>
        /// R1 Regime: high-vol chop detection.
        /// Amplitude > threshold AND Chop > threshold AND Energy > rolling percentile.
        /// Used for regime exits even when entry filter is disabled.
        /// </summary>
        private bool CalculateR1Regime()
        {
            return CalculateR1RegimeAt(0);
        }

        private bool CalculateR1RegimeAt(int barsAgo)
        {
            if (CurrentBar < RegimeWindow * 5 + barsAgo)
                return false;

            double atrVal = atr[barsAgo];
            if (atrVal == 0)
                return false;

            // Amplitude: rolling mean of (High - Low) / ATR
            double ampSum = 0;
            for (int i = 0; i < RegimeWindow; i++)
            {
                double barAtr = atr[barsAgo + i];
                if (barAtr > 0)
                    ampSum += (High[barsAgo + i] - Low[barsAgo + i]) / barAtr;
            }
            double ampRolling = ampSum / RegimeWindow;

            // Chop: rolling mean of (1 - |Trend|) where Trend = (Close-Open)/(High-Low)
            double chopSum = 0;
            for (int i = 0; i < RegimeWindow; i++)
            {
                double rangeHL = High[barsAgo + i] - Low[barsAgo + i];
                if (rangeHL > 0)
                {
                    double trend = (Close[barsAgo + i] - Open[barsAgo + i]) / rangeHL;
                    chopSum += (1.0 - Math.Abs(trend));
                }
                else
                {
                    chopSum += 1.0;  // Zero range = max chop
                }
            }
            double chopRollingVal = chopSum / RegimeWindow;

            // Energy: Volume * |Close - Open| vs rolling percentile
            double currentEnergy = Volume[barsAgo] * Math.Abs(Close[barsAgo] - Open[barsAgo]);
            int energyWindow = RegimeWindow * 5;
            List<double> energyHistory = new List<double>(energyWindow);
            for (int i = 0; i < energyWindow && (barsAgo + i) < CurrentBar; i++)
            {
                energyHistory.Add(Volume[barsAgo + i] * Math.Abs(Close[barsAgo + i] - Open[barsAgo + i]));
            }
            energyHistory.Sort();
            int pctIdx = (int)(energyHistory.Count * EnergyThreshold / 100.0);
            pctIdx = Math.Min(pctIdx, energyHistory.Count - 1);
            double energyThresholdVal = energyHistory.Count > 0 ? energyHistory[pctIdx] : 0;

            return ampRolling > AmpThreshold
                && chopRollingVal > ChopThreshold
                && currentEnergy > energyThresholdVal;
        }

        #endregion

        #region Execution Tracking

        protected override void OnExecutionUpdate(Execution execution, string executionId,
            double price, int quantity, MarketPosition marketPosition,
            string orderId, DateTime time)
        {
            // Track P&L for circuit breakers when a position closes
            if (Position.MarketPosition == MarketPosition.Flat && SystemPerformance.AllTrades.Count > 0)
            {
                Trade lastTrade = SystemPerformance.AllTrades[SystemPerformance.AllTrades.Count - 1];
                double pnl = lastTrade.ProfitCurrency;

                dailyPnl += pnl;

                if (pnl < 0)
                    consecutiveLosses++;
                else
                    consecutiveLosses = 0;
            }
        }

        #endregion

        #region Properties

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Swing Strength", Description = "Fractal lookback bars on each side", Order = 1, GroupName = "Entry")]
        public int SwingStrength { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "EMA Period", Description = "Mean reversion target period", Order = 2, GroupName = "Entry")]
        public int EmaPeriod { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, double.MaxValue)]
        [Display(Name = "Z Threshold", Description = "Z-score extreme threshold", Order = 3, GroupName = "Entry")]
        public double ZThreshold { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Swing Proximity", Description = "Max bars from swing for entry", Order = 4, GroupName = "Entry")]
        public int SwingProximity { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use Wave Filter", Description = "Enable wave direction filter", Order = 5, GroupName = "Entry")]
        public bool UseWaveFilter { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use Regime Filter", Description = "Enable R1 regime entry filter", Order = 6, GroupName = "Entry")]
        public bool UseRegimeFilter { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "ATR Period", Description = "ATR calculation period", Order = 1, GroupName = "Exit")]
        public int AtrPeriod { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, double.MaxValue)]
        [Display(Name = "Stop ATR Multiplier", Description = "Stop distance in ATR units", Order = 2, GroupName = "Exit")]
        public double StopAtrMult { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Max Hold Bars", Description = "Time exit after N bars", Order = 3, GroupName = "Exit")]
        public int MaxHoldBars { get; set; }

        [NinjaScriptProperty]
        [Range(-100000, 0)]
        [Display(Name = "Daily Loss Limit", Description = "Circuit breaker: max daily loss ($)", Order = 1, GroupName = "Risk")]
        public double DailyLossLimit { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Max Consecutive Losses", Description = "Circuit breaker: max losses in a row", Order = 2, GroupName = "Risk")]
        public int MaxConsecutiveLosses { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Regime Window", Description = "R1 regime rolling window", Order = 1, GroupName = "Regime")]
        public int RegimeWindow { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, double.MaxValue)]
        [Display(Name = "Amplitude Threshold", Description = "R1 amplitude threshold", Order = 2, GroupName = "Regime")]
        public double AmpThreshold { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, 1.0)]
        [Display(Name = "Chop Threshold", Description = "R1 chop threshold", Order = 3, GroupName = "Regime")]
        public double ChopThreshold { get; set; }

        [NinjaScriptProperty]
        [Range(1, 99)]
        [Display(Name = "Energy Threshold", Description = "R1 energy percentile", Order = 4, GroupName = "Regime")]
        public int EnergyThreshold { get; set; }

        #endregion
    }
}
