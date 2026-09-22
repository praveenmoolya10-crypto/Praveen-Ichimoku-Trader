import os
from datetime import datetime,timedelta,timezone
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide,TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

class AlpacaAdapter:
 def __init__(self):
  key=os.getenv("ALPACA_API_KEY"); secret=os.getenv("ALPACA_SECRET_KEY")
  if not key or not secret:self.client=None;self.data=None;return
  self.client=TradingClient(key,secret,paper=True);self.data=StockHistoricalDataClient(key,secret)
 def configured(self):return self.client is not None
 def account(self):
  if not self.client:return {"status":"not_configured"}
  a=self.client.get_account();return {"equity":str(a.equity),"cash":str(a.cash),"buying_power":str(a.buying_power),"status":str(a.status)}
 def positions(self):
  if not self.client:return []
  return [p.model_dump(mode="json") for p in self.client.get_all_positions()]
 def orders(self,status=None):
  if not self.client:return []
  return [o.model_dump(mode="json") for o in self.client.get_orders(status=status) if status] if status else [o.model_dump(mode="json") for o in self.client.get_orders()]
 def order(self,order_id):
  if not self.client:raise RuntimeError("Alpaca is not configured")
  return self.client.get_order_by_id(order_id).model_dump(mode="json")
 def bars(self,symbol,timeframe="1Day",limit=200):
  if not self.data:return {"bars":{symbol.upper():[]}}
  tf=TimeFrame.Day if timeframe=="1Day" else TimeFrame.Minute
  req=StockBarsRequest(symbol_or_symbols=symbol.upper(),timeframe=tf,start=datetime.now(timezone.utc)-timedelta(days=max(limit*3,30)),limit=limit)
  raw=self.data.get_stock_bars(req).data.get(symbol.upper(),[])
  return {"bars":{symbol.upper():[{"t":x.timestamp.isoformat(),"o":x.open,"h":x.high,"l":x.low,"c":x.close,"v":x.volume} for x in raw]}}
 def place_order(self,symbol,side,qty,order_type="market",tif="day",client_order_id=None):
  if not self.client:raise RuntimeError("Alpaca is not configured")
  req=MarketOrderRequest(symbol=symbol.upper(),qty=qty,side=OrderSide.BUY if side.lower()=="buy" else OrderSide.SELL,time_in_force=TimeInForce.DAY,client_order_id=client_order_id)
  return self.client.submit_order(req).model_dump(mode="json")
