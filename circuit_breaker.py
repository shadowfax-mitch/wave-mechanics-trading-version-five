"""
Circuit Breaker Risk Management Layer
Wraps around trading strategies to enforce loss limits and drawdown protection.

Usage:
    breaker = CircuitBreaker(
        daily_loss_limit=-80,
        weekly_loss_limit=-150,
        consecutive_loss_limit=2
    )
    
    # Before each trade
    if breaker.can_trade():
        # Execute strategy logic
        result = execute_trade()
        breaker.record_trade(result)
    else:
        # Circuit breaker active - no trading
        print(breaker.get_status())
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import List, Optional
import json
from pathlib import Path


@dataclass
class Trade:
    timestamp: datetime
    pnl: float
    strategy: str
    notes: str = ""


@dataclass
class CircuitBreakerState:
    """Persistent state for circuit breaker"""
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    consecutive_losses: int = 0
    last_trade_date: Optional[date] = None
    week_start_date: Optional[date] = None
    trades_today: List[Trade] = field(default_factory=list)
    trades_this_week: List[Trade] = field(default_factory=list)
    circuit_breaker_active: bool = False
    circuit_breaker_reason: str = ""
    
    def to_dict(self) -> dict:
        return {
            "daily_pnl": self.daily_pnl,
            "weekly_pnl": self.weekly_pnl,
            "consecutive_losses": self.consecutive_losses,
            "last_trade_date": self.last_trade_date.isoformat() if self.last_trade_date else None,
            "week_start_date": self.week_start_date.isoformat() if self.week_start_date else None,
            "trades_today": [
                {
                    "timestamp": t.timestamp.isoformat(),
                    "pnl": t.pnl,
                    "strategy": t.strategy,
                    "notes": t.notes
                }
                for t in self.trades_today
            ],
            "trades_this_week": [
                {
                    "timestamp": t.timestamp.isoformat(),
                    "pnl": t.pnl,
                    "strategy": t.strategy,
                    "notes": t.notes
                }
                for t in self.trades_this_week
            ],
            "circuit_breaker_active": self.circuit_breaker_active,
            "circuit_breaker_reason": self.circuit_breaker_reason,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CircuitBreakerState':
        state = cls()
        state.daily_pnl = data.get("daily_pnl", 0.0)
        state.weekly_pnl = data.get("weekly_pnl", 0.0)
        state.consecutive_losses = data.get("consecutive_losses", 0)
        
        if data.get("last_trade_date"):
            state.last_trade_date = date.fromisoformat(data["last_trade_date"])
        if data.get("week_start_date"):
            state.week_start_date = date.fromisoformat(data["week_start_date"])
        
        # Reconstruct trades
        for t_data in data.get("trades_today", []):
            state.trades_today.append(Trade(
                timestamp=datetime.fromisoformat(t_data["timestamp"]),
                pnl=t_data["pnl"],
                strategy=t_data["strategy"],
                notes=t_data.get("notes", "")
            ))
        
        for t_data in data.get("trades_this_week", []):
            state.trades_this_week.append(Trade(
                timestamp=datetime.fromisoformat(t_data["timestamp"]),
                pnl=t_data["pnl"],
                strategy=t_data["strategy"],
                notes=t_data.get("notes", "")
            ))
        
        state.circuit_breaker_active = data.get("circuit_breaker_active", False)
        state.circuit_breaker_reason = data.get("circuit_breaker_reason", "")
        
        return state


class CircuitBreaker:
    """
    Risk management circuit breaker to prevent catastrophic losses.
    
    Enforces:
    - Daily loss limits
    - Weekly loss limits
    - Consecutive loss limits
    - Automatic trading suspension when limits breached
    """
    
    def __init__(
        self,
        daily_loss_limit: float = -80.0,
        weekly_loss_limit: float = -150.0,
        consecutive_loss_limit: int = 2,
        state_file: Optional[Path] = None
    ):
        """
        Initialize circuit breaker.
        
        Args:
            daily_loss_limit: Maximum daily loss before shutdown (negative number)
            weekly_loss_limit: Maximum weekly loss before shutdown (negative number)
            consecutive_loss_limit: Number of consecutive losses before shutdown
            state_file: Path to persist state (optional, for recovery after restart)
        """
        self.daily_loss_limit = daily_loss_limit
        self.weekly_loss_limit = weekly_loss_limit
        self.consecutive_loss_limit = consecutive_loss_limit
        self.state_file = state_file or Path("circuit_breaker_state.json")
        
        # Load or initialize state
        self.state = self._load_state()
        
        # Check if new day/week
        self._check_rollover()
    
    def _load_state(self) -> CircuitBreakerState:
        """Load state from file or create new"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                return CircuitBreakerState.from_dict(data)
            except Exception as e:
                print(f"Warning: Could not load state file: {e}")
        
        return CircuitBreakerState()
    
    def _save_state(self):
        """Persist state to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state.to_dict(), f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save state file: {e}")
    
    def _check_rollover(self):
        """Check if we need to reset daily/weekly counters"""
        today = date.today()
        
        # Daily rollover
        if self.state.last_trade_date != today:
            # Reset daily counters
            self.state.daily_pnl = 0.0
            self.state.trades_today = []
            
            # If circuit breaker was active from yesterday, reset it
            if self.state.circuit_breaker_active and "daily" in self.state.circuit_breaker_reason.lower():
                self.state.circuit_breaker_active = False
                self.state.circuit_breaker_reason = ""
            
            self.state.last_trade_date = today
        
        # Weekly rollover (start week on Monday)
        if self.state.week_start_date is None:
            # Initialize to this week's Monday
            self.state.week_start_date = today - timedelta(days=today.weekday())
        
        # Check if we crossed into new week
        current_week_start = today - timedelta(days=today.weekday())
        if current_week_start != self.state.week_start_date:
            # Reset weekly counters
            self.state.weekly_pnl = 0.0
            self.state.trades_this_week = []
            self.state.week_start_date = current_week_start
            
            # Reset circuit breaker if it was weekly
            if self.state.circuit_breaker_active and "weekly" in self.state.circuit_breaker_reason.lower():
                self.state.circuit_breaker_active = False
                self.state.circuit_breaker_reason = ""
        
        self._save_state()
    
    def can_trade(self) -> bool:
        """
        Check if trading is allowed.
        
        Returns:
            True if trading allowed, False if circuit breaker active
        """
        self._check_rollover()
        return not self.state.circuit_breaker_active
    
    def record_trade(self, pnl: float, strategy: str = "default", notes: str = ""):
        """
        Record a trade and update circuit breaker state.
        
        Args:
            pnl: Profit/loss of the trade (positive = win, negative = loss)
            strategy: Name of strategy that generated trade
            notes: Optional notes about the trade
        """
        self._check_rollover()
        
        # Create trade record
        trade = Trade(
            timestamp=datetime.now(),
            pnl=pnl,
            strategy=strategy,
            notes=notes
        )
        
        # Update counters
        self.state.daily_pnl += pnl
        self.state.weekly_pnl += pnl
        self.state.trades_today.append(trade)
        self.state.trades_this_week.append(trade)
        
        # Update consecutive losses
        if pnl < 0:
            self.state.consecutive_losses += 1
        else:
            self.state.consecutive_losses = 0
        
        # Check circuit breaker conditions
        self._check_circuit_breaker()
        
        self._save_state()
    
    def _check_circuit_breaker(self):
        """Check if circuit breaker should activate"""
        
        # Check daily loss limit
        if self.state.daily_pnl <= self.daily_loss_limit:
            self.state.circuit_breaker_active = True
            self.state.circuit_breaker_reason = (
                f"Daily loss limit breached: ${self.state.daily_pnl:.2f} <= ${self.daily_loss_limit:.2f}"
            )
            return
        
        # Check weekly loss limit
        if self.state.weekly_pnl <= self.weekly_loss_limit:
            self.state.circuit_breaker_active = True
            self.state.circuit_breaker_reason = (
                f"Weekly loss limit breached: ${self.state.weekly_pnl:.2f} <= ${self.weekly_loss_limit:.2f}"
            )
            return
        
        # Check consecutive losses
        if self.state.consecutive_losses >= self.consecutive_loss_limit:
            self.state.circuit_breaker_active = True
            self.state.circuit_breaker_reason = (
                f"Consecutive loss limit breached: {self.state.consecutive_losses} >= {self.consecutive_loss_limit}"
            )
            return
    
    def get_status(self) -> dict:
        """Get current circuit breaker status"""
        self._check_rollover()
        
        return {
            "can_trade": not self.state.circuit_breaker_active,
            "circuit_breaker_active": self.state.circuit_breaker_active,
            "reason": self.state.circuit_breaker_reason,
            "daily_pnl": self.state.daily_pnl,
            "daily_limit": self.daily_loss_limit,
            "daily_remaining": self.daily_loss_limit - self.state.daily_pnl,
            "weekly_pnl": self.state.weekly_pnl,
            "weekly_limit": self.weekly_loss_limit,
            "weekly_remaining": self.weekly_loss_limit - self.state.weekly_pnl,
            "consecutive_losses": self.state.consecutive_losses,
            "consecutive_limit": self.consecutive_loss_limit,
            "trades_today": len(self.state.trades_today),
            "trades_this_week": len(self.state.trades_this_week),
        }
    
    def reset_circuit_breaker(self, manual_override: bool = False):
        """
        Manually reset circuit breaker.
        
        Args:
            manual_override: If True, allows reset even in same day/week.
                           Use with EXTREME caution.
        """
        if manual_override:
            self.state.circuit_breaker_active = False
            self.state.circuit_breaker_reason = ""
            self._save_state()
            print("⚠️ Circuit breaker MANUALLY OVERRIDDEN - Use extreme caution")
        else:
            print("❌ Cannot reset circuit breaker without manual_override=True")
            print("   This is intentional - prevents impulsive revenge trading")
    
    def get_trade_history(self, days: int = 7) -> List[Trade]:
        """Get recent trade history"""
        cutoff = datetime.now() - timedelta(days=days)
        return [
            t for t in self.state.trades_this_week
            if t.timestamp >= cutoff
        ]


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Initialize circuit breaker
    breaker = CircuitBreaker(
        daily_loss_limit=-80,
        weekly_loss_limit=-150,
        consecutive_loss_limit=2
    )
    
    print("Circuit Breaker Example")
    print("=" * 50)
    
    # Simulate trading day
    trades = [
        (-30, "Morning trade - stopped out"),
        (45, "Mid-morning winner"),
        (-25, "Gave back some profits"),
        (-35, "Another loss - consecutive #2"),
    ]
    
    for i, (pnl, note) in enumerate(trades, 1):
        print(f"\nTrade {i}: ${pnl:+.2f} - {note}")
        
        if breaker.can_trade():
            breaker.record_trade(pnl, strategy="ZThreeNoFilter", notes=note)
            status = breaker.get_status()
            print(f"  Daily P&L: ${status['daily_pnl']:+.2f}")
            print(f"  Consecutive losses: {status['consecutive_losses']}")
            print(f"  Can still trade: {status['can_trade']}")
        else:
            status = breaker.get_status()
            print(f"  🔴 CIRCUIT BREAKER ACTIVE")
            print(f"  Reason: {status['reason']}")
            print(f"  Trade NOT executed")
            break
    
    print("\n" + "=" * 50)
    print("Final Status:")
    status = breaker.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
