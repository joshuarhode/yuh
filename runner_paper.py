from __future__ import annotations
from dotenv import load_dotenv
import pandas as pd

from .config import BotConfig
from .data_alpaca_tool import fetch_crypto_bars
from .telemetry import log
from .risk import RiskState, update_period_starts, check_breakers, on_trade_close
from .strategy import compute_signals, choose_raw_tp, apply_tp_decay, should_time_stop, apply_infra_burn, Position, wallet_score, x_score
from .state import load_positions, save_positions
from datetime import datetime, timezone

def resample_15m_4h(df: pd.DataFrame):
    df15 = df.resample("15min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    df4  = df.resample("4h").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    return df15, df4

def run(days: int = 30):
    load_dotenv()
    cfg = BotConfig()
    rs = RiskState()
    equity = 1.0
    positions = load_positions()

    data = {}
    sigs = {}

    for sym in cfg.symbols:
        # Pull 1Hour bars and resample, since connector parsing minute bars may vary.
        dfh = fetch_crypto_bars(sym, days=days, timeframe="1Hour")
        df15, df4 = resample_15m_4h(dfh)
        data[sym] = (df15, df4)
        sigs[sym] = compute_signals(cfg, df15, df4, sym)

    common = None
    for sym in cfg.symbols:
        idx = data[sym][0].index
        common = idx if common is None else common.intersection(idx)

    for ts in common:
        # Use the simulated timestamp for risk windows (daily/weekly DD), not wall-clock time.
        _ts = pd.Timestamp(ts)
        now = _ts.to_pydatetime()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        update_period_starts(rs, now, equity)
        check_breakers(rs, equity, cfg.max_daily_dd_pct, cfg.max_weekly_dd_pct, cfg.max_consec_losses)

        equity = apply_infra_burn(cfg, equity, hours=0.25)

        if rs.halted:
            log({"t": ts, "event":"HALTED", "reason": rs.reason, "equity": equity})
            continue

        for sym in cfg.symbols:
            df15, _ = data[sym]
            price = float(df15.loc[ts, "close"])
            trend = float(sigs[sym]["trend"].loc[ts])
            gate = bool(sigs[sym]["gate"].loc[ts])
            entry = bool(sigs[sym]["entry"].loc[ts])
            w = wallet_score(sym); x = x_score(sym)

            if sym in positions:
                pos = positions[sym]
                apply_tp_decay(cfg, pos, ts)

                if price >= pos.tp_price:
                    pnl = (pos.tp_price / pos.entry_price - 1.0) - cfg.total_costs
                    equity *= (1 + pnl)
                    on_trade_close(rs, pnl)
                    log({"t": ts, "event":"EXIT_TP", "sym":sym, "pnl_pct":pnl, "equity":equity})
                    del positions[sym]; save_positions(positions)
                    continue

                if should_time_stop(cfg, pos, ts, w, x):
                    pnl = (price / pos.entry_price - 1.0) - cfg.total_costs
                    equity *= (1 + pnl)
                    on_trade_close(rs, pnl)
                    log({"t": ts, "event":"EXIT_TIME", "sym":sym, "pnl_pct":pnl, "equity":equity})
                    del positions[sym]; save_positions(positions)
                    continue

            else:
                if not gate or not entry:
                    continue
                notional = cfg.bankroll_usd * cfg.max_per_asset_exposure
                if sym.startswith("DOGE"):
                    notional *= cfg.doge_size_mult
                qty = notional / price
                raw_tp = choose_raw_tp(cfg, sym, trend, w, x)
                tp_price = price * (1 + raw_tp + cfg.total_costs)
                positions[sym] = Position(sym, qty, price, ts, raw_tp, tp_price)
                save_positions(positions)
                log({"t": ts, "event":"ENTRY", "sym":sym, "price":price, "qty":qty,
                     "raw_tp":raw_tp, "tp_price":tp_price, "trend":trend, "equity":equity})

    log({"event":"DONE", "equity":equity, "open_positions": list(positions.keys())})

if __name__ == "__main__":
    run(30)