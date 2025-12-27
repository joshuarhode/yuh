import pandas as pd
from beastbot.indicators import ema, vwap

def test_ema_constant():
    s = pd.Series([5.0]*200)
    e = ema(s, 50)
    assert float(e.iloc[-1]) == 5.0

def test_vwap_flat():
    df = pd.DataFrame({
        "high":[2,2,2,2],
        "low":[1,1,1,1],
        "close":[1.5,1.5,1.5,1.5],
        "volume":[10,10,10,10],
    })
    vw = vwap(df, 4)
    assert abs(float(vw.iloc[-1]) - 1.5) < 1e-9
