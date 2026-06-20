"""On-chain flow analytics derived from market-data snapshots.

Honest scope: this turns DexScreener volume/txn/price fields into a normalized
"flow" signal (buy pressure, volume acceleration, trend agreement). It is a
confirmation/rug-avoidance aid, not a crystal ball.
"""


def buy_pressure(snapshot):
    """Fraction of h1 taker flow that is buys, in [0, 1]. 0.5 == balanced."""
    buys = snapshot.get("buys_h1", 0)
    sells = snapshot.get("sells_h1", 0)
    total = buys + sells
    if total == 0:
        return 0.5
    return buys / total


def volume_acceleration(snapshot):
    """h1 volume annualized vs h24 average. >1 means activity is picking up."""
    vol_h1 = snapshot.get("volume_h1", 0)
    vol_h24 = snapshot.get("volume_h24", 0)
    if vol_h24 <= 0:
        return 0.0
    expected_h1 = vol_h24 / 24
    return vol_h1 / expected_h1 if expected_h1 > 0 else 0.0


def trend_agreement(snapshot):
    """+1 if h1/h6/h24 changes all agree in sign, scaled by consistency, else lower."""
    changes = [snapshot.get("change_h1", 0), snapshot.get("change_h6", 0), snapshot.get("change_h24", 0)]
    positives = sum(1 for c in changes if c > 0)
    negatives = sum(1 for c in changes if c < 0)
    if positives == 3:
        return 1.0
    if negatives == 3:
        return -1.0
    return (positives - negatives) / 3.0


def flow_features(snapshot):
    return {
        "buy_pressure": buy_pressure(snapshot),
        "volume_accel": volume_acceleration(snapshot),
        "trend_agreement": trend_agreement(snapshot),
    }
