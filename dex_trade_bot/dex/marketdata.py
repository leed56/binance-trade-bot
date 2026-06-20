"""Market data via public HTTP APIs (DexScreener / GeckoTerminal).

This is the price/liquidity/volume source the paper engine runs on. It needs no
RPC and no key, so strategies can be validated on live data with zero setup.
Returns are best-effort: network hiccups yield ``None`` rather than raising.
"""
import requests

DEXSCREENER_TOKEN = "https://api.dexscreener.com/latest/dex/tokens/{address}"
DEXSCREENER_SEARCH = "https://api.dexscreener.com/latest/dex/search?q={query}"

_TIMEOUT = 12


def _get(url):
    try:
        resp = requests.get(url, timeout=_TIMEOUT, headers={"User-Agent": "dex-trade-bot/1.0"})
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        return None
    return None


def _best_bsc_pair(pairs):
    """Pick the most liquid BSC pair from a DexScreener pairs list."""
    bsc = [p for p in (pairs or []) if p.get("chainId") == "bsc"]
    if not bsc:
        return None
    return max(bsc, key=lambda p: (p.get("liquidity") or {}).get("usd", 0) or 0)


def token_market(address):
    """Return a normalized snapshot for a token's best BSC pair, or None."""
    data = _get(DEXSCREENER_TOKEN.format(address=address))
    if not data:
        return None
    pair = _best_bsc_pair(data.get("pairs"))
    if not pair:
        return None
    return _normalize(pair)


def _normalize(pair):
    liq = (pair.get("liquidity") or {}).get("usd", 0) or 0
    price = float(pair.get("priceUsd") or 0)
    vol = pair.get("volume") or {}
    change = pair.get("priceChange") or {}
    txns = pair.get("txns") or {}
    return {
        "token_address": (pair.get("baseToken") or {}).get("address", ""),
        "symbol": (pair.get("baseToken") or {}).get("symbol", "?"),
        "pair_address": pair.get("pairAddress", ""),
        "dex": pair.get("dexId", ""),
        "price_usd": price,
        "liquidity_usd": float(liq),
        "volume_h24": float(vol.get("h24", 0) or 0),
        "volume_h1": float(vol.get("h1", 0) or 0),
        "change_h1": float(change.get("h1", 0) or 0),
        "change_h6": float(change.get("h6", 0) or 0),
        "change_h24": float(change.get("h24", 0) or 0),
        "buys_h1": int((txns.get("h1") or {}).get("buys", 0) or 0),
        "sells_h1": int((txns.get("h1") or {}).get("sells", 0) or 0),
        "pair_created_at": pair.get("pairCreatedAt", 0),
    }


def search(query):
    """Search BSC pairs by symbol/name; returns a list of normalized snapshots."""
    data = _get(DEXSCREENER_SEARCH.format(query=query))
    if not data:
        return []
    out = []
    for pair in data.get("pairs", []):
        if pair.get("chainId") == "bsc":
            out.append(_normalize(pair))
    return out
