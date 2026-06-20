"""PancakeSwap V2 router/factory helpers.

Quotes use the router's ``getAmountsOut`` (on-chain) when web3 is connected.
``quote_out`` returns the expected output amount for a given input, which the
executor and arbitrage strategy use to compute realistic slippage.
"""
from ..constants import (
    FACTORY_ABI,
    PANCAKE_V2_FACTORY,
    PANCAKE_V2_ROUTER,
    ROUTER_ABI,
    USDT,
    WBNB,
)


class PancakeSwap:
    def __init__(self, web3_client, logger, router=PANCAKE_V2_ROUTER, factory=PANCAKE_V2_FACTORY, name="pancake"):
        self.web3_client = web3_client
        self.logger = logger
        self.router_address = router
        self.factory_address = factory
        self.name = name

    def _router(self):
        return self.web3_client.contract(self.router_address, ROUTER_ABI)

    def _factory(self):
        return self.web3_client.contract(self.factory_address, FACTORY_ABI)

    def get_pair(self, token_a, token_b):
        return self._factory().functions.getPair(
            self.web3_client.checksum(token_a), self.web3_client.checksum(token_b)
        ).call()

    def default_path(self, token_in, token_out):
        """Route via WBNB unless one side is already a base asset."""
        bases = {WBNB.lower(), USDT.lower()}
        if token_in.lower() in bases or token_out.lower() in bases:
            return [token_in, token_out]
        return [token_in, WBNB, token_out]

    def quote_out(self, token_in, token_out, amount_in_human, path=None):
        """Expected output (human units) for amount_in_human of token_in. None on failure."""
        if not self.web3_client.connected:
            return None
        path = path or self.default_path(token_in, token_out)
        try:
            dec_in = self.web3_client.erc20_decimals(token_in)
            dec_out = self.web3_client.erc20_decimals(token_out)
            amount_in_raw = int(amount_in_human * 10**dec_in)
            checksummed = [self.web3_client.checksum(p) for p in path]
            amounts = self._router().functions.getAmountsOut(amount_in_raw, checksummed).call()
            return amounts[-1] / 10**dec_out
        except Exception as e:  # pylint: disable=broad-except
            self.logger.debug(f"{self.name} quote failed {token_in}->{token_out}: {e}")
            return None
