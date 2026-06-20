"""Mean-reversion / range strategy.

Fades short-term deviations on liquid tokens: buys when h1 is down but the longer
trend (h24) is intact and buy pressure is firming, expecting reversion. Tighter
profit target and stop than momentum.
"""
from .base import Intent, Strategy


class Strategy(Strategy):  # noqa: F811
    name = "meanrev"
    take_profit_pct = 8.0
    stop_loss_pct = 6.0
    trailing_stop_pct = 4.0
    max_hold_minutes = 180

    MIN_CONFIDENCE = 0.50
    DIP_H1 = -3.0      # require a short-term dip
    TREND_H24 = 0.0    # but a non-negative longer trend

    def generate_open_intents(self, scored_candidates):
        intents = []
        for c in scored_candidates:
            snap = c["snapshot"]
            sc = c["score"]
            if sc["confidence"] < self.MIN_CONFIDENCE:
                continue
            if snap.get("change_h1", 0) > self.DIP_H1:
                continue  # not dipped enough
            if snap.get("change_h24", 0) < self.TREND_H24:
                continue  # longer trend not intact
            if sc["flows"]["buy_pressure"] < 0.5:
                continue  # want buyers stepping in
            # Reversion edge: expect to recover roughly half the dip.
            expected = abs(snap.get("change_h1", 0)) * 0.5
            intents.append(Intent(
                strategy=self.name, token_address=snap["token_address"], symbol=snap["symbol"],
                price_usd=snap["price_usd"], liquidity_usd=snap["liquidity_usd"],
                expected_edge_pct=expected, confidence=sc["confidence"],
                buy_tax_pct=c.get("buy_tax_pct", 0.0), sell_tax_pct=c.get("sell_tax_pct", 0.0),
            ))
        return intents
