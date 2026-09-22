import os
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from .strategy import ichimoku, signal
from .alpaca_adapter import AlpacaAdapter

app=FastAPI(title="Ichimoku Multi-Market Trader",version="1.0.0")
PAPER_TRADING=os.getenv("PAPER_TRADING","true").lower()=="true"
AUTO_TRADING=os.getenv("AUTO_TRADING","false").lower()=="true"
EMERGENCY_STOP=os.getenv("EMERGENCY_STOP","true").lower()=="true"
adapter=AlpacaAdapter()

class OrderRequest(BaseModel):
 symbol:str
 side:str
 qty:float
 order_type:str="market"
 time_in_force:str="day"

@app.get("/",response_class=HTMLResponse)
def dashboard():
 return """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ichimoku Trader</title><style>body{font-family:Arial;background:#0b1020;color:#eee;margin:0;padding:30px}button,select{padding:10px;margin:5px;background:#18223c;color:#fff;border:1px solid #394663;border-radius:8px}.card{background:#11182c;padding:20px;border-radius:12px;margin:15px 0}#sig{font-size:28px;font-weight:bold}</style></head><body><h1>Ichimoku Trader</h1><div class="card"><select id="s"><option>AAPL</option><option>MSFT</option><option>NVDA</option><option>AMZN</option><option>GOOGL</option><option>META</option><option>TSLA</option></select><button onclick="load()">Refresh</button><div id="sig">Loading...</div></div><div class="card"><h3>System</h3><pre id="sys"></pre></div><div class="card"><h3>Ichimoku</h3><pre id="ind"></pre></div><script>async function load(){let s=document.getElementById('s').value;let[a,b]=await Promise.all([fetch('/api/health').then(x=>x.json()),fetch('/api/strategy/'+s).then(x=>x.json())]);document.getElementById('sig').textContent=s+' — '+b.signal;document.getElementById('sys').textContent=JSON.stringify(a,null,2);document.getElementById('ind').textContent=JSON.stringify(b.indicators,null,2)}load();setInterval(load,30000)</script></body></html>"""

@app.get("/api/health")
def health(): return {"status":"ok","paper_trading":PAPER_TRADING,"auto_trading":AUTO_TRADING,"emergency_stop":EMERGENCY_STOP,"time":datetime.now(timezone.utc)}

@app.get("/api/account")
def account(): return adapter.account()
@app.get("/api/positions")
def positions(): return adapter.positions()
@app.get("/api/orders")
def orders(): return adapter.orders()
@app.get("/api/bars/{symbol}")
def bars(symbol:str,timeframe:str="1Day",limit:int=200): return adapter.bars(symbol,timeframe,limit)

@app.post("/api/order")
def order(req:OrderRequest):
 if EMERGENCY_STOP: raise HTTPException(409,"Emergency stop is active")
 if not AUTO_TRADING: raise HTTPException(409,"Automatic trading is disabled")
 if not PAPER_TRADING: raise HTTPException(403,"Live trading is disabled in this build")
 return adapter.place_order(req.symbol,req.side,req.qty,req.order_type,req.time_in_force)

@app.post("/api/emergency-stop")
def emergency_stop():
 os.environ["EMERGENCY_STOP"]="true"; return {"emergency_stop":True}
@app.post("/api/auto-trading/{enabled}")
def auto(enabled:bool):
 os.environ["AUTO_TRADING"]=str(enabled).lower(); return {"auto_trading":enabled}
@app.post("/api/paper/{enabled}")
def paper(enabled:bool):
 os.environ["PAPER_TRADING"]=str(enabled).lower(); return {"paper_trading":enabled}
@app.get("/api/strategy/{symbol}")
def strategy(symbol:str):
 b=adapter.bars(symbol,"1Day",250)["bars"].get(symbol.upper(),[]); ind=ichimoku(b)
 return {"symbol":symbol.upper(),"signal":signal(ind),"indicators":ind[-1] if ind else None}
