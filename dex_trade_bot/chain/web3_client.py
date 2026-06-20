"""Thin web3.py wrapper for BSC.

Imports of web3 are lazy so the package (and unit tests / paper logic that don't
touch the chain) can run even when web3 isn't installed or no RPC is reachable.
``connected`` tells callers whether on-chain reads are available.
"""
from functools import lru_cache

from ..constants import ERC20_ABI, PAIR_ABI


class Web3Client:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.w3 = None
        self.connected = False
        self._connect()

    def _connect(self):
        try:
            from web3 import Web3
            from web3.middleware import geth_poa_middleware

            self.w3 = Web3(Web3.HTTPProvider(self.config.BSC_RPC_URL, request_kwargs={"timeout": 15}))
            # BSC uses PoA-style headers; this middleware is required.
            self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            self.connected = self.w3.is_connected()
            if self.connected:
                self.logger.info(f"Connected to BSC RPC (chain id {self.w3.eth.chain_id})")
            else:
                self.logger.warning("BSC RPC did not respond; on-chain reads disabled (HTTP signals still work)")
        except ImportError:
            self.logger.warning("web3 not installed; running in HTTP-only mode (no on-chain reads)")
        except Exception as e:  # pylint: disable=broad-except
            self.logger.warning(f"Could not connect to BSC RPC: {e}")

    def checksum(self, address):
        from web3 import Web3

        return Web3.to_checksum_address(address)

    def contract(self, address, abi):
        return self.w3.eth.contract(address=self.checksum(address), abi=abi)

    @lru_cache(maxsize=2048)
    def erc20_decimals(self, address):
        try:
            return self.contract(address, ERC20_ABI).functions.decimals().call()
        except Exception:  # pylint: disable=broad-except
            return 18

    @lru_cache(maxsize=2048)
    def erc20_symbol(self, address):
        try:
            return self.contract(address, ERC20_ABI).functions.symbol().call()
        except Exception:  # pylint: disable=broad-except
            return "?"

    def erc20_balance(self, token_address, owner):
        raw = self.contract(token_address, ERC20_ABI).functions.balanceOf(self.checksum(owner)).call()
        return raw / (10 ** self.erc20_decimals(token_address))

    def get_reserves(self, pair_address):
        """Return (reserve0, reserve1, token0, token1) as raw integers/addresses."""
        pair = self.contract(pair_address, PAIR_ABI)
        r0, r1, _ = pair.functions.getReserves().call()
        token0 = pair.functions.token0().call()
        token1 = pair.functions.token1().call()
        return r0, r1, token0, token1

    def bnb_price_usd(self):
        """Spot BNB price in USD via the WBNB/USDT pancake pair reserves."""
        from ..constants import PANCAKE_V2_FACTORY, USDT, WBNB, FACTORY_ABI

        factory = self.contract(PANCAKE_V2_FACTORY, FACTORY_ABI)
        pair_addr = factory.functions.getPair(self.checksum(WBNB), self.checksum(USDT)).call()
        r0, r1, token0, _ = self.get_reserves(pair_addr)
        wbnb_dec = self.erc20_decimals(WBNB)
        usdt_dec = self.erc20_decimals(USDT)
        if token0.lower() == WBNB.lower():
            bnb_reserve, usdt_reserve = r0 / 10**wbnb_dec, r1 / 10**usdt_dec
        else:
            usdt_reserve, bnb_reserve = r0 / 10**usdt_dec, r1 / 10**wbnb_dec
        return usdt_reserve / bnb_reserve if bnb_reserve else 0.0
