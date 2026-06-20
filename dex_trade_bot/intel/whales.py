"""Smart-money / whale tracking and copy-trade signals.

Watches a configured list of wallets (WHALE_WATCHLIST) for recent token buys by
scanning their on-chain transfers. A fresh buy by a watched wallet into a token
emits a positive copy signal for that token.

Honest limit baked in: a whale's buy moves price, so by the time we observe it on
chain we may get a worse fill. The scoring model discounts copy signals by an
expected adverse-fill factor; this module only reports the raw observation.
"""
from ..constants import ERC20_ABI


class WhaleTracker:
    def __init__(self, web3_client, config, logger):
        self.web3_client = web3_client
        self.config = config
        self.logger = logger
        self.watchlist = [w.lower() for w in config.WHALE_WATCHLIST]
        # token_address(lower) -> number of distinct watched wallets seen buying recently
        self._recent_buys = {}

    @property
    def enabled(self):
        return bool(self.watchlist) and self.web3_client.connected

    def observe(self, token_address, lookback_blocks=3000):
        """Count watched wallets that received `token_address` recently (a proxy for buying)."""
        if not self.enabled:
            return 0
        try:
            w3 = self.web3_client.w3
            token = self.web3_client.contract(token_address, ERC20_ABI)
            latest = w3.eth.block_number
            transfer_topic = w3.keccak(text="Transfer(address,address,uint256)").hex()
            logs = w3.eth.get_logs({
                "fromBlock": max(0, latest - lookback_blocks),
                "toBlock": latest,
                "address": token.address,
                "topics": [transfer_topic],
            })
            buyers = set()
            for log in logs:
                if len(log["topics"]) >= 3:
                    to_addr = "0x" + log["topics"][2].hex()[-40:]
                    if to_addr.lower() in self.watchlist:
                        buyers.add(to_addr.lower())
            count = len(buyers)
            self._recent_buys[token_address.lower()] = count
            return count
        except Exception as e:  # pylint: disable=broad-except
            self.logger.debug(f"whale observe failed for {token_address}: {e}")
            return 0

    def copy_signal(self, token_address):
        """0..1 signal based on how many watched wallets are in this token."""
        count = self._recent_buys.get(token_address.lower(), 0)
        if count <= 0:
            return 0.0
        return min(1.0, count / max(1, len(self.watchlist)))
