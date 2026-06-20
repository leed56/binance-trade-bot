"""Stablecoin peg arbitrage / grid (USDT <-> USDC).

Patient mean-reversion on the stable pair. Sits idle while the pair is within a
band of $1. Buys the under-peg leg (USDC priced in USDT) only when the deviation
exceeds the all-in cost, and exits on reversion toward peg. Lowest risk family;
meaningfully profitable only during rare depeg events, so it does nothing most of
the time — that idleness is correct, not a bug.

The orchestrator injects ``pancake`` (quoter) and ``web3_client``.
"""
from ..constants import USDC, USDT
from .base import Intent, Strategy

# Bands as fractions of $1.
ENTRY_DEVIATION = 0.002   # buy when USDC <= 0.998 (covers stable swap costs + margin)
EXIT_BAND = 0.0005        # exit when back within 0.0005 of peg


class Strategy(Strategy):  # noqa: F811
    name = "stablegrid"
    max_hold_minutes = 7 * 24 * 60  # patient: hold up to a week waiting for re-peg
    stop_loss_pct = 5.0             # if USDC truly de-pegs hard, cut it

    def __init__(self, config, logger):
        super().__init__(config, logger)
        self.pancake = None
        self.web3_client = None

    def _usdc_price_in_usdt(self):
        """Quote 1 USDC -> USDT. ~1.0 at peg; < 1 when USDC is cheap."""
        if self.pancake is None or not getattr(self.web3_client, "connected", False):
            return None
        return self.pancake.quote_out(USDC, USDT, 1.0, path=[USDC, USDT])

    def generate_open_intents(self, scored_candidates):
        price = self._usdc_price_in_usdt()
        if price is None or price <= 0:
            return []
        deviation = 1.0 - price  # positive when USDC is under peg
        entry_band = 0.0003 if self.config.demo_active else ENTRY_DEVIATION
        if deviation < entry_band:
            return []  # within band: do nothing (the correct default)

        self.logger.info(f"[STABLEGRID] USDC at {price:.5f} (dev {deviation*100:.3f}%) -> peg entry")
        expected_edge_pct = deviation * 100.0  # expect reversion to peg
        return [Intent(
            strategy=self.name, token_address=USDC, symbol="USDC",
            price_usd=price, liquidity_usd=5_000_000,  # stable pools are deep -> tiny slippage
            expected_edge_pct=expected_edge_pct, confidence=0.9,
        )]

    def reference_price(self, position, snapshot):
        price = self._usdc_price_in_usdt()
        return price if price else position.entry_price_usd

    def reference_liquidity(self, position, snapshot):
        return 5_000_000

    def should_exit(self, position, snapshot):
        price = self._usdc_price_in_usdt()
        if price is None:
            return False, ""
        if price >= 1.0 - EXIT_BAND:
            return True, f"re-pegged at {price:.5f}"
        # Hard stop if USDC collapses further than our tolerance.
        change_pct = (price - position.entry_price_usd) / position.entry_price_usd * 100.0
        if change_pct <= -self.stop_loss_pct:
            return True, f"depeg stop {change_pct:+.1f}%"
        return False, ""
