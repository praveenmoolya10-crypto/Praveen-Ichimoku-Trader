from dataclasses import dataclass

@dataclass
class RiskConfig:
    risk_per_trade:float=0.01
    max_daily_loss:float=0.03
    max_positions:int=10
    stop_loss_pct:float=0.02
    target_pct:float=0.04

def size_position(equity, price, cfg=RiskConfig()):
    if price<=0:return 0
    risk_cash=equity*cfg.risk_per_trade
    return max(0,int(risk_cash/(price*cfg.stop_loss_pct)))
