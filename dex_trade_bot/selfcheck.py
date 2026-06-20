"""Pre-flight connectivity & config check.

Run before trading to see what's reachable and whether the config is sane:

    python -m dex_trade_bot --check

Reports each dependency as OK / FAIL with detail, and whether the bot can run in
the configured mode. Critical checks differ by mode: paper needs a price source
(DexScreener); live additionally needs the BSC RPC and a private key.
"""
import requests

from .cex.binance_adapter import BinanceAdapter
from .chain.web3_client import Web3Client
from .constants import WBNB
from .dex import marketdata

_TIMEOUT = 12


def _ok(name, ok, detail="", critical=False):
    return {"name": name, "ok": ok, "detail": detail, "critical": critical}


def _check_dexscreener():
    try:
        results = marketdata.search("WBNB")
        if results:
            return _ok("DexScreener (price source)", True, f"{len(results)} BSC pairs", critical=True)
        return _ok("DexScreener (price source)", False, "reachable but no data", critical=True)
    except Exception as e:  # pylint: disable=broad-except
        return _ok("DexScreener (price source)", False, str(e)[:80], critical=True)


def _check_honeypot():
    try:
        resp = requests.get(f"https://api.honeypot.is/v2/IsHoneypot?address={WBNB}&chainID=56",
                            timeout=_TIMEOUT, headers={"User-Agent": "dex-trade-bot/1.0"})
        return _ok("honeypot.is (safety screen)", resp.status_code == 200, f"HTTP {resp.status_code}")
    except Exception as e:  # pylint: disable=broad-except
        return _ok("honeypot.is (safety screen)", False, str(e)[:80])


def _check_rpc(config, logger):
    client = Web3Client(config, logger)
    if client.connected:
        try:
            block = client.w3.eth.block_number
            return _ok("BSC RPC (on-chain)", True, f"block {block}", critical=config.is_live)
        except Exception as e:  # pylint: disable=broad-except
            return _ok("BSC RPC (on-chain)", False, str(e)[:80], critical=config.is_live)
    return _ok("BSC RPC (on-chain)", False, "not connected", critical=config.is_live)


def _check_binance(config, logger):
    adapter = BinanceAdapter(config, logger)
    price = adapter.price("BNBUSDT") if adapter.available else None
    if price:
        return _ok("Binance (CEX, crossarb)", True, f"BNB=${price:,.2f}")
    return _ok("Binance (CEX, crossarb)", False, "unreachable (optional)")


def run(config, logger):
    """Run all checks; return (results, ready: bool)."""
    results = [
        _check_dexscreener(),
        _check_rpc(config, logger),
        _check_honeypot(),
        _check_binance(config, logger),
    ]

    # Config sanity
    problems = config.validate()
    results.append(_ok("Config", not problems, "; ".join(problems) or "valid", critical=True))
    results.append(_ok("Wallet address set", bool(config.WALLET_ADDRESS),
                       config.WALLET_ADDRESS or "missing", critical=True))
    if config.is_live:
        results.append(_ok("Private key (live mode)", bool(config.PRIVATE_KEY),
                           "present" if config.PRIVATE_KEY else "MISSING", critical=True))

    ready = all(r["ok"] for r in results if r["critical"])

    # Pretty print
    logger.info("=" * 60)
    logger.info(f"Pre-flight check — mode: {config.EXECUTION_MODE.upper()}")
    logger.info("=" * 60)
    for r in results:
        mark = "OK  " if r["ok"] else "FAIL"
        tag = " [critical]" if r["critical"] else ""
        logger.info(f"  [{mark}] {r['name']}: {r['detail']}{tag}")
    logger.info("=" * 60)
    if ready:
        logger.info(f"READY to run in {config.EXECUTION_MODE} mode.")
    else:
        failed = [r["name"] for r in results if r["critical"] and not r["ok"]]
        logger.warning(f"NOT READY — failing critical checks: {', '.join(failed)}")
    logger.info(f"Enabled strategies: {', '.join(config.ENABLED_STRATEGIES)}")
    return results, ready
