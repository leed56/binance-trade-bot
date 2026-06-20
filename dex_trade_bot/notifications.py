"""Apprise-based notifications (optional).

Same approach as binance_trade_bot/notifications.py: if an APPRISE_URL is
configured, route messages out; otherwise no-op.
"""


class Notifications:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.apobj = None
        if config.APPRISE_URL:
            try:
                import apprise

                self.apobj = apprise.Apprise()
                self.apobj.add(config.APPRISE_URL)
            except ImportError:
                pass

    def send_notification(self, message):
        if self.apobj is not None:
            try:
                self.apobj.notify(body=str(message), title="dex_trade_bot")
            except Exception:  # pylint: disable=broad-except
                pass
