from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass
class RiskState:
    day_start_equity: float = 1.0
    week_start_equity: float = 1.0
    consec_losses: int = 0
    last_day: int = -1
    last_week: int = -1
    halted: bool = False
    reason: str = ""

def _iso_week(dt: datetime) -> int:
    return int(dt.isocalendar().week)

def update_period_starts(rs: RiskState, now: datetime, equity: float):
    day = now.timetuple().tm_yday
    week = _iso_week(now)
    if rs.last_day != day:
        rs.last_day = day
        rs.day_start_equity = equity
        rs.consec_losses = 0
        rs.halted = False
        rs.reason = ""
    if rs.last_week != week:
        rs.last_week = week
        rs.week_start_equity = equity

def check_breakers(rs: RiskState, equity: float, max_daily_dd: float, max_weekly_dd: float, max_consec_losses: int):
    if rs.halted:
        return
    daily_dd = 1 - (equity / rs.day_start_equity) if rs.day_start_equity > 0 else 0
    weekly_dd = 1 - (equity / rs.week_start_equity) if rs.week_start_equity > 0 else 0

    if daily_dd >= max_daily_dd:
        rs.halted = True
        rs.reason = f"DAILY_DD {daily_dd:.3%} >= {max_daily_dd:.3%}"
    elif weekly_dd >= max_weekly_dd:
        rs.halted = True
        rs.reason = f"WEEKLY_DD {weekly_dd:.3%} >= {max_weekly_dd:.3%}"
    elif rs.consec_losses >= max_consec_losses:
        rs.halted = True
        rs.reason = f"CONSEC_LOSSES {rs.consec_losses} >= {max_consec_losses}"

def on_trade_close(rs: RiskState, pnl_pct: float):
    if pnl_pct < 0:
        rs.consec_losses += 1
    else:
        rs.consec_losses = 0
