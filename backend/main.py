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

class APISettings(BaseModel):
 broker:str="alpaca"
 api_key:str
 api_secret:str
 paper:bool=True

@app.get("/",response_class=HTMLResponse)
def dashboard():
 return """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"><title>Praveen Ichimoku Trader</title><style>
*{box-sizing:border-box}body{margin:0;background:#f6f8fc;color:#182230;font-family:Inter,Arial,sans-serif}.app{max-width:1100px;margin:auto;background:#f6f8fc;min-height:100vh}.top{background:#fff;padding:14px 16px;border-bottom:1px solid #e3e8f0}.brand{font-size:21px;font-weight:800}.sub{font-size:12px;color:#7b8798;margin-top:3px}.search{margin-top:12px;width:100%;padding:12px 14px;border:1px solid #d9e0ea;border-radius:10px;background:#f7f9fc}.ticker{display:flex;gap:10px;padding:12px;overflow:auto;background:#fff}.ticker .item{min-width:145px;padding:10px;border:1px solid #e1e6ee;border-radius:10px;background:#fff}.ticker b{display:block;font-size:13px}.ticker strong{font-size:17px}.green{color:#12a76b}.red{color:#e05252}.nav{display:flex;overflow:auto;background:#fff;border-bottom:1px solid #dfe5ee}.nav button{border:0;background:#fff;padding:14px 16px;white-space:nowrap;color:#697587}.nav .active{color:#315fd6;border-bottom:3px solid #315fd6;font-weight:700}.content{padding:12px}.toolbar{display:flex;gap:8px;align-items:center;overflow:auto;margin-bottom:10px}.select,.action{padding:10px 13px;border:1px solid #d9e0ea;border-radius:9px;background:#fff}.buy{background:#0f9d68;color:white;border-color:#0f9d68}.sell{background:#e25555;color:white;border-color:#e25555}.card{background:#fff;border:1px solid #e0e5ed;border-radius:14px;padding:14px;margin-bottom:12px}.chartHead{display:flex;justify-content:space-between;align-items:center}.symbol{font-size:20px;font-weight:800}.signal{padding:7px 10px;border-radius:8px;background:#fff3cf;color:#9a7100;font-weight:800}.chartBox{height:390px;margin-top:8px;position:relative;overflow:hidden;border:1px solid #edf0f5;border-radius:8px;background:#fbfcfe}.chartBox canvas{width:100%;height:100%}.legend{display:flex;gap:14px;font-size:11px;color:#7a8594;padding-top:8px;flex-wrap:wrap}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.stat{padding:10px;background:#f7f9fc;border-radius:9px}.stat small{display:block;color:#7d8897}.stat b{font-size:15px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.row{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #edf0f4}.tablewrap{overflow:auto}.table{width:100%;border-collapse:collapse;min-width:520px}.table th,.table td{text-align:left;padding:10px;border-bottom:1px solid #edf0f4;font-size:13px}.pill{padding:6px 9px;border-radius:7px;background:#eef3ff;color:#315fd6}.bottom{position:sticky;bottom:0;display:flex;justify-content:space-around;background:#fff;border-top:1px solid #dfe5ee;padding:10px 4px}.bottom span{font-size:11px;color:#687487;text-align:center}.bottom .sel{color:#315fd6;font-weight:700}.hint{font-size:12px;color:#7c8796}.watch{max-height:220px;overflow:auto}@media(max-width:600px){.stats{grid-template-columns:1fr 1fr}.grid{grid-template-columns:1fr}.chartBox{height:330px}.content{padding:9px}.top{padding:12px}.nav button{padding:13px 12px}.ticker .item{min-width:132px}}</style></head><body><div class="app">
<div class="top"><div class="brand">Praveen Ichimoku Trader</div><div class="sub">NSE + NASDAQ | Auto & Manual Trading</div><input id="search" class="search" placeholder="Search stock: AAPL, MSFT, NVDA..."></div>
<div class="ticker"><div id="marketTicker" style="width:100%;min-height:64px"></div></div>
<div class="nav"><button class="active">Stocks</button><button>Explore</button><button>Holdings</button><button>Positions</button><button>Orders</button><button>Watchlist</button><button>Scanner</button><button>Strategy</button><button>Settings</button></div>
<div class="content">
<div class="toolbar"><select id="sym" class="select"><option>AAPL</option><option>MSFT</option><option>NVDA</option><option>AMZN</option><option>GOOGL</option><option>META</option><option>TSLA</option><option>NFLX</option><option>AVGO</option><option>AMD</option></select><select id="tf" class="select"><option value="1Day">1D</option><option value="1Min">1m</option></select><button class="action" id="refresh">↻</button><button class="action buy" id="buy">BUY</button><button class="action sell" id="sell">SELL</button></div>
<div class="card"><div class="chartHead"><div><div id="symbol" class="symbol">AAPL</div><div id="last" class="hint">TradingView market chart</div></div><div id="signal" class="signal">HOLD</div></div><div id="tvchart" style="height:430px;margin-top:8px;border-radius:8px;overflow:hidden"></div><div class="legend"><span>TradingView interactive chart</span><span>• Candles</span><span>• Indicators</span><span>• Drawing tools</span><span>• Multiple timeframes</span></div></div><div class="card"><div class="stats"><div class="stat"><small>Open</small><b id="open">—</b></div><div class="stat"><small>High</small><b id="high">—</b></div><div class="stat"><small>Low</small><b id="low">—</b></div><div class="stat"><small>Volume</small><b id="volume">—</b></div></div></div>
<div id="strategyPanel" class="grid"><div id="portfolioPanel" class="card"><div class="chartHead"><b>Portfolio</b><span class="pill">Paper</span></div><div class="row"><span>Account value</span><b id="value">—</b></div><div class="row"><span>Cash</span><b id="cash">—</b></div><div class="row"><span>Buying power</span><b id="bp">—</b></div></div><div class="card"><div class="chartHead"><b>Strategy</b><span id="configured" class="hint">Not configured</span></div><div class="row"><span>Ichimoku</span><b class="green">ACTIVE</b></div><div class="row"><span>Auto trading</span><b id="auto">OFF</b></div><div class="row"><span>Emergency stop</span><b class="red">ON</b></div></div></div>
<div id="holdingsPanel" class="card"><div class="chartHead"><b>Holdings</b><span class="hint">Broker holdings</span></div><div id="holdings" class="watch"></div></div>
<div class="grid"><div id="positionsPanel" class="card"><div class="chartHead"><b>Positions</b><span class="hint">Live</span></div><div id="positions" class="watch"></div></div><div id="ordersPanel" class="card"><div class="chartHead"><b>Orders</b><span class="hint">Live</span></div><div id="orders" class="watch"></div></div></div>
<div id="explorePanel" class="card"><div class="chartHead"><b>TradingView Stock Screener</b><span class="hint">Market scanner</span></div><div class="tabs"><button id="usScreen" class="pill">NASDAQ / US</button><button id="inScreen" class="pill">NSE / India</button></div><div id="tvscreener" style="height:520px"></div></div><div id="scannerPanel" class="card"><div class="chartHead"><b>Ichimoku Scanner</b><span class="hint">App strategy</span></div><div id="scanner" class="watch"></div></div>
<div id="settingsPanel" class="card"><div class="chartHead"><b>API Settings</b><span id="apiStatus" class="hint">Not connected</span></div><p class="hint">Enter broker credentials after the app opens. Credentials are sent over HTTPS to the trading backend and are kept only in the running server session in this build.</p><select id="broker" class="select" style="width:100%;margin-bottom:8px"><option value="alpaca">Alpaca</option><option value="nse">NSE broker (select below)</option></select><input id="apiKey" class="search" placeholder="API Key" autocomplete="off"><input id="apiSecret" class="search" style="margin-top:8px" placeholder="API Secret" type="password" autocomplete="new-password"><label class="hint" style="display:block;margin:10px 0"><input id="paperMode" type="checkbox" checked> Paper trading</label><button id="saveApi" class="action buy" style="width:100%">Save & Test Connection</button><div id="apiMsg" class="hint" style="margin-top:8px"></div></div>
</div><div class="bottom"><span class="sel">⌂<br>Stocks</span><span>⌁<br>Markets</span><span>⇄<br>Trade</span><span>▣<br>Portfolio</span><span>▤<br>Orders</span><span>•••<br>More</span></div>
<script>
const syms=["AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","NFLX","AVGO","AMD"];
let bars=[],ind=null;
async function get(u){try{return await fetch(u).then(r=>r.json())}catch(e){return {}}}
function tvChart(sym){const box=document.getElementById('tvchart');box.innerHTML='<div id="tvinner" style="height:100%;width:100%"></div>';const s=document.createElement('script');s.src='https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';s.async=true;s.innerHTML=JSON.stringify({autosize:true,symbol:'NASDAQ:'+sym,interval:'D',timezone:'exchange',theme:'light',style:'1',withdateranges:true,hide_side_toolbar:false,allow_symbol_change:true,save_image:false,calendar:false,support_host:'https://www.tradingview.com',studies:['Volume@tv-basicstudies']});box.firstChild.appendChild(s)}
function tvScreener(market){const box=document.getElementById('tvscreener');box.innerHTML='<div id="scrinner" style="height:100%;width:100%"></div>';const s=document.createElement('script');s.src='https://s3.tradingview.com/external-embedding/embed-widget-screener.js';s.async=true;s.innerHTML=JSON.stringify({width:'100%',height:'100%',defaultColumn:'overview',defaultScreen:'most_capitalized',showToolbar:true,locale:'en',market:market,colorTheme:'light'});box.firstChild.appendChild(s)}
function tvMarketTicker(){const box=document.getElementById('marketTicker');box.innerHTML='<div style="display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:8px;overflow:auto"><div id="mNIFTY"></div><div id="mSENSEX"></div><div id="mNASDAQ"></div><div id="mSPX"></div></div>';[['mNIFTY','NSE:NIFTY'],['mSENSEX','BSE:SENSEX'],['mNASDAQ','NASDAQ:IXIC'],['mSPX','SP:SPX']].forEach(([id,symbol])=>{const b=document.getElementById(id);b.innerHTML='<div class="tradingview-widget-container" style="width:100%;height:70px"><div class="tradingview-widget-container__widget"></div></div>';const s=document.createElement('script');s.src='https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js';s.async=true;s.innerHTML=JSON.stringify({symbol,chartOnly:false,dateRanges:'1D',noTimeScale:true,colorTheme:'light',isTransparent:false,locale:'en',autosize:true});b.firstChild.appendChild(s)})}
function navTo(target){const el=document.getElementById(target);if(el)el.scrollIntoView({behavior:'smooth',block:'start'})}
async function saveApi(){const msg=document.getElementById('apiMsg');const broker=document.getElementById('broker').value;if(broker!=='alpaca'){msg.textContent='NSE trading needs a specific supported broker adapter; Alpaca is enabled now.';return}msg.textContent='Connecting…';try{const r=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({broker,api_key:document.getElementById('apiKey').value,api_secret:document.getElementById('apiSecret').value,paper:document.getElementById('paperMode').checked})});const j=await r.json();if(!r.ok)throw new Error(j.detail||'Connection failed');document.getElementById('apiStatus').textContent='Connected';document.getElementById('apiStatus').className='green';msg.textContent='Connection successful. Account data can now load.';document.getElementById('apiKey').value='';document.getElementById('apiSecret').value='';load()}catch(e){document.getElementById('apiStatus').textContent='Not connected';msg.textContent=e.message||'Connection failed'}}
function setupNavigation(){const map={Stocks:'portfolioPanel',Explore:'explorePanel',Holdings:'holdingsPanel',Positions:'positionsPanel',Orders:'ordersPanel',Watchlist:'scannerPanel',Scanner:'scannerPanel',Strategy:'strategyPanel',Settings:'settingsPanel'};document.querySelectorAll('.nav button').forEach(b=>b.addEventListener('click',()=>navTo(map[b.textContent.trim()]||'portfolioPanel')));document.querySelectorAll('.bottom span').forEach(b=>b.addEventListener('click',()=>{const t=b.innerText.split('\n')[1]||'';const m={Stocks:'portfolioPanel',Markets:'explorePanel',Trade:'tvchart',Portfolio:'holdingsPanel',Orders:'ordersPanel',More:'settingsPanel'};navTo(m[t]||'portfolioPanel')}));document.getElementById('saveApi').addEventListener('click',saveApi)}
async function load(){let sym=document.getElementById('sym').value;let [st,a,p,o]=await Promise.all([get('/api/strategy/'+sym),get('/api/account'),get('/api/positions'),get('/api/orders')]);ind=st;document.getElementById('symbol').textContent=sym;document.getElementById('last').textContent='TradingView interactive market chart';document.getElementById('signal').textContent=st.signal||'HOLD';document.getElementById('value').textContent=a.equity?'$'+a.equity:'—';document.getElementById('cash').textContent=a.cash?'$'+a.cash:'—';document.getElementById('bp').textContent=a.buying_power?'$'+a.buying_power:'—';document.getElementById('configured').textContent=a.status==='not_configured'?'Not configured':'Connected';const holdingHtml=(p||[]).map(q=>'<div class="row"><div><b>'+q.symbol+'</b><div class="hint">'+(q.qty||'0')+' shares</div></div><span>'+((q.market_value||q.current_price||'—'))+'</span></div>').join('')||'<div class="hint">No holdings</div>';document.getElementById('holdings').innerHTML=holdingHtml;document.getElementById('positions').innerHTML=(p||[]).map(q=>'<div class="row"><b>'+q.symbol+'</b><span>'+q.qty+' @ '+q.avg_entry_price+'</span></div>').join('')||'<div class="hint">No open positions</div>';document.getElementById('orders').innerHTML=(o||[]).slice(0,8).map(q=>'<div class="row"><b>'+q.symbol+' '+q.side+'</b><span>'+q.status+'</span></div>').join('')||'<div class="hint">No orders</div>';let ss=await Promise.all(syms.map(async q=>[q,await get('/api/strategy/'+q)]));document.getElementById('scanner').innerHTML=ss.map(q=>'<div class="row"><b>'+q[0]+'</b><span class="'+(q[1].signal==='BUY'?'green':q[1].signal==='SELL'?'red':'hint')+'">'+(q[1].signal||'HOLD')+'</span></div>').join('');tvChart(sym)}
document.getElementById('sym').addEventListener('change',load);document.getElementById('refresh').addEventListener('click',load);document.getElementById('search').addEventListener('change',e=>{let v=e.target.value.trim().toUpperCase();if(syms.includes(v)){document.getElementById('sym').value=v;load()}});document.getElementById('usScreen').addEventListener('click',()=>tvScreener('us'));document.getElementById('inScreen').addEventListener('click',()=>tvScreener('india'));load();tvScreener('us');tvMarketTicker();setupNavigation();setInterval(load,30000);
</script>
</script></div></body></html>"""

@app.get("/api/settings")
def settings_status():
 return {"broker":"alpaca","configured":adapter.configured(),"paper":True}

@app.post("/api/settings")
def settings(req:APISettings):
 if req.broker.lower()!="alpaca": raise HTTPException(400,"Only Alpaca is configured in this build. Select your NSE broker before enabling NSE execution.")
 if not req.paper: raise HTTPException(403,"Live trading is disabled in this build. Use paper trading.")
 try:
  adapter.configure(req.api_key.strip(),req.api_secret.strip(),True)
  a=adapter.account()
  return {"status":"connected","broker":"alpaca","paper":True,"account_status":a.get("status")}
 except Exception as e:
  adapter.client=None;adapter.data=None
  raise HTTPException(400,f"Broker connection failed: {e}")

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
