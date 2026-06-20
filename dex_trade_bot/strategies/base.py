"""Strategy base class.

A strategy turns scored candidates into OPEN intents and decides when to exit its
own positions. Exit defaults (trailing stop / take-profit / stop-loss / time stop)
live here; strategies override ``should_exit`` only when they need different logic.
"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Intent:
    strategy: str
    token_address: str
    symbol: str
    price_usd: float
    liquidity_usd: float
    expected_edge_pct: float
    confidence: float
    buy_tax_pct: float = 0.0
    sell_tax_pct: float = 0.0
    meta: dict = field(default_factory=dict)

    def as_candidate(self):
        return {"token_address": self.token_address, "symbol": self.symbol}


class Strategy:
    name = "base"

    # Default exit parameters (override per strategy as needed).
    take_profit_pct = 25.0
    stop_loss_pct = 12.0
    trailing_stop_pct = 10.0
    max_hold_minutes = 240

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    def generate_open_intents(self, scored_candidates):
        """Return a list of Intent for tokens this strategy wants to open. Override."""
        raise NotImplementedError

    def reference_price(self, position, snapshot):
        """Current price used for exit bookkeeping. Override when not snapshot-driven."""
        return (snapshot or {}).get("price_usd", position.entry_price_usd)

    def reference_liquidity(self, position, snapshot):
        return (snapshot or {}).get("liquidity_usd", 0) or 0

    def should_exit(self, position, snapshot):
        """Generic exit logic shared by most strategies. Returns (bool, reason)."""
        price = snapshot.get("price_usd", 0)
        if price <= 0 or position.entry_price_usd <= 0:
            return False, ""

        change_pct = (price - position.entry_price_usd) / position.entry_price_usd * 100.0

        if change_pct >= self.take_profit_pct:
            return True, f"take-profit {change_pct:+.1f}%"
        if change_pct <= -self.stop_loss_pct:
            return True, f"stop-loss {change_pct:+.1f}%"

        # Trailing stop off the high-water mark.
        if position.high_water_price > 0:
            drawdown = (price - position.high_water_price) / position.high_water_price * 100.0
            if drawdown <= -self.trailing_stop_pct and change_pct > 0:
                return True, f"trailing-stop {drawdown:+.1f}% from high"

        age_min = (datetime.utcnow() - position.opened_at).total_seconds() / 60
        if age_min >= self.max_hold_minutes:
            return True, f"time-stop {age_min:.0f}m"

        return False, ""
