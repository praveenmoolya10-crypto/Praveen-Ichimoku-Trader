import pandas as pd

def ichimoku(bars):
    if not bars:return []
    df=pd.DataFrame(bars)
    h=df["h"].astype(float); l=df["l"].astype(float); c=df["c"].astype(float)
    tenkan=(h.rolling(9).max()+l.rolling(9).min())/2
    kijun=(h.rolling(26).max()+l.rolling(26).min())/2
    span_a=((tenkan+kijun)/2).shift(26)
    span_b=((h.rolling(52).max()+l.rolling(52).min())/2).shift(26)
    chikou=c.shift(-26)
    out=pd.DataFrame({"close":c,"tenkan":tenkan,"kijun":kijun,"span_a":span_a,"span_b":span_b,"chikou":chikou}).dropna()
    return out.to_dict("records")

def signal(rows):
    if not rows:return "HOLD"
    x=rows[-1]; cloud_top=max(x["span_a"],x["span_b"]); cloud_bottom=min(x["span_a"],x["span_b"])
    bullish=x["close"]>cloud_top and x["tenkan"]>x["kijun"]
    bearish=x["close"]<cloud_bottom and x["tenkan"]<x["kijun"]
    if bullish:return "BUY"
    if bearish:return "SELL"
    return "HOLD"
