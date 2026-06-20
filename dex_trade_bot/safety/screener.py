"""The screening gate. No token reaches a strategy without passing this.

Checks (cheapest first, fail fast):
  1. Liquidity floor          (MIN_LIQUIDITY_USD)
  2. Honeypot + tax           (honeypot.is API; can-sell? buy/sell tax)
  3. Buy-tax cap              (MAX_BUY_TAX_PCT)

honeypot.is is BSC-aware and free. If it's unreachable we FAIL CLOSED (reject),
because trading an unscreened token is exactly the catastrophic case the rails
exist to prevent.
"""
from dataclasses import dataclass

import requests

HONEYPOT_API = "https://api.honeypot.is/v2/IsHoneypot?address={address}&chainID=56"
_TIMEOUT = 12


@dataclass
class ScreenResult:
    passed: bool
    reason: str = ""
    buy_tax_pct: float = 0.0
    sell_tax_pct: float = 0.0
    is_honeypot: bool = False


class Screener:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    def screen(self, token_address, liquidity_usd) -> ScreenResult:
        if liquidity_usd < self.config.MIN_LIQUIDITY_USD:
            return ScreenResult(False, f"liquidity ${liquidity_usd:,.0f} < floor ${self.config.MIN_LIQUIDITY_USD:,.0f}")

        hp = self._honeypot_check(token_address)
        if hp is None:
            return ScreenResult(False, "honeypot API unreachable (fail-closed)")

        if hp["is_honeypot"]:
            return ScreenResult(False, f"honeypot: {hp['reason']}", hp["buy_tax"], hp["sell_tax"], True)

        if hp["buy_tax"] > self.config.MAX_BUY_TAX_PCT:
            return ScreenResult(False, f"buy tax {hp['buy_tax']:.1f}% > max {self.config.MAX_BUY_TAX_PCT:.1f}%",
                                hp["buy_tax"], hp["sell_tax"])

        if hp["sell_tax"] > self.config.MAX_BUY_TAX_PCT:
            return ScreenResult(False, f"sell tax {hp['sell_tax']:.1f}% > max {self.config.MAX_BUY_TAX_PCT:.1f}%",
                                hp["buy_tax"], hp["sell_tax"])

        return ScreenResult(True, "ok", hp["buy_tax"], hp["sell_tax"])

    def _honeypot_check(self, token_address):
        try:
            resp = requests.get(HONEYPOT_API.format(address=token_address), timeout=_TIMEOUT,
                                headers={"User-Agent": "dex-trade-bot/1.0"})
            if resp.status_code != 200:
                return None
            data = resp.json()
        except (requests.RequestException, ValueError):
            return None

        hp_result = data.get("honeypotResult") or {}
        sim = data.get("simulationResult") or {}
        return {
            "is_honeypot": bool(hp_result.get("isHoneypot", True)),  # default True = treat unknown as unsafe
            "reason": hp_result.get("honeypotReason", "unknown"),
            "buy_tax": float(sim.get("buyTax", 0) or 0),
            "sell_tax": float(sim.get("sellTax", 0) or 0),
        }
