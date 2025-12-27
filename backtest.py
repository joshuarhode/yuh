from __future__ import annotations
import pandas as pd
from .config import BotConfig
from .strategy import compute_signals, choose_raw_tp, apply_tp_decay, should_time_stop, apply_infra_burn, Position, wallet_score, x_score

def backtest_symbol(cfg: BotConfig, df15: pd.DataFrame, df4: pd.DataFrame, symbol: str, bankroll_usd: float = 1000.0):
    sig = compute_signals(cfg, df15, df4, symbol)

    equity = 1.0
    pos: Position | None = None
    trades = []

    for ts, row in df15.iterrows():
        # Azure burn every 15m bar
        equity = apply_infra_burn(cfg, equity, hours=0.25)

        price = float(row["close"])
        trend = float(sig["trend"].loc[ts])
        gate = bool(sig["gate"].loc[ts])
        entry = bool(sig["entry"].loc[ts])
        w = wallet_score(symbol)
        x = x_score(symbol)

        if pos:
            apply_tp_decay(cfg, pos, ts)

            if price >= pos.tp_price:
                pnl = (pos.tp_price / pos.entry_price - 1.0) - cfg.total_costs
                equity *= (1 + pnl)
                trades.append({"symbol":symbol,"entry":pos.entry_time,"exit":ts,"reason":"TP","pnl_pct":pnl})
                pos = None
                continue

            if should_time_stop(cfg, pos, ts, w, x):
                pnl = (price / pos.entry_price - 1.0) - cfg.total_costs
                equity *= (1 + pnl)
                trades.append({"symbol":symbol,"entry":pos.entry_time,"exit":ts,"reason":"TIME","pnl_pct":pnl})
                pos = None
                continue

        else:
            if not gate or not entry:
                continue
            raw_tp = choose_raw_tp(cfg, symbol, trend, w, x)
            tp_price = price * (1 + raw_tp + cfg.total_costs)
            notional = bankroll_usd * cfg.max_per_asset_exposure
            if symbol.startswith("DOGE"):
                notional *= cfg.doge_size_mult
            qty = notional / price
            pos = Position(symbol=symbol, qty=qty, entry_price=price, entry_time=ts, raw_tp=raw_tp, tp_price=tp_price)

    return equity, pd.DataFrame(trades)
