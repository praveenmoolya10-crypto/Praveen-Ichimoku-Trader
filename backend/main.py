import os, asyncio, hashlib, hmac
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from .strategy import ichimoku, signal
from .alpaca_adapter import AlpacaAdapter
from .risk import size_position, RiskConfig

app=FastAPI(title="Praveen Ichimoku Multi-Market Trader",version="2.0.0")
adapter=AlpacaAdapter()
risk=RiskConfig()
last_trades={}
scanner_task=None

def flag(name,default):
 return os.getenv(name,default).lower()=="true"
def symbols():
 return [x.strip().upper() for x in os.getenv("TRADING_SYMBOLS","AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,NFLX,AVGO,AMD").split(",") if x.strip()]
def can_trade():
 return flag("PAPER_TRADING","true") and flag("AUTO_TRADING","false") and not flag("EMERGENCY_STOP","true") and adapter.configured()

class OrderRequest(BaseModel):
 symbol:str; side:str; qty:float; order_type:str="market"; time_in_force:str="day"

class TradingViewAlert(BaseModel):
 symbol:str; action:str; price:float|None=None; timeframe:str="1D"; source:str="tradingview"

@app.get("/",response_class=HTMLResponse)
def dashboard():
 return """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Praveen Ichimoku Trader</title><style>
*{box-sizing:border-box}body{margin:0;background:#07111f;color:#e8eef7;font-family:Inter,Arial,sans-serif}button,select,input{font:inherit}.top{display:flex;align-items:center;gap:18px;padding:16px 24px;border-bottom:1px solid #203047}.brand{font-size:22px;font-weight:800}.sub{font-size:12px;color:#8ea1bb;margin-top:3px}.search{flex:1;max-width:480px;background:#101e31;border:1px solid #29405c;border-radius:12px;padding:12px 16px;color:#fff}.pill{padding:10px 14px;border-radius:10px;border:1px solid #29405c;background:#101e31}.paper{color:#56e0b1;border-color:#176c59}.danger{color:#ff7676;border-color:#79363d}.ticker{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:16px 24px}.tile,.card{background:#0c1929;border:1px solid #20334b;border-radius:12px}.tile{padding:15px}.price{font-size:23px;font-weight:800;margin-top:8px}.up{color:#34d399}.down{color:#fb5c66}.nav{display:flex;gap:4px;padding:8px 24px;border-bottom:1px solid #203047;overflow:auto}.nav button{background:transparent;border:0;color:#9db0c8;padding:13px 16px;white-space:nowrap;border-radius:8px}.nav button.active{background:#12315a;color:#62a7ff}.wrap{padding:16px 24px}.grid{display:grid;grid-template-columns:1fr 1.3fr 1fr;gap:12px}.wide{grid-column:span 2}.card{padding:18px}.head{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}.muted{color:#8ea1bb}.big{font-size:32px;font-weight:800}.row{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #17283d}.tabs{display:flex;gap:8px;margin-bottom:12px}.tabs button{border:1px solid #29405c;background:#122137;color:#bdcbe0;padding:8px 12px;border-radius:8px}.tabs .sel{background:#1765d8;color:white}.table{width:100%;border-collapse:collapse}.table th,.table td{text-align:left;padding:9px;border-bottom:1px solid #17283d;font-size:13px}.badge{padding:5px 8px;border-radius:7px;background:#25344a}.buy{color:#35d69d}.sell{color:#ff6d78}.status{display:flex;justify-content:space-between;padding:9px 0}.stocklist{max-height:250px;overflow:auto}.bottom{display:flex;justify-content:space-around;padding:13px;border-top:1px solid #203047;color:#8ea1bb;margin-top:10px}@media(max-width:900px){.ticker{grid-template-columns:1fr 1fr}.grid{grid-template-columns:1fr}.wide{grid-column:auto}.top{flex-wrap:wrap}.search{order:3;max-width:none;width:100%}}@media(max-width:520px){.ticker{grid-template-columns:1fr}.wrap,.ticker,.nav,.top{padding-left:12px;padding-right:12px}.nav button{padding:10px}.table{min-width:600px}.tablewrap{overflow:auto}}
</style></head><body><div class="top"><div><div class="brand">◈ Praveen Ichimoku Trader</div><div class="sub">NSE + NASDAQ | Auto & Manual Trading</div></div><input class="search" placeholder="Search stocks (AAPL, RELIANCE, TCS)"><span class="pill paper">● Paper Trading</span><span class="pill">Auto Trading: OFF</span><span class="pill danger">Emergency Stop: ON</span></div>
<div class="ticker"><div class="tile"><b>NIFTY 50</b><div class="price">—</div><span class="muted">NSE data</span></div><div class="tile"><b>SENSEX</b><div class="price">—</div><span class="muted">NSE data</span></div><div class="tile"><b>NASDAQ</b><div class="price">—</div><span class="muted">Alpaca data</span></div><div class="tile"><b>S&P 500</b><div class="price">—</div><span class="muted">Alpaca data</span></div></div>
<div class="nav"><button class="active">⌂ Dashboard</button><button>⌕ Explore</button><button>▣ Holdings</button><button>▥ Positions</button><button>▤ Orders</button><button>☆ Watchlist</button><button>◉ Scanner</button><button>⌁ Strategy</button><button>⚙ Settings</button></div>
<div class="wrap"><div class="grid"><div class="card"><div class="head"><b>Portfolio Summary</b><span>◉</span></div><div class="big" id="value">—</div><div class="muted">Account value</div><div class="row"><span>Cash</span><b id="cash">—</b></div><div class="row"><span>Buying power</span><b id="bp">—</b></div></div>
<div class="card wide"><div class="head"><b>Holdings</b><span class="muted">View All</span></div><div class="tablewrap"><table class="table"><thead><tr><th>Stock</th><th>Qty</th><th>Avg Price</th><th>LTP</th><th>P&L</th></tr></thead><tbody id="positions"></tbody></table></div></div>
<div class="card"><div class="head"><b>Strategy Status</b><span class="muted">v2.0</span></div><div class="status">Ichimoku Strategy <b class="buy">ACTIVE</b></div><div class="status">Paper Trading <b class="buy">ENABLED</b></div><div class="status">Auto Trading <b>DISABLED</b></div><div class="status">Emergency Stop <b class="sell">ON</b></div><div class="status">Alpaca <b id="configured">NOT CONFIGURED</b></div></div>
<div class="card wide"><div class="head"><b>Orders</b><span class="muted">View All</span></div><div class="tabs"><button class="sel">Pending</button><button>Executed</button><button>Rejected</button><button>Cancelled</button></div><div class="tablewrap"><table class="table"><thead><tr><th>Stock</th><th>Side</th><th>Qty</th><th>Type</th><th>Status</th></tr></thead><tbody id="orders"></tbody></table></div></div>
<div class="card"><div class="head"><b>Watchlist</b><span class="muted">10 stocks</span></div><div class="stocklist" id="watch"></div></div><div class="card"><div class="head"><b>Ichimoku Scanner</b><span class="muted">Live</span></div><div class="stocklist" id="signals"></div></div></div></div>
<div class="bottom"><span>⌂ Home</span><span>▥ Markets</span><span>⇄ Trade</span><span>▣ Portfolio</span><span>▤ Orders</span><span>₹ Funds</span><span>••• More</span></div>
<script>
const syms=["AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","NFLX","AVGO","AMD"];
async function j(u){try{return await fetch(u).then(r=>r.json())}catch(e){return {}}}
async function load(){const[h,a,p,o]=await Promise.all([j('/api/health'),j('/api/account'),j('/api/positions'),j('/api/orders')]);document.getElementById('configured').textContent=h.configured?'CONNECTED':'NOT CONFIGURED';document.getElementById('value').textContent=a.equity?'$'+a.equity:'—';document.getElementById('cash').textContent=a.cash?'$'+a.cash:'—';document.getElementById('bp').textContent=a.buying_power?'$'+a.buying_power:'—';document.getElementById('positions').innerHTML=(p||[]).map(x=>'<tr><td><b>'+x.symbol+'</b></td><td>'+x.qty+'</td><td>'+x.avg_entry_price+'</td><td>'+x.current_price+'</td><td class="'+(Number(x.unrealized_pl)>=0?'buy':'sell')+'">'+(x.unrealized_pl||'—')+'</td></tr>').join('')||'<tr><td colspan="5" class="muted">No open positions</td></tr>';document.getElementById('orders').innerHTML=(o||[]).slice(0,12).map(x=>'<tr><td><b>'+x.symbol+'</b></td><td class="'+(x.side==='buy'?'buy':'sell')+'">'+x.side+'</td><td>'+x.qty+'</td><td>'+x.type+'</td><td><span class="badge">'+x.status+'</span></td></tr>').join('')||'<tr><td colspan="5" class="muted">No orders</td></tr>';document.getElementById('watch').innerHTML=syms.map(s=>'<div class="row"><b>'+s+'</b><span class="muted">Scanner</span></div>').join('');let arr=await Promise.all(syms.map(async s=>[s,await j('/api/strategy/'+s)]));document.getElementById('signals').innerHTML=arr.map(([s,x])=>'<div class="row"><b>'+s+'</b><b class="'+String(x.signal||'HOLD').toLowerCase()+'">'+(x.signal||'HOLD')+'</b></div>').join('')}
load();setInterval(load,30000)
</script></body></html>"""

@app.get("/api/health")
def health():
 return {"status":"ok","version":"2.0.0","configured":adapter.configured(),"paper_trading":flag("PAPER_TRADING","true"),"auto_trading":flag("AUTO_TRADING","false"),"emergency_stop":flag("EMERGENCY_STOP","true"),"symbols":symbols(),"time":datetime.now(timezone.utc)}

@app.get("/api/account")
def account(): return adapter.account()
@app.get("/api/positions")
def positions(): return adapter.positions()
@app.get("/api/orders")
def orders(): return adapter.orders()
@app.get("/api/order/{order_id}")
def order_status(order_id:str): return adapter.order(order_id)
@app.get("/api/bars/{symbol}")
def bars(symbol:str,timeframe:str="1Day",limit:int=200): return adapter.bars(symbol,timeframe,limit)

@app.get("/api/strategy/{symbol}")
def strategy(symbol:str):
 b=adapter.bars(symbol,"1Day",250)["bars"].get(symbol.upper(),[]); ind=ichimoku(b)
 return {"symbol":symbol.upper(),"signal":signal(ind),"indicators":ind[-1] if ind else None,"bars":len(b)}

def execute(symbol,action,qty=None,source="scanner"):
 symbol=symbol.upper(); action=action.upper()
 if not can_trade(): raise HTTPException(409,"Trading is not enabled, emergency stop is active, or Alpaca credentials are missing")
 if action not in ("BUY","SELL"): return {"status":"ignored","reason":"Only BUY/SELL execute"}
 open_positions=adapter.positions()
 existing={p.get("symbol","").upper() for p in open_positions}
 if action=="BUY" and symbol in existing:return {"status":"ignored","reason":"position already open","symbol":symbol}
 if action=="SELL" and symbol not in existing:return {"status":"ignored","reason":"no position to sell","symbol":symbol}
 if qty is None:
  a=adapter.account(); equity=float(a.get("equity") or 0)
  b=adapter.bars(symbol,"1Day",5)["bars"].get(symbol,[])
  price=float(b[-1]["c"]) if b else 0
  qty=size_position(equity,price,risk)
 if qty<=0:return {"status":"ignored","reason":"risk sizing returned zero"}
 key=f"{symbol}:{action}"
 if key in last_trades and (datetime.now(timezone.utc)-last_trades[key]).total_seconds()<300:return {"status":"ignored","reason":"duplicate protection"}
 last_trades[key]=datetime.now(timezone.utc)
 oid=f"ichimoku-{symbol.lower()}-{int(datetime.now(timezone.utc).timestamp())}"
 return adapter.place_order(symbol,action,qty,"market","day",oid)

@app.post("/api/order")
def order(req:OrderRequest): return execute(req.symbol,req.side,req.qty,"api")

@app.post("/api/tradingview")
def tradingview(alert:TradingViewAlert,x_webhook_secret: str|None=Header(default=None)):
 secret=os.getenv("TRADINGVIEW_WEBHOOK_SECRET","")
 if secret and not hmac.compare_digest(x_webhook_secret or "",secret): raise HTTPException(401,"Invalid webhook secret")
 return execute(alert.symbol,alert.action,None,"tradingview")

@app.post("/api/emergency-stop")
def emergency_stop():
 os.environ["EMERGENCY_STOP"]="true"; return {"emergency_stop":True}

@app.post("/api/auto-trading/{enabled}")
def auto(enabled:bool):
 os.environ["AUTO_TRADING"]=str(enabled).lower(); return {"auto_trading":enabled}

@app.post("/api/paper/{enabled}")
def paper(enabled:bool):
 if not enabled: raise HTTPException(403,"Live trading is disabled in this build")
 os.environ["PAPER_TRADING"]="true"; return {"paper_trading":True}

async def scanner():
 while True:
  try:
   if can_trade():
    for s in symbols():
     try:
      b=adapter.bars(s,"1Day",250)["bars"].get(s,[]); sig=signal(ichimoku(b))
      if sig in ("BUY","SELL"): execute(s,sig,None,"scanner")
     except Exception: pass
  except Exception: pass
  await asyncio.sleep(int(os.getenv("SCAN_INTERVAL_SECONDS","60")))

@app.on_event("startup")
async def startup():
 global scanner_task
 scanner_task=asyncio.create_task(scanner())

@app.on_event("shutdown")
async def shutdown():
 if scanner_task: scanner_task.cancel()
