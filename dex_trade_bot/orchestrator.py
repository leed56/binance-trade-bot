"""Orchestrator: coordinates the cooperating agents on a scheduled loop.

Cycle responsibilities:
  - discover()        : gather candidates (trending + new pairs)
  - screen + score    : run the safety gate and intel scoring -> scored candidates
  - open_trades()     : strategies -> intents -> risk gate -> executor
  - manage_positions(): trailing/stop/take-profit/time exits per strategy
  - snapshot_pnl()    : record the account value curve

These run as separate scheduled jobs (see __main__.py), mirroring the
job-per-concern style of binance_trade_bot/crypto_trading.py.
"""
import time
from datetime import datetime

from .dex import marketdata
from .dex.aggregator import Aggregator
from .execution import get_executor
from .execution.base import all_in_cost_pct
from .intel import scoring
from .intel.mempool import MempoolWatcher
from .intel.whales import WhaleTracker
from .models import PnLSnapshot
from .safety.screener import Screener
from .strategies import load_enabled

_SCREEN_TTL_SECONDS = 600  # cache screen results to respect honeypot API limits


class Orchestrator:
    def __init__(self, config, database, web3_client, wallet, pancake, logger):
        self.config = config
        self.db = database
        self.web3_client = web3_client
        self.wallet = wallet
        self.pancake = pancake
        self.logger = logger

        self.screener = Screener(config, logger)
        self.whales = WhaleTracker(web3_client, config, logger)
        self.mempool = MempoolWatcher(config, logger)
        self.aggregator = Aggregator(web3_client, logger) if web3_client.connected else None
        self.executor = get_executor(config, web3_client, wallet, pancake, database, logger)
        self.strategies = load_enabled(config.ENABLED_STRATEGIES, config, logger)
        self._inject_dependencies()

        # discovery providers (imported here to avoid a hard web3 dependency at import time)
        from .discovery.new_pairs import NewPairsDiscovery
        from .discovery.trending import TrendingDiscovery

        self.trending = TrendingDiscovery(config, logger)
        self.new_pairs = NewPairsDiscovery(web3_client, config, logger)

        self._screen_cache = {}  # token -> (timestamp, ScreenResult)
        self._scored = []        # latest scored candidates
        self.strategy_by_name = {s.name: s for s in self.strategies}

    def _inject_dependencies(self):
        for s in self.strategies:
            if s.name == "arbitrage":
                s.aggregator = self.aggregator
            if s.name == "stablegrid":
                s.pancake = self.pancake
                s.web3_client = self.web3_client

    # --- cash / accounting -------------------------------------------------
    def cash_usd(self):
        invested = sum(p.cost_usd for p in self.db.open_positions())
        return self.config.STARTING_BALANCE_USD + self.db.realized_pnl() - invested

    # --- discovery + screening + scoring -----------------------------------
    def discover(self):
        raw = []
        for snap in self.trending.discover(limit=30):
            raw.append({"token_address": snap["token_address"], "source": "trending", "snapshot": snap})
        for c in self.new_pairs.discover():
            raw.append({"token_address": c["token_address"], "source": "new_pairs", "snapshot": None})

        scored = []
        for item in raw:
            snap = item["snapshot"] or marketdata.token_market(item["token_address"])
            if not snap or snap.get("price_usd", 0) <= 0:
                continue
            screen = self._screen(item["token_address"], snap["liquidity_usd"])
            if not screen.passed:
                continue
            whale_sig = self.whales.copy_signal(item["token_address"]) if self.whales.enabled else 0.0
            mem_sig = self.mempool.signal(item["token_address"]) if self.mempool.enabled else 0.0
            sc = scoring.score(snap, whale_signal=whale_sig, mempool_signal=mem_sig)
            scored.append({
                "snapshot": snap, "score": sc, "source": item["source"],
                "buy_tax_pct": screen.buy_tax_pct, "sell_tax_pct": screen.sell_tax_pct,
            })
        self._scored = scored
        self.logger.info(f"Discovery: {len(scored)} screened+scored candidates")
        return scored

    def _screen(self, token_address, liquidity_usd):
        cached = self._screen_cache.get(token_address)
        if cached and (time.time() - cached[0]) < _SCREEN_TTL_SECONDS:
            return cached[1]
        result = self.screener.screen(token_address, liquidity_usd)
        self._screen_cache[token_address] = (time.time(), result)
        if not result.passed:
            self.logger.debug(f"Screen rejected {token_address}: {result.reason}")
        return result

    # --- opening trades ----------------------------------------------------
    def open_trades(self):
        halted, why = self._risk().trading_halted()
        if halted:
            self.logger.info(f"Trading halted: {why}")
            return
        for strategy in self.strategies:
            try:
                intents = strategy.generate_open_intents(self._scored)
            except Exception as e:  # pylint: disable=broad-except
                self.logger.error(f"{strategy.name} intent generation failed: {e}")
                continue
            for intent in intents:
                self._try_open(intent)

    def _try_open(self, intent):
        cash = self.cash_usd()
        est_cost_pct = all_in_cost_pct(
            min(self.config.MAX_POSITION_USD, cash), intent.liquidity_usd,
            intent.buy_tax_pct + intent.sell_tax_pct,
        )
        decision = self._risk().evaluate_open(
            intent.as_candidate(), cash, intent.expected_edge_pct, est_cost_pct
        )
        if not decision.approved:
            self.logger.debug(f"Risk vetoed {intent.symbol} ({intent.strategy}): {decision.reason}")
            return
        self.executor.open_position(
            intent.as_candidate(), decision.size_usd,
            intent.price_usd, intent.strategy, intent.liquidity_usd, intent.buy_tax_pct,
        )

    # --- managing open positions -------------------------------------------
    def manage_positions(self):
        for position in self.db.open_positions():
            strategy = self.strategy_by_name.get(position.strategy)
            if strategy is None:
                continue
            snapshot = marketdata.token_market(position.token_address)
            self._update_high_water(position, snapshot, strategy)
            try:
                exit_now, reason = strategy.should_exit(position, snapshot or {})
            except Exception as e:  # pylint: disable=broad-except
                self.logger.error(f"should_exit failed for {position.symbol}: {e}")
                continue
            if exit_now:
                price = strategy.reference_price(position, snapshot)
                liq = strategy.reference_liquidity(position, snapshot)
                self.executor.close_position(position, price, liq,
                                             sell_tax_pct=0.0, reason=reason)

    def _update_high_water(self, position, snapshot, strategy):
        price = strategy.reference_price(position, snapshot)
        if price and price > position.high_water_price:
            with self.db.db_session() as session:
                from .models import Position as P

                row = session.query(P).get(position.id)
                row.high_water_price = price

    # --- pnl ---------------------------------------------------------------
    def snapshot_pnl(self):
        positions = self.db.open_positions()
        mtm = 0.0
        for p in positions:
            strategy = self.strategy_by_name.get(p.strategy)
            snap = marketdata.token_market(p.token_address) if strategy else None
            price = strategy.reference_price(p, snap) if strategy else p.entry_price_usd
            mtm += p.qty * (price or p.entry_price_usd)
        cash = self.cash_usd()
        with self.db.db_session() as session:
            session.add(PnLSnapshot(cash, mtm, self.db.realized_pnl(), len(positions)))
        self.logger.info(
            f"PnL snapshot: cash ${cash:.2f} + positions ${mtm:.2f} = ${cash + mtm:.2f} "
            f"| realized ${self.db.realized_pnl():+.2f} | open {len(positions)}")

    def _risk(self):
        # Lazily created so it picks up the live DB each call cheaply.
        if not hasattr(self, "_risk_manager"):
            from .risk.manager import RiskManager

            self._risk_manager = RiskManager(self.config, self.db, self.logger)
        return self._risk_manager
