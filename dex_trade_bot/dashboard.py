"""Simple local PnL dashboard for dex_trade_bot.

Reads the same SQLite DB the bot writes (dex_trading.db) and serves a single
auto-refreshing page: account value, realized PnL, an inline PnL chart, open
positions and recent trades. No external assets (works offline).

Run alongside the bot:
    python -m dex_trade_bot.dashboard        # then open http://127.0.0.1:8080
"""
from flask import Flask, jsonify

from .config import Config
from .database import Database
from .logger import Logger


def create_app(config=None):
    config = config or Config()
    logger = Logger(logging_service="dex_dashboard", enable_notifications=False)
    db = Database(logger, config)
    db.create_database()

    app = Flask(__name__)

    @app.route("/api/summary")
    def summary():
        series = db.pnl_series(limit=1)
        realized = db.realized_pnl()
        if series:
            latest = series[-1]
            total, cash, positions, open_n = (
                latest["total"], latest["cash"], latest["positions"], latest["open"],
            )
        else:
            total = cash = config.STARTING_BALANCE_USD
            positions, open_n = 0.0, 0
        start = config.STARTING_BALANCE_USD
        return jsonify({
            "mode": config.EXECUTION_MODE,
            "starting_balance": start,
            "total_value": total,
            "cash": cash,
            "positions_value": positions,
            "realized_pnl": round(realized, 4),
            "return_pct": round((total - start) / start * 100, 2) if start else 0.0,
            "open_positions": open_n,
            "enabled_strategies": config.ENABLED_STRATEGIES,
        })

    @app.route("/api/pnl")
    def pnl():
        return jsonify(db.pnl_series())

    @app.route("/api/positions")
    def positions():
        return jsonify(db.open_positions_view())

    @app.route("/api/trades")
    def trades():
        return jsonify(db.recent_trades())

    @app.route("/api/strategies")
    def strategies():
        return jsonify(db.strategy_performance())

    @app.route("/")
    def index():
        return _PAGE

    return app


_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>dex_trade_bot</title>
<style>
 body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#0e1117;color:#e6edf3;margin:0;padding:24px}
 h1{font-size:18px;margin:0 0 4px} .sub{color:#7d8590;font-size:12px;margin-bottom:18px}
 .cards{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:20px}
 .card{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px 18px;min-width:140px}
 .card .label{color:#7d8590;font-size:11px;text-transform:uppercase;letter-spacing:.05em}
 .card .val{font-size:22px;font-weight:600;margin-top:4px}
 .pos{color:#3fb950}.neg{color:#f85149}
 table{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}
 th,td{text-align:left;padding:6px 10px;border-bottom:1px solid #21262d}
 th{color:#7d8590;font-weight:500;font-size:11px;text-transform:uppercase}
 h2{font-size:14px;margin:24px 0 4px;color:#c9d1d9}
 svg{background:#161b22;border:1px solid #30363d;border-radius:10px}
 .badge{background:#21262d;border-radius:6px;padding:2px 8px;font-size:11px;color:#7d8590}
</style></head>
<body>
 <h1>dex_trade_bot <span id="mode" class="badge"></span></h1>
 <div class="sub">Local PnL dashboard — auto-refreshes every 5s. Honest note: at ~$30 expect break-even to small loss.</div>
 <div class="cards" id="cards"></div>
 <h2>Account value over time</h2>
 <svg id="chart" width="100%" height="180" viewBox="0 0 1000 180" preserveAspectRatio="none"></svg>
 <h2>Strategy performance</h2>
 <table id="strategies"><thead><tr><th>Strategy</th><th>Trades</th><th>Win rate</th><th>Avg PnL $</th><th>Realized PnL $</th></tr></thead><tbody></tbody></table>
 <h2>Open positions</h2>
 <table id="positions"><thead><tr><th>Symbol</th><th>Strategy</th><th>Qty</th><th>Entry</th><th>Cost $</th><th>Opened</th></tr></thead><tbody></tbody></table>
 <h2>Recent trades</h2>
 <table id="trades"><thead><tr><th>Time</th><th>Symbol</th><th>Strategy</th><th>Side</th><th>Value $</th><th>Cost $</th><th>Mode</th></tr></thead><tbody></tbody></table>
<script>
const f=n=>(n==null?'-':Number(n).toLocaleString(undefined,{maximumFractionDigits:6}));
const cls=n=>n>=0?'pos':'neg';
async function j(u){const r=await fetch(u);return r.json();}
async function refresh(){
 const s=await j('/api/summary');
 document.getElementById('mode').textContent=s.mode.toUpperCase();
 const ret=s.return_pct;
 document.getElementById('cards').innerHTML=`
  <div class="card"><div class="label">Total value</div><div class="val">$${f(s.total_value)}</div></div>
  <div class="card"><div class="label">Realized PnL</div><div class="val ${cls(s.realized_pnl)}">$${f(s.realized_pnl)}</div></div>
  <div class="card"><div class="label">Return</div><div class="val ${cls(ret)}">${ret>=0?'+':''}${f(ret)}%</div></div>
  <div class="card"><div class="label">Cash</div><div class="val">$${f(s.cash)}</div></div>
  <div class="card"><div class="label">In positions</div><div class="val">$${f(s.positions_value)}</div></div>
  <div class="card"><div class="label">Open</div><div class="val">${s.open_positions}</div></div>`;
 const d=await j('/api/pnl');drawChart(d);
 const st=await j('/api/strategies');
 document.querySelector('#strategies tbody').innerHTML=st.map(r=>`<tr><td>${r.strategy}</td><td>${r.trades}</td><td>${f(r.win_rate)}%</td><td class="${cls(r.avg_pnl)}">${f(r.avg_pnl)}</td><td class="${cls(r.realized_pnl)}">${f(r.realized_pnl)}</td></tr>`).join('')||'<tr><td colspan=5 style="color:#7d8590">no closed trades yet</td></tr>';
 const p=await j('/api/positions');
 document.querySelector('#positions tbody').innerHTML=p.map(r=>`<tr><td>${r.symbol}</td><td>${r.strategy}</td><td>${f(r.qty)}</td><td>${f(r.entry)}</td><td>${f(r.cost_usd)}</td><td>${r.opened_at.slice(0,19).replace('T',' ')}</td></tr>`).join('')||'<tr><td colspan=6 style="color:#7d8590">none</td></tr>';
 const t=await j('/api/trades');
 document.querySelector('#trades tbody').innerHTML=t.map(r=>`<tr><td>${r.t.slice(0,19).replace('T',' ')}</td><td>${r.symbol}</td><td>${r.strategy}</td><td class="${r.side=='BUY'?'pos':'neg'}">${r.side}</td><td>${f(r.value)}</td><td>${f(r.cost)}</td><td>${r.mode}</td></tr>`).join('')||'<tr><td colspan=7 style="color:#7d8590">no trades yet</td></tr>';
}
function drawChart(d){
 const svg=document.getElementById('chart');
 if(!d.length){svg.innerHTML='<text x=500 y=90 fill=#7d8590 text-anchor=middle>no data yet — run the bot</text>';return;}
 const vals=d.map(x=>x.total),min=Math.min(...vals),max=Math.max(...vals),pad=(max-min)*0.1||1;
 const lo=min-pad,hi=max+pad,W=1000,H=180;
 const pts=d.map((x,i)=>[i/(d.length-1||1)*W,H-(x.total-lo)/(hi-lo)*H]);
 const path=pts.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+' '+p[1].toFixed(1)).join(' ');
 const last=vals[vals.length-1],first=vals[0],col=last>=first?'#3fb950':'#f85149';
 svg.innerHTML=`<path d="${path}" fill="none" stroke="${col}" stroke-width="2"/>`+
  `<text x=8 y=14 fill=#7d8590 font-size=11>$${hi.toFixed(2)}</text>`+
  `<text x=8 y=172 fill=#7d8590 font-size=11>$${lo.toFixed(2)}</text>`;
}
refresh();setInterval(refresh,5000);
</script>
</body></html>"""


def main():
    import os

    app = create_app()
    port = int(os.environ.get("DASHBOARD_PORT", "8080"))
    app.run(host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
