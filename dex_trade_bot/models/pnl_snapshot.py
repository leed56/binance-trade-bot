from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer

from .base import Base


class PnLSnapshot(Base):
    """Periodic snapshot of total account value, for a PnL curve."""

    __tablename__ = "pnl_snapshots"

    id = Column(Integer, primary_key=True)
    cash_usd = Column(Float)  # uninvested stable balance
    positions_value_usd = Column(Float)  # mark-to-market of open positions
    total_value_usd = Column(Float)
    realized_pnl_usd = Column(Float)
    open_positions = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __init__(self, cash_usd, positions_value_usd, realized_pnl_usd, open_positions):
        self.cash_usd = cash_usd
        self.positions_value_usd = positions_value_usd
        self.total_value_usd = cash_usd + positions_value_usd
        self.realized_pnl_usd = realized_pnl_usd
        self.open_positions = open_positions
