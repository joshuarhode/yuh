from __future__ import annotations
import numpy as np
import pandas as pd

def ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()

def vwap(df: pd.DataFrame, lookback: int) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = tp * df["volume"]
    return pv.rolling(lookback).sum() / df["volume"].rolling(lookback).sum()

def trend_score_4h(df4: pd.DataFrame) -> pd.Series:
    close = df4["close"]
    e50 = ema(close, 50)
    e200 = ema(close, 200)
    spread = (e50 - e200) / e200
    slope = (e200 - e200.shift(20)) / e200.shift(20)
    hh = (close - close.rolling(20).max()) / close
    ll = (close - close.rolling(20).min()) / close

    def clip(x, d): return np.clip(x / d, -1, 1)
    c1 = clip(spread, 0.05)
    c2 = clip(slope, 0.05)
    c3 = clip(-hh, 0.05)
    c4 = clip(ll, 0.05)
    return (0.35*c1 + 0.30*c2 + 0.20*c3 + 0.15*c4).clip(-1, 1)

def structure_gate(df4: pd.DataFrame, structure_band: float, ema200_slope_block: float) -> pd.Series:
    close = df4["close"]
    e200 = ema(close, 200)
    dist = (close - e200).abs() / e200
    slope = (e200 - e200.shift(20)) / e200.shift(20)
    ok = (close > e200) | ((dist <= structure_band) & (slope > ema200_slope_block))
    return ok.fillna(False)

def entry_signal(df15: pd.DataFrame, lookback: int, vwap_lookback: int, k: float) -> pd.Series:
    vw = vwap(df15, vwap_lookback)
    rets = np.log(df15["close"]).diff()
    sigma_dollars = rets.rolling(lookback).std() * df15["close"]
    sig = df15["close"] <= (vw - k * sigma_dollars)
    return sig.fillna(False)
