"""Env-first configuration.

Reuses the override idea from binance_trade_bot/config.py but reads everything
from environment variables (loaded from a .env file via python-dotenv when
present). Secrets live only in the environment, never in a committed file.
"""
import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv optional; env may be set by the shell/VPS instead
    pass


def _get(name, default=None):
    val = os.environ.get(name)
    return val if val not in (None, "") else default


def _get_float(name, default):
    return float(_get(name, default))


def _get_int(name, default):
    return int(_get(name, default))


def _get_bool(name, default=False):
    return str(_get(name, str(default))).strip().lower() in ("1", "true", "yes", "on")


def _get_list(name, default=""):
    raw = _get(name, default) or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


class Config:  # pylint: disable=too-many-instance-attributes
    def __init__(self):
        # Wallet
        self.WALLET_ADDRESS = _get("WALLET_ADDRESS", "")
        self.PRIVATE_KEY = _get("PRIVATE_KEY", "")  # only required for live mode

        # Chain
        self.BSC_RPC_URL = _get("BSC_RPC_URL", "https://bsc-dataseed.binance.org")
        self.BSC_WSS_URL = _get("BSC_WSS_URL", "")

        # Execution
        self.EXECUTION_MODE = _get("EXECUTION_MODE", "paper").lower()

        # Risk limits
        self.STARTING_BALANCE_USD = _get_float("STARTING_BALANCE_USD", 30)
        self.MAX_POSITION_USD = _get_float("MAX_POSITION_USD", 5)
        self.MAX_TRADE_PCT = _get_float("MAX_TRADE_PCT", 20)
        self.DAILY_LOSS_STOP_USD = _get_float("DAILY_LOSS_STOP_USD", 8)
        self.MAX_SLIPPAGE_BPS = _get_int("MAX_SLIPPAGE_BPS", 150)
        self.MAX_OPEN_POSITIONS = _get_int("MAX_OPEN_POSITIONS", 3)
        self.MIN_LIQUIDITY_USD = _get_float("MIN_LIQUIDITY_USD", 20000)
        self.MAX_BUY_TAX_PCT = _get_float("MAX_BUY_TAX_PCT", 8)
        self.PER_TOKEN_COOLDOWN_MIN = _get_int("PER_TOKEN_COOLDOWN_MIN", 30)

        # Strategies
        self.ENABLED_STRATEGIES = _get_list("ENABLED_STRATEGIES", "momentum,meanrev,stablegrid")

        # Intelligence
        self.WHALE_WATCHLIST = _get_list("WHALE_WATCHLIST", "")
        self.ENABLE_MEMPOOL_WATCH = _get_bool("ENABLE_MEMPOOL_WATCH", False)

        # Notifications
        self.APPRISE_URL = _get("APPRISE_URL", "")

        # Loop
        self.SCOUT_SLEEP_TIME = _get_int("SCOUT_SLEEP_TIME", 15)

        # Persistence
        self.DB_PATH = _get("DB_PATH", "sqlite:///dex_trading.db")

    @property
    def is_live(self) -> bool:
        return self.EXECUTION_MODE == "live"

    def validate(self):
        """Return a list of human-readable problems; empty list means OK."""
        problems = []
        if self.EXECUTION_MODE not in ("paper", "live"):
            problems.append(f"EXECUTION_MODE must be 'paper' or 'live', got '{self.EXECUTION_MODE}'")
        if self.is_live and not self.PRIVATE_KEY:
            problems.append("EXECUTION_MODE=live requires PRIVATE_KEY to be set")
        if not self.WALLET_ADDRESS:
            problems.append("WALLET_ADDRESS is required (read-only address is enough for paper mode)")
        if self.MAX_TRADE_PCT <= 0 or self.MAX_TRADE_PCT > 100:
            problems.append("MAX_TRADE_PCT must be between 0 and 100")
        return problems
