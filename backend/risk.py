from dataclasses import dataclass
@dataclass
class RiskConfig:
 risk_per_trade:float=0.01; max_daily_loss:float=0.03; max_positions:int=10; stop_loss_pct:float=0.02; target_pct:float=0.04; max_order_value_pct:float=0.20
def size_position(equity,price,cfg=RiskConfig()):
 if equity<=0 or price<=0:return 0
 return max(0,min(int((equity*cfg.risk_per_trade)/(price*cfg.stop_loss_pct)),int((equity*cfg.max_order_value_pct)/price)))
