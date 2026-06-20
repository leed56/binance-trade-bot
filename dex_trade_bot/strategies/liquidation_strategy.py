"""Lending liquidation strategy (Venus on BSC) — MONITOR at $30.

Capturing a liquidation means repaying part of an undercollateralized borrower's
debt to seize their collateral plus a bonus. That requires capital (often far more
than $30) and wins go to gas-competitive funded bots. So this strategy surfaces and
logs opportunities via the Venus monitor but does not place liquidation calls at
this capital level — it emits no open intents. The wiring is here so it can be
enabled with real capital later by extending the executor with a liquidate path.

The orchestrator injects ``venus`` (VenusMonitor).
"""
from .base import Strategy


class Strategy(Strategy):  # noqa: F811
    name = "liquidation"

    def __init__(self, config, logger):
        super().__init__(config, logger)
        self.venus = None

    def generate_open_intents(self, scored_candidates):
        if self.venus is None or not self.venus.enabled:
            return []
        opportunities = self.venus.scan()
        if opportunities:
            total = sum(o["shortfall_usd"] for o in opportunities)
            self.logger.info(
                f"[LIQUIDATION-MONITOR] {len(opportunities)} liquidatable accounts "
                f"(total shortfall ${total:,.2f}) — needs capital to execute, not firing at $30")
        return []  # monitor only at this capital level
