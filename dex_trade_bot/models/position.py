from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String

from .base import Base


class PositionState:
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class Position(Base):
    """An open or closed position in a single token, held against a stable bridge."""

    __tablename__ = "positions"

    id = Column(Integer, primary_key=True)
    token_address = Column(String, index=True)
    symbol = Column(String)
    strategy = Column(String)
    state = Column(String, default=PositionState.OPEN, index=True)

    qty = Column(Float, default=0.0)  # token units held
    entry_price_usd = Column(Float, default=0.0)
    cost_usd = Column(Float, default=0.0)  # what we paid incl. fees/tax/slippage
    high_water_price = Column(Float, default=0.0)  # for trailing stop

    exit_price_usd = Column(Float, default=0.0)
    proceeds_usd = Column(Float, default=0.0)
    realized_pnl_usd = Column(Float, default=0.0)

    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    def __init__(self, token_address, symbol, strategy, qty, entry_price_usd, cost_usd):
        self.token_address = token_address
        self.symbol = symbol
        self.strategy = strategy
        self.qty = qty
        self.entry_price_usd = entry_price_usd
        self.cost_usd = cost_usd
        self.high_water_price = entry_price_usd
        self.state = PositionState.OPEN

    def unrealized_pnl_usd(self, current_price_usd):
        return self.qty * current_price_usd - self.cost_usd
