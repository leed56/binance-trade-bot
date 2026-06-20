"""Shared execution cost model.

Both the paper and live executors price a trade the same way so paper results are
a faithful preview of live behaviour: gas + token tax + AMM slippage.
"""
from dataclasses import dataclass

# Flat BSC gas estimate per swap, in USD. BSC gas is cheap and fairly stable.
DEFAULT_GAS_USD = 0.20


@dataclass
class FillResult:
    success: bool
    qty: float = 0.0          # token units transacted
    price_usd: float = 0.0    # effective price after slippage
    value_usd: float = 0.0    # gross notional
    gas_usd: float = 0.0
    tax_usd: float = 0.0
    slippage_usd: float = 0.0
    tx_hash: str = ""
    reason: str = ""

    @property
    def net_cost_usd(self):
        return self.gas_usd + self.tax_usd + self.slippage_usd


def estimate_slippage_pct(size_usd, liquidity_usd):
    """Constant-product price impact approximation for a size against pool depth.

    For an x*y=k pool, buying with `size` of one side moves price by roughly
    size/liquidity (small-trade regime). Doubled here as a conservative guard for
    the round-trip and depth concentration.
    """
    if liquidity_usd <= 0:
        return 100.0
    return min(100.0, (size_usd / liquidity_usd) * 100.0 * 2.0)


def all_in_cost_pct(size_usd, liquidity_usd, tax_pct, gas_usd=DEFAULT_GAS_USD):
    """Total round-trip-ish cost as a percent of size: slippage + tax + gas."""
    if size_usd <= 0:
        return 100.0
    slippage_pct = estimate_slippage_pct(size_usd, liquidity_usd)
    gas_pct = gas_usd / size_usd * 100.0
    return slippage_pct + tax_pct + gas_pct
