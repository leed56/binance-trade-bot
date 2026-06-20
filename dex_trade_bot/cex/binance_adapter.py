"""Binance (CEX) price adapter.

Paper mode uses PUBLIC price endpoints — no API key required. Keys are only
needed for live CEX order placement (not used by the monitors). Imports of the
``binance`` client are lazy and failures degrade to ``None`` so the bot runs
without the dependency or network.
"""


class BinanceAdapter:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.client = None
        self._connect()

    def _connect(self):
        try:
            from binance.client import Client

            # Public endpoints work with empty credentials; keys only needed to trade.
            self.client = Client(
                self.config.BINANCE_API_KEY or None,
                self.config.BINANCE_API_SECRET or None,
                tld=self.config.BINANCE_TLD,
            )
            self.logger.info("Binance adapter ready (public prices)")
        except ImportError:
            self.logger.warning("python-binance not installed; CEX prices unavailable")
        except Exception as e:  # pylint: disable=broad-except
            self.logger.warning(f"Binance adapter init failed: {e}")

    @property
    def available(self):
        return self.client is not None

    def price(self, symbol):
        """Spot price for e.g. 'CAKEUSDT'. Returns float or None."""
        if not self.available:
            return None
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker["price"])
        except Exception as e:  # pylint: disable=broad-except
            self.logger.debug(f"Binance price failed for {symbol}: {e}")
            return None

    def taker_fee_pct(self):
        """Conservative default taker fee for cost modelling (0.1%)."""
        return 0.1
