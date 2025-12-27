from __future__ import annotations
from dataclasses import dataclass
import os

@dataclass(frozen=True)
class BotConfig:
    symbols: tuple[str, ...] = ("SOL/USD", "DOGE/USD")

    # execution + structure timeframes
    exec_tf: str = "15min"
    struct_tf: str = "4H"

    # costs (fees+slippage baseline). You can optimize this too, but keep it conservative.
    total_costs: float = 0.0050

    # Azure burn
    bankroll_usd: float = float(os.getenv("BANKROLL_USD", "1000"))
    azure_monthly_usd: float = float(os.getenv("AZURE_MONTHLY_USD", "40"))

    # exposure
    max_total_exposure: float = 0.60
    max_per_asset_exposure: float = 0.30
    doge_size_mult: float = 0.70

    # structure gate
    structure_band: float = 0.08
    ema200_slope_block: float = -0.0015

    # entry bands
    entry_lookback_15m: int = 96
    vwap_lookback_15m: int = 96
    k_band = {"SOL/USD": 2.0, "DOGE/USD": 2.3}

    # TP tiers
    base_tp = {"SOL/USD": 0.08, "DOGE/USD": 0.10}
    boost_tp = {"SOL/USD": 0.15, "DOGE/USD": 0.18}
    tp_cap: float = 0.20

    # TP decay + time stops
    tp_decay_at_h = {"SOL/USD": 18, "DOGE/USD": 9}
    tp_decay_mult: float = 0.75
    time_stop_h = {"SOL/USD": 24, "DOGE/USD": 12}
    time_ext_h  = {"SOL/USD": 36, "DOGE/USD": 18}

    # boost thresholds
    trend_permissive: float = 0.10
    wallet_bearish: float = -0.50
    wallet_supportive: float = 0.30
    x_boost: float = 0.50

    # live execution safety
    max_spread_pct = {"SOL/USD": 0.0020, "DOGE/USD": 0.0030}
    max_slip_pct   = {"SOL/USD": 0.0040, "DOGE/USD": 0.0060}
    order_ttl_sec: int = 20
    poll_interval_sec: float = 1.0
    post_only: bool = True

    # risk breakers
    max_daily_dd_pct: float = float(os.getenv("MAX_DAILY_DD_PCT", "0.03"))
    max_weekly_dd_pct: float = float(os.getenv("MAX_WEEKLY_DD_PCT", "0.07"))
    max_consec_losses: int = int(os.getenv("MAX_CONSEC_LOSSES", "4"))

def azure_hourly_usd(cfg: BotConfig) -> float:
    return (cfg.azure_monthly_usd / 30.0) / 24.0
