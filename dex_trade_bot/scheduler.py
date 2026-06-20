"""SafeScheduler: a Scheduler that logs job exceptions and keeps running.

Same pattern as binance_trade_bot/scheduler.py, vendored here so the DEX bot has
no import-time dependency on the CEX package's __init__ (and its extra deps).
"""
import datetime
import logging
from traceback import format_exc

from schedule import Job, Scheduler


class SafeScheduler(Scheduler):
    def __init__(self, logger, rerun_immediately=True):
        self.logger = logger
        self.rerun_immediately = rerun_immediately
        super().__init__()

    def _run_job(self, job: Job):
        try:
            super()._run_job(job)
        except Exception:  # pylint: disable=broad-except
            self.logger.error(f"Error while {next(iter(job.tags))}...\n{format_exc()}")
            job.last_run = datetime.datetime.now()
            if not self.rerun_immediately:
                job._schedule_next_run()  # pylint: disable=protected-access


# logging import kept for parity with the original (callers may pass a std logger)
_ = logging
