"""Entrypoint. Mirrors binance_trade_bot/crypto_trading.py and reuses SafeScheduler."""
import time

from .chain.wallet import Wallet
from .chain.web3_client import Web3Client
from .config import Config
from .database import Database
from .dex.pancakeswap import PancakeSwap
from .logger import Logger
from .notifications import Notifications
from .orchestrator import Orchestrator
from .scheduler import SafeScheduler


def build(config=None):
    """Construct the full object graph. Returns (orchestrator, config, logger, db)."""
    logger = Logger()
    config = config or Config()

    problems = config.validate()
    if problems:
        for p in problems:
            logger.error(f"Config error: {p}")
        raise SystemExit(1)

    logger.attach_notifier(Notifications(config, logger))
    logger.info(f"Starting dex_trade_bot in {config.EXECUTION_MODE.upper()} mode", notification=True)
    if config.is_live:
        logger.warning("LIVE MODE: real funds at risk. Caps enforced by the risk manager.")

    db = Database(logger, config)
    db.create_database()

    web3_client = Web3Client(config, logger)
    wallet = Wallet(web3_client, config, logger)
    pancake = PancakeSwap(web3_client, logger)

    orchestrator = Orchestrator(config, db, web3_client, wallet, pancake, logger)
    orchestrator.mempool.start()
    return orchestrator, config, logger, db


def run_once(orchestrator, logger):
    """Execute one full cycle and a PnL snapshot. Used for smoke tests."""
    logger.info("Running a single cycle (--once)")
    orchestrator.discover()
    orchestrator.open_trades()
    orchestrator.manage_positions()
    orchestrator.snapshot_pnl()
    logger.info("Single cycle complete")


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(prog="dex_trade_bot")
    parser.add_argument("--once", action="store_true", help="run a single cycle and exit")
    parser.add_argument("--check", action="store_true",
                        help="run a pre-flight connectivity & config check and exit")
    args = parser.parse_args(argv)

    if args.check:
        from .config import Config
        from .selfcheck import run as run_check

        logger = Logger()
        config = Config()
        _, ready = run_check(config, logger)
        raise SystemExit(0 if ready else 1)

    orchestrator, config, logger, _ = build()

    if args.once:
        try:
            run_once(orchestrator, logger)
        finally:
            orchestrator.mempool.stop()
        return

    schedule = SafeScheduler(logger)
    schedule.every(config.SCOUT_SLEEP_TIME).seconds.do(orchestrator.discover).tag("discovery")
    schedule.every(config.SCOUT_SLEEP_TIME).seconds.do(orchestrator.open_trades).tag("opening")
    schedule.every(max(5, config.SCOUT_SLEEP_TIME)).seconds.do(orchestrator.manage_positions).tag("managing")
    schedule.every(1).minutes.do(orchestrator.snapshot_pnl).tag("pnl")
    schedule.every(6).hours.do(orchestrator.db.prune_candidates).tag("pruning")

    logger.info("Scheduler started")
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    finally:
        orchestrator.mempool.stop()


if __name__ == "__main__":
    main()
