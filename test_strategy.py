import pandas as pd
from beastbot.config import BotConfig
from beastbot.strategy import Position, apply_tp_decay, choose_raw_tp

def test_tp_decay():
    cfg = BotConfig()
    ts0 = pd.Timestamp("2025-01-01T00:00:00Z")
    pos = Position("DOGE/USD", qty=1, entry_price=100, entry_time=ts0, raw_tp=0.18, tp_price=118)
    ts1 = ts0 + pd.Timedelta(hours=10)
    apply_tp_decay(cfg, pos, ts1)
    assert pos.raw_tp <= 0.18

def test_choose_raw_tp_cap():
    cfg = BotConfig()
    raw = choose_raw_tp(cfg, "SOL/USD", tscore=1.0, w=0.0, x=1.0)
    assert raw <= cfg.tp_cap
