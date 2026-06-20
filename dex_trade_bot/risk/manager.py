"""Risk manager: the last gate before any intent becomes an order.

Enforces hard caps and computes position size. Any single failing check vetoes
the trade. Also owns the daily loss stop and a global kill switch.
"""
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class RiskDecision:
    approved: bool
    size_usd: float = 0.0
    reason: str = ""


class RiskManager:
    def __init__(self, config, database, logger):
        self.config = config
        self.db = database
        self.logger = logger
        self.kill_switch = False
        self._day = self._today()
        self._day_start_realized = self.db.realized_pnl()

    @staticmethod
    def _today():
        return datetime.now(timezone.utc).date()

    def _roll_day(self):
        today = self._today()
        if today != self._day:
            self._day = today
            self._day_start_realized = self.db.realized_pnl()

    def daily_pnl(self):
        self._roll_day()
        return self.db.realized_pnl() - self._day_start_realized

    def trading_halted(self):
        if self.kill_switch:
            return True, "kill switch engaged"
        if self.daily_pnl() <= -abs(self.config.DAILY_LOSS_STOP_USD):
            return True, f"daily loss stop hit ({self.daily_pnl():.2f} USD)"
        return False, ""

    def evaluate_open(self, candidate, cash_usd, expected_edge_pct, est_cost_pct):
        """Decide whether to open, and for how much (USD)."""
        halted, why = self.trading_halted()
        if halted:
            return RiskDecision(False, reason=why)

        if self.db.count_open_positions() >= self.config.MAX_OPEN_POSITIONS:
            return RiskDecision(False, reason="max open positions reached")

        if self.db.get_open_position(candidate["token_address"]) is not None:
            return RiskDecision(False, reason="already holding this token")

        demo = self.config.demo_active

        # Cooldown: don't re-enter a token we just traded (shortened in demo).
        cooldown_min = 1 if demo else self.config.PER_TOKEN_COOLDOWN_MIN
        last = self.db.last_trade_time(candidate["token_address"])
        if last is not None:
            age_min = (datetime.utcnow() - last).total_seconds() / 60
            if age_min < cooldown_min:
                return RiskDecision(False, reason=f"token cooldown ({age_min:.0f}m)")

        # Gas-vs-edge guard: expected edge must clear all-in costs with a margin.
        # Demo mode bypasses this so you can watch trades happen (paper-only).
        if not demo and expected_edge_pct <= est_cost_pct:
            return RiskDecision(
                False, reason=f"edge {expected_edge_pct:.2f}% <= cost {est_cost_pct:.2f}%"
            )

        if demo:
            size_usd = round(
                min(self.config.MAX_POSITION_USD, cash_usd * self.config.MAX_TRADE_PCT / 100.0), 4
            )
        else:
            size_usd = self._position_size(cash_usd, expected_edge_pct, est_cost_pct)
        if size_usd <= 0:
            return RiskDecision(False, reason="computed size <= 0")

        return RiskDecision(True, size_usd=size_usd, reason="approved" + (" (demo)" if demo else ""))

    def _position_size(self, cash_usd, expected_edge_pct, est_cost_pct):
        """Fractional-Kelly-style sizing, hard-capped by config."""
        net_edge = max(0.0, (expected_edge_pct - est_cost_pct) / 100.0)
        # Quarter-Kelly on a conservative edge, then clamp.
        kelly_fraction = min(0.25, net_edge)  # net_edge already small
        size = cash_usd * kelly_fraction
        size = min(size, self.config.MAX_POSITION_USD, cash_usd * self.config.MAX_TRADE_PCT / 100.0)
        return round(size, 4)

    def engage_kill_switch(self, reason=""):
        self.kill_switch = True
        self.logger.error(f"KILL SWITCH ENGAGED: {reason}", notification=True)
