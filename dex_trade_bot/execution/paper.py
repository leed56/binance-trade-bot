"""Paper executor: simulates fills against live quotes, no signing, no funds.

Applies the shared cost model (gas + tax + slippage) so a paper PnL curve is a
realistic preview of live performance. Writes Position and Trade rows exactly
like the live executor would.
"""
from datetime import datetime

from ..models import Position, PositionState, Trade, TradeSide
from .base import DEFAULT_GAS_USD, FillResult, estimate_slippage_pct


class PaperExecutor:
    mode = "paper"

    def __init__(self, config, web3_client, pancake, database, logger):
        self.config = config
        self.web3_client = web3_client
        self.pancake = pancake
        self.db = database
        self.logger = logger

    def open_position(self, candidate, size_usd, price_usd, strategy, liquidity_usd, buy_tax_pct=0.0):
        slippage_pct = estimate_slippage_pct(size_usd, liquidity_usd)
        slippage_usd = size_usd * slippage_pct / 100.0
        tax_usd = size_usd * buy_tax_pct / 100.0
        gas_usd = DEFAULT_GAS_USD

        # Tokens actually received after slippage+tax are deducted from the notional.
        effective_spend = size_usd - slippage_usd - tax_usd
        if effective_spend <= 0 or price_usd <= 0:
            return FillResult(False, reason="non-positive effective spend")
        qty = effective_spend / price_usd
        effective_price = (size_usd) / qty if qty else price_usd  # cost basis per token incl. costs

        with self.db.db_session() as session:
            position = Position(
                token_address=candidate["token_address"],
                symbol=candidate.get("symbol", "?"),
                strategy=strategy,
                qty=qty,
                entry_price_usd=price_usd,
                cost_usd=size_usd + gas_usd,
            )
            session.add(position)
            session.flush()
            session.add(Trade(
                token_address=candidate["token_address"], symbol=candidate.get("symbol", "?"),
                strategy=strategy, side=TradeSide.BUY, qty=qty, price_usd=price_usd,
                value_usd=size_usd, mode=self.mode, position_id=position.id,
                gas_usd=gas_usd, tax_usd=tax_usd, slippage_usd=slippage_usd,
            ))

        self.logger.info(
            f"[PAPER] OPEN {candidate.get('symbol','?')} {strategy} ${size_usd:.2f} @ {price_usd:.6g} "
            f"(slip ${slippage_usd:.3f}, tax ${tax_usd:.3f})", notification=True)
        return FillResult(True, qty=qty, price_usd=effective_price, value_usd=size_usd,
                          gas_usd=gas_usd, tax_usd=tax_usd, slippage_usd=slippage_usd)

    def close_position(self, position, price_usd, liquidity_usd, sell_tax_pct=0.0, reason=""):
        gross = position.qty * price_usd
        slippage_pct = estimate_slippage_pct(gross, liquidity_usd)
        slippage_usd = gross * slippage_pct / 100.0
        tax_usd = gross * sell_tax_pct / 100.0
        gas_usd = DEFAULT_GAS_USD
        proceeds = gross - slippage_usd - tax_usd - gas_usd
        realized = proceeds - position.cost_usd

        with self.db.db_session() as session:
            row = session.query(Position).get(position.id)
            row.state = PositionState.CLOSED
            row.exit_price_usd = price_usd
            row.proceeds_usd = proceeds
            row.realized_pnl_usd = realized
            row.closed_at = datetime.utcnow()
            session.add(Trade(
                token_address=row.token_address, symbol=row.symbol, strategy=row.strategy,
                side=TradeSide.SELL, qty=row.qty, price_usd=price_usd, value_usd=gross,
                mode=self.mode, position_id=row.id, gas_usd=gas_usd, tax_usd=tax_usd,
                slippage_usd=slippage_usd,
            ))

        self.logger.info(
            f"[PAPER] CLOSE {position.symbol} @ {price_usd:.6g} -> PnL ${realized:+.2f} ({reason})",
            notification=True)
        return FillResult(True, qty=position.qty, price_usd=price_usd, value_usd=gross,
                          gas_usd=gas_usd, tax_usd=tax_usd, slippage_usd=slippage_usd, reason=reason)
