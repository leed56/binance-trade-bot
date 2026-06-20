"""New-pair discovery via the PancakeSwap factory ``PairCreated`` event.

Polls recent blocks for newly created pairs that include a base asset (WBNB or a
stable), then resolves the non-base token as a fresh candidate. Requires an RPC
connection; degrades to an empty list when offline.
"""
from ..constants import FACTORY_ABI, PANCAKE_V2_FACTORY, STABLES, WBNB

_BASES = {WBNB.lower()} | {addr.lower() for addr in STABLES.values()}


class NewPairsDiscovery:
    def __init__(self, web3_client, config, logger):
        self.web3_client = web3_client
        self.config = config
        self.logger = logger
        self._last_block = None

    def discover(self, lookback_blocks=400):
        if not self.web3_client.connected:
            return []
        try:
            w3 = self.web3_client.w3
            factory = self.web3_client.contract(PANCAKE_V2_FACTORY, FACTORY_ABI)
            latest = w3.eth.block_number
            from_block = self._last_block or max(0, latest - lookback_blocks)
            events = factory.events.PairCreated().get_logs(fromBlock=from_block, toBlock=latest)
            self._last_block = latest + 1

            candidates = []
            for ev in events:
                token0 = ev["args"]["token0"]
                token1 = ev["args"]["token1"]
                base, token = self._classify(token0, token1)
                if token is None:
                    continue  # neither side is a base asset we price against
                candidates.append({
                    "token_address": token,
                    "base_address": base,
                    "pair_address": ev["args"]["pair"],
                    "symbol": self.web3_client.erc20_symbol(token),
                    "source": "new_pairs",
                })
            if candidates:
                self.logger.info(f"Discovered {len(candidates)} new pairs")
            return candidates
        except Exception as e:  # pylint: disable=broad-except
            self.logger.debug(f"new-pairs discovery failed: {e}")
            return []

    @staticmethod
    def _classify(token0, token1):
        t0, t1 = token0.lower(), token1.lower()
        if t0 in _BASES and t1 not in _BASES:
            return token0, token1
        if t1 in _BASES and t0 not in _BASES:
            return token1, token0
        return None, None
