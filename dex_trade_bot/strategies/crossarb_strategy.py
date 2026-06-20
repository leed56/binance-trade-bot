"""Cross-venue (CEX vs DEX) strategy.

Compares Binance spot price (a deep, fast global reference) against the BSC DEX
price for the same token. Two honest realities shape this:

  * True cross-venue arbitrage (buy on one venue, sell on the other) is NOT viable
    at $30: deposit/withdrawal latency and transfer fees between Binance and the
    chain dwarf the edge. So we do not attempt two-legged transfers.
  * What IS executable on-chain alone: treat Binance as an oracle. When the DEX
    price lags meaningfully BELOW Binance, buy the token on the DEX expecting it to
    converge upward. This is a single-venue trade the normal executor can do.

It logs every gap (monitor value) and only emits a buy intent when the lag clears
DEX costs with margin. The orchestrator injects ``cex``, ``pancake``, ``web3_client``.
"""
from ..constants import COMMON_TOKENS, USDT
from ..dex import marketdata
from .base import Intent, Strategy

MIN_LAG_PCT = 1.5  # DEX must lag CEX by this much to clear DEX gas+slippage


class Strategy(Strategy):  # noqa: F811
    name = "crossarb"
    take_profit_pct = 4.0
    stop_loss_pct = 4.0
    trailing_stop_pct = 2.5
    max_hold_minutes = 120

    def __init__(self, config, logger):
        super().__init__(config, logger)
        self.cex = None
        self.pancake = None
        self.web3_client = None

    def generate_open_intents(self, scored_candidates):
        if self.cex is None or not self.cex.available or not getattr(self.web3_client, "connected", False):
            return []
        intents = []
        for symbol in self.config.CROSSARB_SYMBOLS:
            token = COMMON_TOKENS.get(symbol.upper())
            if not token:
                continue
            dex_price = self.pancake.quote_out(token, USDT, 1.0)
            cex_price = self.cex.price(f"{symbol.upper()}USDT")
            if not dex_price or not cex_price:
                continue
            lag_pct = (cex_price - dex_price) / dex_price * 100.0
            self.logger.info(
                f"[CROSSARB-MONITOR] {symbol}: CEX {cex_price:.6g} vs DEX {dex_price:.6g} "
                f"(DEX lag {lag_pct:+.2f}%)")
            min_lag = 0.2 if self.config.demo_active else MIN_LAG_PCT
            if lag_pct < min_lag:
                continue
            snap = marketdata.token_market(token) or {}
            liquidity = snap.get("liquidity_usd", 0) or 0
            intents.append(Intent(
                strategy=self.name, token_address=token, symbol=symbol.upper(),
                price_usd=dex_price, liquidity_usd=liquidity,
                expected_edge_pct=lag_pct, confidence=0.5,
            ))
        return intents
