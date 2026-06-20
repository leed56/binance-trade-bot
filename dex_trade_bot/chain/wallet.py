"""Wallet: key handling and signing for live mode.

Hard rules enforced here:
- The private key is read from config (env) only and is never logged.
- Approvals are ALWAYS bounded to the exact amount needed for a trade. We never
  call approve(MAX_UINT256). After an exit, ``revoke_approval`` zeroes any
  leftover allowance.
"""
import time

from ..constants import ERC20_ABI, MAX_UINT256


class Wallet:
    def __init__(self, web3_client, config, logger):
        self.web3_client = web3_client
        self.config = config
        self.logger = logger
        self.account = None
        self.address = config.WALLET_ADDRESS

        if config.is_live:
            self._load_account()

    def _load_account(self):
        from eth_account import Account

        if not self.config.PRIVATE_KEY:
            raise ValueError("Live mode requires PRIVATE_KEY")
        self.account = Account.from_key(self.config.PRIVATE_KEY)
        if self.address and self.account.address.lower() != self.address.lower():
            self.logger.warning("WALLET_ADDRESS does not match PRIVATE_KEY; using key-derived address")
        self.address = self.account.address
        # Never log the key. Only the derived public address.
        self.logger.info(f"Live wallet loaded: {self.address}")

    def _w3(self):
        return self.web3_client.w3

    def _send(self, tx):
        w3 = self._w3()
        tx.setdefault("chainId", w3.eth.chain_id)
        tx.setdefault("nonce", w3.eth.get_transaction_count(self.address))
        tx.setdefault("gasPrice", w3.eth.gas_price)
        signed = self.account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        return receipt

    def ensure_approval(self, token_address, spender, amount_raw):
        """Approve exactly ``amount_raw`` for ``spender`` if current allowance is short.

        Bounded by design — never grants unlimited allowance.
        """
        if amount_raw >= MAX_UINT256:
            raise ValueError("Refusing unbounded approval")
        token = self.web3_client.contract(token_address, ERC20_ABI)
        spender = self.web3_client.checksum(spender)
        current = token.functions.allowance(self.address, spender).call()
        if current >= amount_raw:
            return None
        tx = token.functions.approve(spender, int(amount_raw)).build_transaction(
            {"from": self.address, "gas": 60000}
        )
        self.logger.info(f"Approving {amount_raw} of {token_address} for {spender} (bounded)")
        return self._send(tx)

    def revoke_approval(self, token_address, spender):
        """Zero out any leftover allowance after a position is closed."""
        token = self.web3_client.contract(token_address, ERC20_ABI)
        spender = self.web3_client.checksum(spender)
        current = token.functions.allowance(self.address, spender).call()
        if current == 0:
            return None
        tx = token.functions.approve(spender, 0).build_transaction({"from": self.address, "gas": 60000})
        self.logger.info(f"Revoking leftover allowance for {token_address}")
        return self._send(tx)

    def send_contract_call(self, contract_fn, gas=300000):
        tx = contract_fn.build_transaction(
            {"from": self.address, "gas": gas, "nonce": self._w3().eth.get_transaction_count(self.address)}
        )
        return self._send(tx)

    @staticmethod
    def deadline(seconds=120):
        return int(time.time()) + seconds
