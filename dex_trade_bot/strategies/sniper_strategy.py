"""New-pair sniper strategy.

Acts only on freshly discovered pairs (source == new_pairs) that passed the strict
screen and show rising liquidity. Highest risk family: smallest size, aggressive
trailing stop, short time stop. Screening already removed honeypots/high-tax tokens.
"""
from .base import Intent, Strategy


class Strategy(Strategy):  # noqa: F811
    name = "sniper"
    take_profit_pct = 50.0
    stop_loss_pct = 18.0
    trailing_stop_pct = 15.0
    max_hold_minutes = 90

    MIN_CONFIDENCE = 0.30  # fresh pairs have thin history; confidence is inherently lower

    def generate_open_intents(self, scored_candidates):
        intents = []
        for c in scored_candidates:
            snap = c["snapshot"]
            sc = c["score"]
            if c.get("source") != "new_pairs":
                continue
            if sc["confidence"] < self.MIN_CONFIDENCE:
                continue
            if sc["flows"]["buy_pressure"] < 0.55:
                continue  # demand must outweigh selling on a fresh pair
            intents.append(Intent(
                strategy=self.name, token_address=snap["token_address"], symbol=snap["symbol"],
                price_usd=snap["price_usd"], liquidity_usd=snap["liquidity_usd"],
                expected_edge_pct=max(sc["expected_edge_pct"], 6.0), confidence=sc["confidence"],
                buy_tax_pct=c.get("buy_tax_pct", 0.0), sell_tax_pct=c.get("sell_tax_pct", 0.0),
            ))
        return intents
