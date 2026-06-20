"""The mathematical edge model.

Combines flow features, whale/copy signals and mempool signals into a single
expected-edge estimate and a confidence. Strategies use ``edge_score`` for
go/no-go and the risk manager uses it for fractional-Kelly position sizing.

Honesty constraint encoded here: the model is a weighted, bounded blend that can
only ever express modest edge. It does not, and cannot, manufacture edge on an
efficient pair — garbage signals in, near-0.5 score out.
"""
from .flows import flow_features

# Weights sum to 1.0; tuned to be conservative.
_WEIGHTS = {
    "buy_pressure": 0.30,
    "trend": 0.30,
    "volume": 0.15,
    "whale": 0.20,
    "mempool": 0.05,
}


def _squash(x, lo, hi):
    """Linear-clamp x from [lo, hi] into [0, 1]."""
    if hi == lo:
        return 0.5
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def score(snapshot, whale_signal=0.0, mempool_signal=0.0):
    """Return dict with edge_score (0..1), confidence (0..1), expected_edge_pct."""
    flows = flow_features(snapshot)

    buy_component = flows["buy_pressure"]  # already 0..1
    trend_component = _squash(flows["trend_agreement"], -1.0, 1.0)
    volume_component = _squash(flows["volume_accel"], 0.0, 3.0)

    raw = (
        _WEIGHTS["buy_pressure"] * buy_component
        + _WEIGHTS["trend"] * trend_component
        + _WEIGHTS["volume"] * volume_component
        + _WEIGHTS["whale"] * whale_signal
        + _WEIGHTS["mempool"] * mempool_signal
    )

    # Confidence grows with liquidity and trading activity (thin/illiquid == low confidence).
    liq = snapshot.get("liquidity_usd", 0)
    activity = snapshot.get("buys_h1", 0) + snapshot.get("sells_h1", 0)
    confidence = min(1.0, _squash(liq, 0, 100000) * 0.6 + _squash(activity, 0, 50) * 0.4)

    # Translate the 0..1 score into a modest expected edge in percent. Capped small
    # on purpose: an excellent score implies a few percent, never a moonshot.
    expected_edge_pct = (raw - 0.5) * 2 * 4.0  # range roughly [-4%, +4%]

    return {
        "edge_score": round(raw, 4),
        "confidence": round(confidence, 4),
        "expected_edge_pct": round(expected_edge_pct, 4),
        "flows": flows,
    }
