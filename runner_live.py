from __future__ import annotations
from dotenv import load_dotenv
import time
import pandas as pd
from datetime import datetime, timezone

from .config import BotConfig
from .telemetry import log, alert
from .watchdog import CrashGuard
from .risk import RiskState, update_period_starts, check_breakers, on_trade_close
from .strategy import compute_signals, choose_raw_tp, apply_tp_decay, should_time_stop, apply_infra_burn, Position, wallet_score, x_score
from .state import load_positions, save_positions
from .execution_ccxt import make_exchange, RealBroker, ExecConfig
from .data_alpaca_tool import fetch_crypto_bars

def resample_15m_4h(df: pd.DataFrame):
    df15 = df.resample("15min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    df4  = df.resample("4H").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    return df15, df4

def run():
    load_dotenv()
    cfg = BotConfig()
    ex = make_exchange()
    broker = RealBroker(ex, ExecConfig(cfg.max_spread_pct, cfg.max_slip_pct, cfg.order_ttl_sec, cfg.poll_interval_sec, cfg.post_only))

    rs = RiskState()
    guard = CrashGuard()

    positions = load_positions()
    equity = 1.0

    while True:
        try:
            now = datetime.now(timezone.utc)
            update_period_starts(rs, now, equity)
            check_breakers(rs, equity, cfg.max_daily_dd_pct, cfg.max_weekly_dd_pct, cfg.max_consec_losses)

            # infra burn per 15m tick
            equity = apply_infra_burn(cfg, equity, hours=0.25)

            if rs.halted:
                log({"event":"HALTED","reason":rs.reason,"equity":equity})
                time.sleep(60)
                continue

            for sym in cfg.symbols:
                # fetch recent bars (1Hour) and resample
                dfh = fetch_crypto_bars(sym, days=7, timeframe="1Hour")
                df15, df4 = resample_15m_4h(dfh)
                if len(df15) < 150 or len(df4) < 80:
                    continue

                sig = compute_signals(cfg, df15, df4, sym)
                ts = df15.index[-1]
                price = float(df15["close"].iloc[-1])
                trend = float(sig["trend"].iloc[-1])
                gate = bool(sig["gate"].iloc[-1])
                entry = bool(sig["entry"].iloc[-1])
                w = wallet_score(sym); x = x_score(sym)

                if sym in positions:
                    pos = positions[sym]
                    apply_tp_decay(cfg, pos, ts)

                    # TP exit
                    if price >= pos.tp_price:
                        filled_qty, avg = broker.sell_qty(sym, pos.qty)
                        pnl = (avg / pos.entry_price - 1.0) - cfg.total_costs
                        equity *= (1 + pnl)
                        on_trade_close(rs, pnl)
                        log({"t": ts, "event":"EXIT_TP", "sym":sym, "avg":avg, "pnl_pct":pnl, "equity":equity})
                        del positions[sym]; save_positions(positions)
                        continue

                    # Time exit
                    if should_time_stop(cfg, pos, ts, w, x):
                        filled_qty, avg = broker.sell_qty(sym, pos.qty)
                        pnl = (avg / pos.entry_price - 1.0) - cfg.total_costs
                        equity *= (1 + pnl)
                        on_trade_close(rs, pnl)
                        log({"t": ts, "event":"EXIT_TIME", "sym":sym, "avg":avg, "pnl_pct":pnl, "equity":equity})
                        del positions[sym]; save_positions(positions)
                        continue

                else:
                    if not gate or not entry:
                        continue

                    # Notional sizing
                    notional = cfg.bankroll_usd * cfg.max_per_asset_exposure
                    if sym.startswith("DOGE"):
                        notional *= cfg.doge_size_mult

                    raw_tp = choose_raw_tp(cfg, sym, trend, w, x)

                    filled_qty, avg = broker.buy_notional(sym, notional)
                    tp_price = avg * (1 + raw_tp + cfg.total_costs)

                    positions[sym] = Position(sym, filled_qty, avg, ts, raw_tp, tp_price)
                    save_positions(positions)
                    log({"t": ts, "event":"ENTRY", "sym":sym, "avg":avg, "qty":filled_qty,
                         "raw_tp":raw_tp, "tp_price":tp_price, "trend":trend, "equity":equity})

            # loop every minute, signals based on latest 15m bar anyway
            time.sleep(60)

        except Exception as e:
            guard.hit(e)
            time.sleep(5)

if __name__ == "__main__":
    run()
