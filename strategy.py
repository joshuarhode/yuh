from __future__ import annotations
from dataclasses import dataclass
import pandas as pd

from .config import BotConfig, azure_hourly_usd
from .indicators import trend_score_4h, structure_gate, entry_signal

@dataclass
class Position:
    symbol: str
    qty: float
    entry_price: float
    entry_time: pd.Timestamp
    raw_tp: float
    tp_price: float
    extended: bool = False

# Stubs: wire later (do NOT let them trigger entries)
def wallet_score(_symbol: str) -> float:
    return 0.0

def x_score(_symbol: str) -> float:
    return 0.0

def apply_infra_burn(cfg: BotConfig, equity: float, hours: float) -> float:
    burn = azure_hourly_usd(cfg) * hours
    burn_pct = burn / cfg.bankroll_usd
    return max(0.0, equity * (1.0 - burn_pct))

def compute_signals(cfg: BotConfig, df15: pd.DataFrame, df4: pd.DataFrame, symbol: str) -> dict:
    t = trend_score_4h(df4).reindex(df15.index, method="ffill")
    g = structure_gate(df4, cfg.structure_band, cfg.ema200_slope_block).reindex(df15.index, method="ffill")
    e = entry_signal(df15, cfg.entry_lookback_15m, cfg.vwap_lookback_15m, cfg.k_band[symbol])
    return {"trend": t, "gate": g, "entry": e}

def choose_raw_tp(cfg: BotConfig, symbol: str, tscore: float, w: float, x: float) -> float:
    raw = cfg.base_tp[symbol]
    boost_ok = (tscore > cfg.trend_permissive) and (w >= cfg.wallet_bearish) and (x > cfg.x_boost)
    if boost_ok:
        raw = min(cfg.boost_tp[symbol], cfg.tp_cap)
    return raw

def apply_tp_decay(cfg: BotConfig, pos: Position, now: pd.Timestamp):
    now_ts = pd.Timestamp(now)
    entry_ts = pd.Timestamp(pos.entry_time)
    hours_in = (now_ts - entry_ts) / pd.Timedelta(hours=1)
    if hours_in >= cfg.tp_decay_at_h[pos.symbol]:
        pos.raw_tp = min(pos.raw_tp * cfg.tp_decay_mult, cfg.tp_cap)
        pos.tp_price = pos.entry_price * (1 + pos.raw_tp + cfg.total_costs)

def should_time_stop(cfg: BotConfig, pos: Position, now: pd.Timestamp, w: float, x: float) -> bool:
    now_ts = pd.Timestamp(now)
    entry_ts = pd.Timestamp(pos.entry_time)
    hours_in = (now_ts - entry_ts) / pd.Timedelta(hours=1)
    base = cfg.time_stop_h[pos.symbol]
    ext = cfg.time_ext_h[pos.symbol]

    if hours_in >= base and not pos.extended:
        if (w > cfg.wallet_supportive) and (x > cfg.x_boost):
            pos.extended = True
            return False
        return True
    if pos.extended and hours_in >= ext:
        return True
    return False
