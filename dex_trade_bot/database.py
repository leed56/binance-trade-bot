"""Persistence layer.

Reuses the session-context pattern from binance_trade_bot/database.py: a
``db_session`` contextmanager that commits on success and rolls back on error.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta

from sqlalchemy import create_engine, func
from sqlalchemy.orm import scoped_session, sessionmaker

from .models import Base, Candidate, PnLSnapshot, Position, PositionState, Trade


class Database:
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        self.engine = create_engine(config.DB_PATH)
        self.SessionMaker = scoped_session(sessionmaker(bind=self.engine))

    def create_database(self):
        Base.metadata.create_all(self.engine)

    @contextmanager
    def db_session(self):
        session = self.SessionMaker()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # --- positions ---------------------------------------------------------
    def open_positions(self):
        with self.db_session() as session:
            rows = session.query(Position).filter(Position.state == PositionState.OPEN).all()
            session.expunge_all()
            return rows

    def get_open_position(self, token_address):
        with self.db_session() as session:
            row = (
                session.query(Position)
                .filter(Position.state == PositionState.OPEN, Position.token_address == token_address)
                .first()
            )
            if row is not None:
                session.expunge(row)
            return row

    def count_open_positions(self):
        with self.db_session() as session:
            return session.query(Position).filter(Position.state == PositionState.OPEN).count()

    def realized_pnl(self):
        with self.db_session() as session:
            total = session.query(func.sum(Position.realized_pnl_usd)).filter(
                Position.state == PositionState.CLOSED
            ).scalar()
            return total or 0.0

    def realized_pnl_since(self, since: datetime):
        with self.db_session() as session:
            total = session.query(func.sum(Position.realized_pnl_usd)).filter(
                Position.state == PositionState.CLOSED, Position.closed_at >= since
            ).scalar()
            return total or 0.0

    def last_trade_time(self, token_address):
        with self.db_session() as session:
            row = (
                session.query(Trade)
                .filter(Trade.token_address == token_address)
                .order_by(Trade.created_at.desc())
                .first()
            )
            return row.created_at if row else None

    # --- candidates --------------------------------------------------------
    def save_candidate(self, candidate: Candidate):
        with self.db_session() as session:
            session.add(candidate)

    def prune_candidates(self, hours=24):
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        with self.db_session() as session:
            session.query(Candidate).filter(Candidate.created_at < cutoff).delete()
