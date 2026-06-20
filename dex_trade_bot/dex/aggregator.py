"""Best-price comparison across BSC DEXes (for the arbitrage monitor).

Wraps two PancakeSwap-style routers (Pancake + Biswap, both V2-compatible) and
reports the price gap for the same token between them.
"""
from ..constants import BISWAP_FACTORY, BISWAP_ROUTER, PANCAKE_V2_FACTORY, PANCAKE_V2_ROUTER
from .pancakeswap import PancakeSwap


class Aggregator:
    def __init__(self, web3_client, logger):
        self.web3_client = web3_client
        self.logger = logger
        self.venues = [
            PancakeSwap(web3_client, logger, PANCAKE_V2_ROUTER, PANCAKE_V2_FACTORY, "pancake"),
            PancakeSwap(web3_client, logger, BISWAP_ROUTER, BISWAP_FACTORY, "biswap"),
        ]

    def best_quote(self, token_in, token_out, amount_in_human):
        """Return (venue, output) for the venue giving the most output, or (None, None)."""
        best_venue, best_out = None, None
        for venue in self.venues:
            out = venue.quote_out(token_in, token_out, amount_in_human)
            if out is not None and (best_out is None or out > best_out):
                best_venue, best_out = venue, out
        return best_venue, best_out

    def price_gap(self, token, stable, amount_human):
        """Compare token price across venues. Returns dict with the relative gap."""
        quotes = {}
        for venue in self.venues:
            out = venue.quote_out(token, stable, amount_human)
            if out is not None and out > 0:
                quotes[venue.name] = out / amount_human  # stable-per-token
        if len(quotes) < 2:
            return None
        cheap = min(quotes, key=quotes.get)
        rich = max(quotes, key=quotes.get)
        gap_pct = (quotes[rich] - quotes[cheap]) / quotes[cheap] * 100
        return {"buy_on": cheap, "sell_on": rich, "gap_pct": gap_pct, "quotes": quotes}
