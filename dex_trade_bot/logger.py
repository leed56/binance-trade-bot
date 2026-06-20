"""Logging for the DEX bot.

Mirrors the simple console+file logger style of binance_trade_bot/logger.py but
adds one hard rule: the private key must never reach a log sink. ``Logger.info``
and friends scrub anything that looks like a 64-hex private key before emitting.
"""
import logging
import os
import re

# Matches a 32-byte hex key with or without the 0x prefix.
_PRIVATE_KEY_RE = re.compile(r"(0x)?[0-9a-fA-F]{64}")


def _scrub(message: str) -> str:
    return _PRIVATE_KEY_RE.sub("<redacted-secret>", str(message))


class Logger:
    def __init__(self, logging_service="dex_trade_bot", enable_notifications=True):
        self.Logger = logging.getLogger(f"{logging_service}_logger")
        self.Logger.setLevel(logging.DEBUG)
        self.Logger.propagate = False
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        os.makedirs("logs", exist_ok=True)
        fh = logging.FileHandler(f"logs/{logging_service}.log")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        self.Logger.addHandler(fh)

        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(formatter)
        self.Logger.addHandler(ch)

        self.enable_notifications = enable_notifications
        self.notifier = None  # set by main() once Notifications is built

    def attach_notifier(self, notifier):
        self.notifier = notifier

    def _notify(self, message, notification):
        if notification and self.enable_notifications and self.notifier is not None:
            self.notifier.send_notification(_scrub(message))

    def log(self, message, level="info", notification=False):
        getattr(self.Logger, level)(_scrub(message))
        self._notify(message, notification)

    def info(self, message, notification=False):
        self.log(message, "info", notification)

    def warning(self, message, notification=False):
        self.log(message, "warning", notification)

    def error(self, message, notification=True):
        self.log(message, "error", notification)

    def debug(self, message, notification=False):
        self.log(message, "debug", notification)
