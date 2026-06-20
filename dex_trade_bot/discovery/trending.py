"""Trending-token discovery via DexScreener search.

Returns normalized market snapshots for liquid, actively-traded BSC tokens. Used
by the momentum and mean-reversion strategies. Needs no RPC.
"""
from ..dex import marketdata

# Broad seed queries to surface active BSC pairs without a paid trending feed.
_SEED_QUERIES = ["WBNB", "USDT", "BUSD"]


class TrendingDiscovery:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    def discover(self, limit=30):
        seen = {}
        for query in _SEED_QUERIES:
            for snap in marketdata.search(query):
                addr = snap.get("token_address", "").lower()
                if not addr or addr in seen:
                    continue
                if snap["liquidity_usd"] < self.config.MIN_LIQUIDITY_USD:
                    continue
                if snap["volume_h24"] <= 0:
                    continue
                seen[addr] = snap
        # Rank by recent activity so the most tradable names come first.
        ranked = sorted(seen.values(), key=lambda s: s["volume_h1"], reverse=True)
        return ranked[:limit]
