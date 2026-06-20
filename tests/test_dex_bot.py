"""Unit tests for the dex_trade_bot package.

These cover the deterministic core that needs no network: cost math, the screener
gate decisions, risk-manager vetoes, intel scoring bounds, and paper-fill PnL
accounting against an in-memory SQLite DB.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dex_trade_bot.config import Config
from dex_trade_bot.database import Database
from dex_trade_bot.execution.base import all_in_cost_pct, estimate_slippage_pct
from dex_trade_bot.execution.paper import PaperExecutor
from dex_trade_bot.intel import scoring
from dex_trade_bot.risk.manager import RiskManager
from dex_trade_bot.safety.screener import ScreenResult, Screener


class DummyLogger:
    def info(self, *a, **k):
        pass

    warning = debug = error = info


def make_config(**overrides):
    for key in list(os.environ):
        if key in ("EXECUTION_MODE",):
            del os.environ[key]
    os.environ["WALLET_ADDRESS"] = "0x0000000000000000000000000000000000000001"
    os.environ["EXECUTION_MODE"] = "paper"
    os.environ["DB_PATH"] = "sqlite:///:memory:"
    cfg = Config()
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def make_db(cfg):
    db = Database(DummyLogger(), cfg)
    db.create_database()
    return db


# --- cost model ------------------------------------------------------------
def test_slippage_grows_with_size():
    assert estimate_slippage_pct(10, 100000) < estimate_slippage_pct(1000, 100000)


def test_slippage_zero_liquidity_is_max():
    assert estimate_slippage_pct(10, 0) == 100.0


def test_all_in_cost_includes_tax_and_gas():
    cost = all_in_cost_pct(size_usd=5, liquidity_usd=50000, tax_pct=3.0, gas_usd=0.2)
    # tax 3% + gas (0.2/5=4%) + small slippage
    assert cost > 7.0


# --- screener --------------------------------------------------------------
def test_screener_rejects_thin_liquidity():
    cfg = make_config(MIN_LIQUIDITY_USD=20000)
    res = Screener(cfg, DummyLogger()).screen("0xabc", liquidity_usd=1000)
    assert not res.passed
    assert "liquidity" in res.reason


def test_screen_result_shape():
    r = ScreenResult(True, "ok", 1.0, 2.0)
    assert r.passed and r.buy_tax_pct == 1.0


# --- scoring ---------------------------------------------------------------
def test_score_bounds():
    snap = {"liquidity_usd": 50000, "buys_h1": 30, "sells_h1": 10, "volume_h1": 1000,
            "volume_h24": 12000, "change_h1": 5, "change_h6": 8, "change_h24": 10}
    out = scoring.score(snap, whale_signal=1.0, mempool_signal=1.0)
    assert 0.0 <= out["edge_score"] <= 1.0
    assert 0.0 <= out["confidence"] <= 1.0
    assert -4.001 <= out["expected_edge_pct"] <= 4.001


def test_score_neutral_for_flat_market():
    snap = {"liquidity_usd": 0, "buys_h1": 0, "sells_h1": 0, "volume_h1": 0,
            "volume_h24": 0, "change_h1": 0, "change_h6": 0, "change_h24": 0}
    out = scoring.score(snap)
    assert out["confidence"] == 0.0


# --- risk manager ----------------------------------------------------------
def test_risk_vetoes_when_edge_below_cost():
    cfg = make_config()
    db = make_db(cfg)
    rm = RiskManager(cfg, db, DummyLogger())
    candidate = {"token_address": "0xtok", "symbol": "TOK"}
    d = rm.evaluate_open(candidate, cash_usd=30, expected_edge_pct=1.0, est_cost_pct=5.0)
    assert not d.approved
    assert "edge" in d.reason


def test_risk_approves_and_caps_size():
    cfg = make_config(MAX_POSITION_USD=5, MAX_TRADE_PCT=50)
    db = make_db(cfg)
    rm = RiskManager(cfg, db, DummyLogger())
    candidate = {"token_address": "0xtok", "symbol": "TOK"}
    d = rm.evaluate_open(candidate, cash_usd=30, expected_edge_pct=20.0, est_cost_pct=3.0)
    assert d.approved
    assert d.size_usd <= 5.0  # capped by MAX_POSITION_USD


def test_daily_loss_stop_halts():
    cfg = make_config(DAILY_LOSS_STOP_USD=8)
    db = make_db(cfg)
    rm = RiskManager(cfg, db, DummyLogger())
    rm._day_start_realized = 0.0
    # simulate a realized loss by monkeypatching the db reader
    db.realized_pnl = lambda: -9.0
    halted, _ = rm.trading_halted()
    assert halted


# --- paper executor PnL accounting -----------------------------------------
def test_paper_roundtrip_pnl_with_costs():
    cfg = make_config()
    db = make_db(cfg)
    ex = PaperExecutor(cfg, web3_client=None, pancake=None, database=db, logger=DummyLogger())
    candidate = {"token_address": "0xtok", "symbol": "TOK"}
    fill = ex.open_position(candidate, size_usd=5.0, price_usd=1.0, strategy="momentum",
                            liquidity_usd=100000, buy_tax_pct=1.0)
    assert fill.success
    pos = db.get_open_position("0xtok")
    assert pos is not None
    # Exit flat: should be a small loss due to gas + tax + slippage both ways.
    ex.close_position(pos, price_usd=1.0, liquidity_usd=100000, sell_tax_pct=1.0, reason="test")
    assert db.count_open_positions() == 0
    assert db.realized_pnl() < 0  # costs make a flat round-trip a loss


def test_paper_profit_when_price_rises_enough():
    cfg = make_config()
    db = make_db(cfg)
    ex = PaperExecutor(cfg, web3_client=None, pancake=None, database=db, logger=DummyLogger())
    candidate = {"token_address": "0xtok2", "symbol": "TOK2"}
    ex.open_position(candidate, size_usd=5.0, price_usd=1.0, strategy="momentum",
                     liquidity_usd=1_000_000, buy_tax_pct=0.0)
    pos = db.get_open_position("0xtok2")
    ex.close_position(pos, price_usd=2.0, liquidity_usd=1_000_000, sell_tax_pct=0.0, reason="tp")
    assert db.realized_pnl() > 0


# --- orchestrator end-to-end (offline, with fakes) -------------------------
def _strong_snapshot(addr="0xPIPE", price=1.0):
    return {"token_address": addr, "symbol": "PIPE", "pair_address": "0xpair", "dex": "pancake",
            "price_usd": price, "liquidity_usd": 50000, "volume_h24": 2400, "volume_h1": 1000,
            "change_h1": 5.0, "change_h6": 8.0, "change_h24": 10.0, "buys_h1": 40, "sells_h1": 5,
            "pair_created_at": 0}


def test_orchestrator_full_pipeline(monkeypatch):
    import types

    from dex_trade_bot import orchestrator as orch_mod
    from dex_trade_bot.orchestrator import Orchestrator
    from dex_trade_bot.safety.screener import ScreenResult

    # Larger budget here purely to clear the gas-vs-edge guard and exercise a fill.
    cfg = make_config(STARTING_BALANCE_USD=100, MAX_POSITION_USD=20, MAX_TRADE_PCT=50,
                      ENABLED_STRATEGIES=["momentum"])
    db = make_db(cfg)
    fake_web3 = types.SimpleNamespace(connected=False, w3=None)
    wallet = types.SimpleNamespace(address=cfg.WALLET_ADDRESS)
    pancake = types.SimpleNamespace()

    orch = Orchestrator(cfg, db, fake_web3, wallet, pancake, DummyLogger())
    orch.trending = types.SimpleNamespace(discover=lambda limit=30: [_strong_snapshot()])
    orch.new_pairs = types.SimpleNamespace(discover=lambda: [])
    orch.screener.screen = lambda addr, liq: ScreenResult(True, "ok", 0.0, 0.0)

    # 1) discovery -> screened + scored
    scored = orch.discover()
    assert len(scored) == 1
    assert scored[0]["score"]["edge_score"] >= 0.6

    # 2) strategies -> risk -> paper fill
    orch.open_trades()
    assert db.count_open_positions() == 1

    # 3) price doubles -> momentum take-profit closes with a profit
    monkeypatch.setattr(orch_mod.marketdata, "token_market",
                        lambda addr: _strong_snapshot(price=2.0))
    orch.manage_positions()
    assert db.count_open_positions() == 0
    assert db.realized_pnl() > 0


# --- hybrid CEX/DEX + lending ----------------------------------------------
def test_binance_adapter_price_with_fake_client():
    import types

    from dex_trade_bot.cex.binance_adapter import BinanceAdapter

    cfg = make_config()
    adapter = BinanceAdapter(cfg, DummyLogger())
    adapter.client = types.SimpleNamespace(
        get_symbol_ticker=lambda symbol: {"price": "2.5"})
    assert adapter.available
    assert adapter.price("CAKEUSDT") == 2.5


def test_crossarb_emits_intent_when_dex_lags(monkeypatch):
    import types

    import dex_trade_bot.strategies.crossarb_strategy as ca

    cfg = make_config(CROSSARB_SYMBOLS=["CAKE"])
    s = ca.Strategy(cfg, DummyLogger())
    s.cex = types.SimpleNamespace(available=True, price=lambda sym: 2.0)        # CEX = 2.00
    s.pancake = types.SimpleNamespace(quote_out=lambda a, b, amt, path=None: 1.9)  # DEX = 1.90
    s.web3_client = types.SimpleNamespace(connected=True)
    monkeypatch.setattr(ca.marketdata, "token_market", lambda addr: {"liquidity_usd": 80000})

    intents = s.generate_open_intents([])
    assert len(intents) == 1
    assert intents[0].symbol == "CAKE"
    assert intents[0].expected_edge_pct > 1.5  # ~5.3% lag


def test_crossarb_silent_when_in_line(monkeypatch):
    import types

    import dex_trade_bot.strategies.crossarb_strategy as ca

    cfg = make_config(CROSSARB_SYMBOLS=["CAKE"])
    s = ca.Strategy(cfg, DummyLogger())
    s.cex = types.SimpleNamespace(available=True, price=lambda sym: 1.905)  # ~in line
    s.pancake = types.SimpleNamespace(quote_out=lambda a, b, amt, path=None: 1.9)
    s.web3_client = types.SimpleNamespace(connected=True)
    monkeypatch.setattr(ca.marketdata, "token_market", lambda addr: {"liquidity_usd": 80000})
    assert s.generate_open_intents([]) == []


def test_venus_shortfall_parsing():
    import types

    from dex_trade_bot.lending.venus import VenusMonitor

    cfg = make_config(VENUS_WATCH_ACCOUNTS=["0xBorrower"])
    call_obj = types.SimpleNamespace(call=lambda: (0, 0, int(5 * 1e18)))
    fns = types.SimpleNamespace(getAccountLiquidity=lambda acct: call_obj)
    contract = types.SimpleNamespace(functions=fns)
    fake_web3 = types.SimpleNamespace(connected=True, contract=lambda a, abi: contract,
                                      checksum=lambda a: a)
    mon = VenusMonitor(fake_web3, cfg, DummyLogger())
    assert mon.enabled
    assert mon.account_shortfall_usd("0xBorrower") == 5.0
    assert mon.scan()[0]["shortfall_usd"] == 5.0


def test_liquidation_strategy_is_monitor_only():
    import types

    import dex_trade_bot.strategies.liquidation_strategy as lq

    cfg = make_config()
    s = lq.Strategy(cfg, DummyLogger())
    s.venus = types.SimpleNamespace(
        enabled=True, scan=lambda: [{"account": "0xa", "shortfall_usd": 100.0}])
    assert s.generate_open_intents([]) == []  # never fires at $30


# --- dashboard -------------------------------------------------------------
def test_dashboard_endpoints(tmp_path):
    from dex_trade_bot.dashboard import create_app
    from dex_trade_bot.models import PnLSnapshot

    db_file = tmp_path / "dash.db"
    cfg = make_config(STARTING_BALANCE_USD=30)
    cfg.DB_PATH = f"sqlite:///{db_file}"
    db = make_db(cfg)
    # seed a paper roundtrip + a couple of pnl snapshots
    ex = PaperExecutor(cfg, web3_client=None, pancake=None, database=db, logger=DummyLogger())
    ex.open_position({"token_address": "0xz", "symbol": "ZZZ"}, 5.0, 1.0, "momentum", 1_000_000, 0.0)
    pos = db.get_open_position("0xz")
    ex.close_position(pos, 1.3, 1_000_000, 0.0, "tp")
    with db.db_session() as session:
        session.add(PnLSnapshot(25.0, 5.0, db.realized_pnl(), 1))

    app = create_app(cfg)
    client = app.test_client()

    s = client.get("/api/summary").get_json()
    assert s["mode"] == "paper"
    assert s["starting_balance"] == 30
    assert "return_pct" in s

    assert client.get("/api/pnl").status_code == 200
    assert isinstance(client.get("/api/trades").get_json(), list)
    assert len(client.get("/api/trades").get_json()) >= 2  # buy + sell
    assert client.get("/").status_code == 200

    # per-strategy performance: the one closed momentum trade should appear
    strat = client.get("/api/strategies").get_json()
    assert isinstance(strat, list) and len(strat) == 1
    row = strat[0]
    assert row["strategy"] == "momentum"
    assert row["trades"] == 1
    assert row["realized_pnl"] > 0  # closed at +30%
    assert row["win_rate"] == 100.0


# --- self-check ------------------------------------------------------------
def test_selfcheck_returns_structure_without_raising():
    from dex_trade_bot import selfcheck

    cfg = make_config()  # paper mode, valid wallet
    results, ready = selfcheck.run(cfg, DummyLogger())
    # Always returns a list of structured checks and a bool, even if network is down.
    assert isinstance(results, list) and results
    assert all({"name", "ok", "detail", "critical"} <= set(r) for r in results)
    assert isinstance(ready, bool)


def test_selfcheck_flags_missing_wallet_as_not_ready(monkeypatch):
    from dex_trade_bot import selfcheck

    cfg = make_config()
    cfg.WALLET_ADDRESS = ""  # critical config problem
    # Stub network checks so the test is deterministic offline.
    monkeypatch.setattr(selfcheck, "_check_dexscreener",
                        lambda: selfcheck._ok("DexScreener (price source)", True, "ok", critical=True))
    monkeypatch.setattr(selfcheck, "_check_honeypot",
                        lambda: selfcheck._ok("honeypot.is (safety screen)", True, "ok"))
    monkeypatch.setattr(selfcheck, "_check_rpc",
                        lambda c, l: selfcheck._ok("BSC RPC (on-chain)", True, "ok"))
    monkeypatch.setattr(selfcheck, "_check_binance",
                        lambda c, l: selfcheck._ok("Binance (CEX, crossarb)", True, "ok"))
    _, ready = selfcheck.run(cfg, DummyLogger())
    assert ready is False  # missing wallet is a critical failure


# --- demo mode -------------------------------------------------------------
def test_demo_mode_bypasses_cost_gate_paper_only():
    from dex_trade_bot.risk.manager import RiskManager

    # Strict (default): a sub-cost edge is vetoed.
    cfg = make_config()
    db = make_db(cfg)
    rm = RiskManager(cfg, db, DummyLogger())
    cand = {"token_address": "0xstable", "symbol": "USDC"}
    strict = rm.evaluate_open(cand, cash_usd=30, expected_edge_pct=0.26, est_cost_pct=4.0)
    assert not strict.approved and "cost" in strict.reason

    # Demo (paper): same sub-cost edge is approved with a real size.
    cfg.DEMO_MODE = True
    demo = rm.evaluate_open(cand, cash_usd=30, expected_edge_pct=0.26, est_cost_pct=4.0)
    assert demo.approved and demo.size_usd > 0

    # Demo must NEVER loosen anything in live mode.
    cfg.EXECUTION_MODE = "live"
    assert cfg.demo_active is False
    live = rm.evaluate_open(cand, cash_usd=30, expected_edge_pct=0.26, est_cost_pct=4.0)
    assert not live.approved


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
