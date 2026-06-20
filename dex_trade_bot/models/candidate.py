from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String

from .base import Base


class Candidate(Base):
    """A token/pool surfaced by the discovery agent and scored by intel/screening."""

    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True)
    token_address = Column(String, index=True)
    symbol = Column(String)
    source = Column(String)  # new_pairs | trending | whale | mempool
    liquidity_usd = Column(Float)
    price_usd = Column(Float)

    # screening outcome
    passed_screen = Column(Boolean, default=False)
    screen_reason = Column(String, default="")
    buy_tax_pct = Column(Float, default=0.0)
    sell_tax_pct = Column(Float, default=0.0)

    # intel scores (0..1)
    edge_score = Column(Float, default=0.0)
    confidence = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)

    def __init__(self, token_address, symbol, source, **kwargs):
        self.token_address = token_address
        self.symbol = symbol
        self.source = source
        for key, value in kwargs.items():
            setattr(self, key, value)
