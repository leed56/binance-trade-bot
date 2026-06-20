"""Mempool watcher — WATCH ONLY.

Subscribes to pending transactions on a WSS BSC endpoint and flags large pending
swaps/liquidity adds as an *early signal* for the discovery agent.

Deliberate non-goal: we do NOT front-run. We never submit a competing tx with
higher gas to land ahead of an observed pending tx. That is a gas-priority
auction professional bots win, and it shades into predatory MEV. This watcher
only produces intelligence; execution always goes through the normal risk gate.
"""
import json
import threading


class MempoolWatcher:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self._thread = None
        self._stop = threading.Event()
        # token_address(lower) -> count of large pending txs observed recently
        self.signals = {}

    @property
    def enabled(self):
        return self.config.ENABLE_MEMPOOL_WATCH and bool(self.config.BSC_WSS_URL)

    def start(self):
        if not self.enabled:
            self.logger.info("Mempool watch disabled (set ENABLE_MEMPOOL_WATCH=true and BSC_WSS_URL)")
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.logger.info("Mempool watcher started (watch-only)")

    def stop(self):
        self._stop.set()

    def _run(self):
        try:
            import asyncio

            import websockets
        except ImportError:
            self.logger.warning("websockets not installed; mempool watch unavailable")
            return

        async def listen():
            async with websockets.connect(self.config.BSC_WSS_URL) as ws:
                await ws.send(json.dumps(
                    {"id": 1, "method": "eth_subscribe", "params": ["newPendingTransactions"]}
                ))
                while not self._stop.is_set():
                    try:
                        await ws.recv()  # tx hash; full decode/labeling left as a hook
                    except Exception:  # pylint: disable=broad-except
                        break

        try:
            import asyncio

            asyncio.new_event_loop().run_until_complete(listen())
        except Exception as e:  # pylint: disable=broad-except
            self.logger.warning(f"mempool watcher stopped: {e}")

    def signal(self, token_address):
        return min(1.0, self.signals.get(token_address.lower(), 0) / 5.0)
