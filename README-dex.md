# dex_trade_bot — Autonomous BSC DEX Trading Bot

An autonomous, **paper-first** on-chain trading framework for BNB Smart Chain. You
supply a wallet address (and, only for live mode, a private key) plus a few risk
limits; the bot discovers candidates, screens them for safety, scores them, and
opens/manages/closes positions behind hard risk rails.

> ### Read this first — honest expectations
> This is a **learning and validation framework**, not a money printer.
> - With **~$30** of capital, realistic outcome is **break-even to a small loss**.
>   `profit = capital × edge − (gas + tax + slippage)`. Cleverness raises *edge*;
>   it cannot raise *capital*, and the cost terms have a floor.
> - On-chain **arbitrage/MEV** is dominated by professional firms with private
>   orderflow. At $30 the arbitrage module is mainly a **monitor**, not a profit center.
> - A hot private key driving an autonomous signer is the #1 way to lose a wallet.
>   The bot defaults to **paper mode** and never grants unlimited token approvals.

## How it works (multi-agent loop)

| Agent | File | Job |
|-------|------|-----|
| Discovery | `discovery/` | New PancakeSwap pairs + trending tokens (DexScreener) |
| Screening | `safety/screener.py` | Honeypot/tax/liquidity gate — **fails closed** |
| Intelligence | `intel/` | Whale/copy signals, on-chain flows, mempool watch, edge scoring |
| Strategies | `strategies/` | momentum, meanrev, sniper, arbitrage, stablegrid |
| Risk | `risk/manager.py` | Size caps, daily loss stop, gas-vs-edge guard, kill switch |
| Execution | `execution/` | `PaperExecutor` (sim) or `LiveExecutor` (signed swaps) |

## Strategies

- **momentum** — ride confirmed up-trends with healthy buy pressure.
- **meanrev** — fade short dips on tokens with an intact longer trend.
- **sniper** — small, aggressive entries on freshly screened new pairs (highest risk).
- **arbitrage** — Pancake-vs-Biswap price-gap **monitor**; only fires on a wide gap.
- **stablegrid** — patient USDT/USDC peg arbitrage; idle until a real depeg makes
  the deviation exceed costs.

## Quick start (paper, $0 cost)

```bash
pip install -r requirements-dex.txt
cp .env.example .env          # set WALLET_ADDRESS (a read-only address is fine for paper)
python -m dex_trade_bot --once   # run a single cycle
python -m dex_trade_bot           # run the full scheduled loop
```

Paper mode needs no private key and no premium node — a free public BSC RPC and
DexScreener are enough. It simulates fills with the same gas+tax+slippage cost
model the live executor uses, so the paper PnL curve previews live behaviour.

## Going live (only after reviewing paper results)

Set `EXECUTION_MODE=live`, provide `PRIVATE_KEY`, and keep `MAX_POSITION_USD` small.
Live trades use **bounded approvals only** (never `MAX_UINT256`) and a hard slippage
floor (`MAX_SLIPPAGE_BPS`). Start a tiny dry check (~$2) before trusting it.

## Configuration

All settings come from environment variables (see `.env.example`): wallet, RPC,
`EXECUTION_MODE`, the risk caps (`MAX_POSITION_USD`, `DAILY_LOSS_STOP_USD`,
`MAX_SLIPPAGE_BPS`, `MAX_OPEN_POSITIONS`, `MIN_LIQUIDITY_USD`, `MAX_BUY_TAX_PCT`,
`PER_TOKEN_COOLDOWN_MIN`), `ENABLED_STRATEGIES`, and the intel toggles.

## Deployment

- **Paper:** your own PC. Cost $0.
- **Live:** a cheap $4–6/mo VPS for 24/7 uptime so positions are never orphaned.
  Reuse the repo's `Dockerfile` / `docker-compose.yml`. Free/free-tier BSC RPC is
  sufficient; a WSS endpoint (`BSC_WSS_URL`) is only needed for mempool/sniping.
  **Do not** buy premium nodes at this capital — it is negative-EV.

## Safety rails

Private key from env only and never logged (the logger scrubs 64-hex secrets);
mandatory screening before any buy; bounded approvals with post-exit revoke; global
kill switch + daily loss stop; gas-vs-edge guard that blocks trades whose edge does
not clear all-in costs.

## Tests

```bash
python -m pytest tests/test_dex_bot.py -v
```

Covers the cost model, screener vetoes, risk gating, intel score bounds, paper-fill
PnL accounting, and a full offline orchestrator pipeline (entry → take-profit exit).
