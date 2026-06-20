"""Venus Protocol (BSC) liquidation monitor.

Checks watched accounts' account liquidity via the comptroller. An account with a
positive ``shortfall`` is undercollateralized and liquidatable.

Honest scope at $30: this is a MONITOR. Actually capturing a liquidation requires
capital to repay the borrower's debt (you receive seized collateral + bonus), and
the space is dominated by funded, gas-competitive bots. We surface opportunities
and log them; we do not pretend $30 can win them. Discovering the full borrower set
on-chain is heavy, so accounts are supplied via VENUS_WATCH_ACCOUNTS (or wired from
an external indexer later).
"""
from ..constants import VENUS_COMPTROLLER, VENUS_COMPTROLLER_ABI


class VenusMonitor:
    def __init__(self, web3_client, config, logger):
        self.web3_client = web3_client
        self.config = config
        self.logger = logger
        self.accounts = config.VENUS_WATCH_ACCOUNTS

    @property
    def enabled(self):
        return bool(self.accounts) and self.web3_client.connected

    def _comptroller(self):
        return self.web3_client.contract(VENUS_COMPTROLLER, VENUS_COMPTROLLER_ABI)

    def account_shortfall_usd(self, account):
        """Return shortfall in USD (Venus returns 1e18-scaled USD), or None on error."""
        try:
            error, _liquidity, shortfall = self._comptroller().functions.getAccountLiquidity(
                self.web3_client.checksum(account)
            ).call()
            if error != 0:
                return None
            return shortfall / 1e18
        except Exception as e:  # pylint: disable=broad-except
            self.logger.debug(f"Venus liquidity check failed for {account}: {e}")
            return None

    def scan(self):
        """Return a list of {account, shortfall_usd} for liquidatable watched accounts."""
        if not self.enabled:
            return []
        opportunities = []
        for account in self.accounts:
            shortfall = self.account_shortfall_usd(account)
            if shortfall and shortfall > 0:
                self.logger.info(f"[VENUS-MONITOR] {account} liquidatable: shortfall ${shortfall:,.2f}")
                opportunities.append({"account": account, "shortfall_usd": shortfall})
        return opportunities
