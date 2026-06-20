"""DEX-DEX arbitrage — primarily a MONITOR at $30.

Compares a token's price across two BSC DEXes (Pancake vs Biswap) via the
aggregator. Logs every meaningful gap as a learning record. It only emits an OPEN
intent when the gap exceeds the all-in cost by a wide, configurable margin — which
at $30 will almost never happen, by design. The orchestrator injects ``aggregator``.
"""
from .base import Intent, Strategy

MIN_GAP_PCT_TO_TRADE = 3.0  # gap must clear gas+slippage+tax with margin; rare at small size


class Strategy(Strategy):  # noqa: F811
    name = "arbitrage"
    take_profit_pct = 100.0  # arb closes immediately; these are placeholders
    stop_loss_pct = 50.0
    max_hold_minutes = 5

    def __init__(self, config, logger):
        super().__init__(config, logger)
        self.aggregator = None  # set by orchestrator when web3 is connected

    def generate_open_intents(self, scored_candidates):
        if self.aggregator is None:
            return []
        from ..constants import USDT

        intents = []
        for c in scored_candidates[:15]:  # bound work per cycle
            snap = c["snapshot"]
            probe_usd = min(self.config.MAX_POSITION_USD, 5.0)
            gap = self.aggregator.price_gap(snap["token_address"], USDT, probe_usd)
            if not gap:
                continue
            self.logger.info(
                f"[ARB-MONITOR] {snap['symbol']}: {gap['gap_pct']:.2f}% "
                f"(buy {gap['buy_on']} / sell {gap['sell_on']})")
            if gap["gap_pct"] >= MIN_GAP_PCT_TO_TRADE:
                intents.append(Intent(
                    strategy=self.name, token_address=snap["token_address"], symbol=snap["symbol"],
                    price_usd=snap["price_usd"], liquidity_usd=snap["liquidity_usd"],
                    expected_edge_pct=gap["gap_pct"], confidence=0.8,
                    buy_tax_pct=c.get("buy_tax_pct", 0.0), sell_tax_pct=c.get("sell_tax_pct", 0.0),
                    meta={"arb": gap},
                ))
        return intents
