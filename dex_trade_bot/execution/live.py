"""Live executor: signs and broadcasts real swaps on BSC.

Gated behind EXECUTION_MODE=live and the small MAX_POSITION_USD cap. Uses bounded
approvals only and a hard slippage floor (MAX_SLIPPAGE_BPS) on every swap. Trades
the stable bridge (USDT) into the token and back.

This path is intentionally conservative and is only exercised after paper results
are reviewed (plan phase 4). It reuses the same DB bookkeeping as paper mode.
"""
from datetime import datetime

from ..constants import ROUTER_ABI, USDT
from ..models import Position, PositionState, Trade, TradeSide
from .base import DEFAULT_GAS_USD, FillResult


class LiveExecutor:
    mode = "live"

    def __init__(self, config, web3_client, wallet, pancake, database, logger):
        self.config = config
        self.web3_client = web3_client
        self.wallet = wallet
        self.pancake = pancake
        self.db = database
        self.logger = logger
        self.bridge = USDT

    def _min_out(self, expected_out):
        return expected_out * (1 - self.config.MAX_SLIPPAGE_BPS / 10000.0)

    def _swap(self, token_in, token_out, amount_in_human):
        """Execute a bounded-approval swap; returns (qty_out_human, tx_hash) or (None, None)."""
        wc = self.web3_client
        expected_out = self.pancake.quote_out(token_in, token_out, amount_in_human)
        if not expected_out:
            self.logger.error(f"No quote for {token_in}->{token_out}; aborting swap")
            return None, None

        dec_in = wc.erc20_decimals(token_in)
        dec_out = wc.erc20_decimals(token_out)
        amount_in_raw = int(amount_in_human * 10**dec_in)
        min_out_raw = int(self._min_out(expected_out) * 10**dec_out)

        # Bounded approval for exactly this swap.
        self.wallet.ensure_approval(token_in, self.pancake.router_address, amount_in_raw)

        router = wc.contract(self.pancake.router_address, ROUTER_ABI)
        path = [wc.checksum(p) for p in self.pancake.default_path(token_in, token_out)]
        fn = router.functions.swapExactTokensForTokensSupportingFeeOnTransferTokens(
            amount_in_raw, min_out_raw, path, wc.checksum(self.wallet.address), self.wallet.deadline()
        )
        before = wc.erc20_balance(token_out, self.wallet.address)
        receipt = self.wallet.send_contract_call(fn)
        after = wc.erc20_balance(token_out, self.wallet.address)
        # Clean up any residual allowance.
        self.wallet.revoke_approval(token_in, self.pancake.router_address)
        return after - before, receipt.transactionHash.hex()

    def open_position(self, candidate, size_usd, price_usd, strategy, liquidity_usd, buy_tax_pct=0.0):
        token = candidate["token_address"]
        qty, tx_hash = self._swap(self.bridge, token, size_usd)
        if not qty or qty <= 0:
            return FillResult(False, reason="live buy returned no tokens")
        effective_price = size_usd / qty

        with self.db.db_session() as session:
            position = Position(token_address=token, symbol=candidate.get("symbol", "?"), strategy=strategy,
                                qty=qty, entry_price_usd=price_usd, cost_usd=size_usd + DEFAULT_GAS_USD)
            session.add(position)
            session.flush()
            session.add(Trade(token_address=token, symbol=candidate.get("symbol", "?"), strategy=strategy,
                              side=TradeSide.BUY, qty=qty, price_usd=effective_price, value_usd=size_usd,
                              mode=self.mode, position_id=position.id, gas_usd=DEFAULT_GAS_USD, tx_hash=tx_hash))

        self.logger.info(f"[LIVE] OPEN {candidate.get('symbol','?')} ${size_usd:.2f} tx={tx_hash}",
                         notification=True)
        return FillResult(True, qty=qty, price_usd=effective_price, value_usd=size_usd,
                          gas_usd=DEFAULT_GAS_USD, tx_hash=tx_hash)

    def close_position(self, position, price_usd, liquidity_usd, sell_tax_pct=0.0, reason=""):
        proceeds, tx_hash = self._swap(position.token_address, self.bridge, position.qty)
        if proceeds is None:
            return FillResult(False, reason="live sell failed")
        realized = proceeds - position.cost_usd

        with self.db.db_session() as session:
            row = session.query(Position).get(position.id)
            row.state = PositionState.CLOSED
            row.exit_price_usd = price_usd
            row.proceeds_usd = proceeds
            row.realized_pnl_usd = realized
            row.closed_at = datetime.utcnow()
            session.add(Trade(token_address=row.token_address, symbol=row.symbol, strategy=row.strategy,
                              side=TradeSide.SELL, qty=row.qty, price_usd=price_usd, value_usd=proceeds,
                              mode=self.mode, position_id=row.id, gas_usd=DEFAULT_GAS_USD, tx_hash=tx_hash))

        self.logger.info(f"[LIVE] CLOSE {position.symbol} -> PnL ${realized:+.2f} ({reason}) tx={tx_hash}",
                         notification=True)
        return FillResult(True, qty=position.qty, price_usd=price_usd, value_usd=proceeds,
                          gas_usd=DEFAULT_GAS_USD, tx_hash=tx_hash, reason=reason)
