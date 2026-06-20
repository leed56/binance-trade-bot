from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String

from .base import Base


class TradeSide:
    BUY = "BUY"
    SELL = "SELL"


class Trade(Base):
    """A single executed (or simulated) swap leg."""

    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    position_id = Column(Integer, index=True, nullable=True)
    token_address = Column(String, index=True)
    symbol = Column(String)
    strategy = Column(String)
    side = Column(String)  # BUY | SELL

    qty = Column(Float)  # token units
    price_usd = Column(Float)
    value_usd = Column(Float)  # qty * price before costs
    gas_usd = Column(Float, default=0.0)
    tax_usd = Column(Float, default=0.0)
    slippage_usd = Column(Float, default=0.0)

    mode = Column(String)  # paper | live
    tx_hash = Column(String, default="")  # empty in paper mode
    created_at = Column(DateTime, default=datetime.utcnow)

    def __init__(self, token_address, symbol, strategy, side, qty, price_usd, value_usd, mode, **kwargs):
        self.token_address = token_address
        self.symbol = symbol
        self.strategy = strategy
        self.side = side
        self.qty = qty
        self.price_usd = price_usd
        self.value_usd = value_usd
        self.mode = mode
        for key, value in kwargs.items():
            setattr(self, key, value)
