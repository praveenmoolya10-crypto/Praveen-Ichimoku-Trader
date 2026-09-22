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
 return """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Praveen Ichimoku Trader</title><style>body{font-family:Arial;background:#0b1020;color:#eee;margin:0;padding:20px}.card{background:#11182c;padding:18px;border-radius:12px;margin:12px 0}button,select{padding:10px;background:#18223c;color:#fff;border:1px solid #394663;border-radius:8px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}.sig{font-size:28px;font-weight:bold}pre{overflow:auto}</style></head><body><h1>Praveen Ichimoku Trader</h1><div class="grid"><div class="card"><b>System</b><pre id="sys">Loading</pre></div><div class="card"><b>Account</b><pre id="acc">Loading</pre></div></div><div class="card"><select id="s"></select><button onclick="load()">Refresh</button><span id="sig" class="sig"></span><pre id="ind"></pre></div><div class="grid"><div class="card"><h3>Positions</h3><pre id="pos"></pre></div><div class="card"><h3>Recent Orders</h3><pre id="ord"></pre></div></div><script>
async function load(){let s=document.getElementById('s').value;let [h,a,p,o,x]=await Promise.all([fetch('/api/health').then(r=>r.json()),fetch('/api/account').then(r=>r.json()),fetch('/api/positions').then(r=>r.json()),fetch('/api/orders').then(r=>r.json()),fetch('/api/strategy/'+s).then(r=>r.json())]);document.getElementById('sys').textContent=JSON.stringify(h,null,2);document.getElementById('acc').textContent=JSON.stringify(a,null,2);document.getElementById('pos').textContent=JSON.stringify(p,null,2);document.getElementById('ord').textContent=JSON.stringify(o,null,2);document.getElementById('sig').textContent=s+' — '+x.signal;document.getElementById('ind').textContent=JSON.stringify(x.indicators,null,2)}async function init(){let h=await fetch('/api/health').then(r=>r.json());document.getElementById('s').innerHTML=h.symbols.map(s=>'<option>'+s+'</option>').join('');load()}init();setInterval(load,30000)</script></body></html>"""

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
