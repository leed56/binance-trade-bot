"""Momentum / trend strategy.

Enters tokens with a confirmed positive trend, healthy buy pressure and a decent
edge score. Rides the move with a trailing stop. Most viable family at small size.
"""
from .base import Intent, Strategy


class Strategy(Strategy):  # noqa: F811  (plugin loader expects class named Strategy)
    name = "momentum"
    take_profit_pct = 30.0
    stop_loss_pct = 12.0
    trailing_stop_pct = 10.0
    max_hold_minutes = 360

    MIN_EDGE_SCORE = 0.60
    MIN_CONFIDENCE = 0.40
    MIN_CHANGE_H1 = 2.0  # percent

    def generate_open_intents(self, scored_candidates):
        intents = []
        for c in scored_candidates:
            snap = c["snapshot"]
            sc = c["score"]
            if sc["edge_score"] < self.MIN_EDGE_SCORE or sc["confidence"] < self.MIN_CONFIDENCE:
                continue
            if snap.get("change_h1", 0) < self.MIN_CHANGE_H1:
                continue
            if sc["flows"]["trend_agreement"] <= 0:
                continue
            intents.append(Intent(
                strategy=self.name, token_address=snap["token_address"], symbol=snap["symbol"],
                price_usd=snap["price_usd"], liquidity_usd=snap["liquidity_usd"],
                expected_edge_pct=sc["expected_edge_pct"], confidence=sc["confidence"],
                buy_tax_pct=c.get("buy_tax_pct", 0.0), sell_tax_pct=c.get("sell_tax_pct", 0.0),
            ))
        return intents
