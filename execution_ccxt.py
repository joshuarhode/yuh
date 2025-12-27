from __future__ import annotations
import os, time
from dataclasses import dataclass
import ccxt

from .telemetry import log

@dataclass
class ExecConfig:
    max_spread_pct: dict
    max_slip_pct: dict
    order_ttl_sec: int = 20
    poll_interval_sec: float = 1.0
    post_only: bool = True

def make_exchange() -> ccxt.Exchange:
    ex_id = os.getenv("EXCHANGE_ID", "coinbase")
    klass = getattr(ccxt, ex_id)
    params = {
        "apiKey": os.getenv("EXCHANGE_API_KEY"),
        "secret": os.getenv("EXCHANGE_API_SECRET"),
        "enableRateLimit": True,
    }
    pw = os.getenv("EXCHANGE_API_PASSPHRASE")
    if pw:
        params["password"] = pw
    return klass(params)

class RealBroker:
    def __init__(self, exchange: ccxt.Exchange, cfg: ExecConfig):
        self.ex = exchange
        self.cfg = cfg

    def _mid_spread(self, symbol: str):
        ob = self.ex.fetch_order_book(symbol)
        bid = ob["bids"][0][0] if ob["bids"] else None
        ask = ob["asks"][0][0] if ob["asks"] else None
        if bid is None or ask is None:
            raise RuntimeError("Empty orderbook")
        mid = (bid + ask) / 2
        spread = (ask - bid) / mid
        return float(mid), float(spread), float(bid), float(ask)

    def _abort_if_bad(self, symbol: str):
        mid, spread, bid, ask = self._mid_spread(symbol)
        if spread > self.cfg.max_spread_pct[symbol]:
            raise RuntimeError(f"Spread too wide {spread:.4%} > {self.cfg.max_spread_pct[symbol]:.4%}")
        return mid, bid, ask

    def buy_notional(self, symbol: str, notional_usd: float) -> tuple[float, float]:
        mid, bid, ask = self._abort_if_bad(symbol)
        qty = notional_usd / mid

        # limit-first post-only on bid
        limit_price = bid
        params = {"postOnly": self.cfg.post_only} if self.cfg.post_only else {}
        log({"event":"ORDER_SUBMIT","side":"buy","type":"limit","symbol":symbol,"qty":qty,"price":limit_price})
        order = self.ex.create_limit_buy_order(symbol, qty, limit_price, params=params)

        start = time.time()
        filled = 0.0
        cost = 0.0

        while True:
            o = self.ex.fetch_order(order["id"], symbol)
            f = float(o.get("filled") or 0.0)
            avg = o.get("average") or limit_price
            filled = f
            cost = f * float(avg)

            if o.get("status") in ("closed", "filled") or (qty > 0 and f >= qty * 0.999):
                break

            if time.time() - start >= self.cfg.order_ttl_sec:
                log({"event":"ORDER_TTL","symbol":symbol,"order_id":order["id"],"filled":filled})
                try:
                    self.ex.cancel_order(order["id"], symbol)
                except Exception:
                    pass
                break

            time.sleep(self.cfg.poll_interval_sec)

        remaining = max(0.0, qty - filled)
        if remaining > 0:
            mid2, _, _ = self._abort_if_bad(symbol)
            slip = abs(mid2 - mid) / mid
            if slip > self.cfg.max_slip_pct[symbol]:
                raise RuntimeError(f"Slippage too high {slip:.4%} > {self.cfg.max_slip_pct[symbol]:.4%}")
            log({"event":"ORDER_FALLBACK","side":"buy","type":"market","symbol":symbol,"qty":remaining})
            mo = self.ex.create_market_buy_order(symbol, remaining)
            # best effort average
            try:
                mo2 = self.ex.fetch_order(mo["id"], symbol)
                f2 = float(mo2.get("filled") or remaining)
                a2 = float(mo2.get("average") or mid2)
            except Exception:
                f2, a2 = remaining, mid2
            filled += f2
            cost += f2 * a2

        if filled <= 0:
            raise RuntimeError("Buy failed: 0 filled")
        avg_price = cost / filled
        log({"event":"ORDER_DONE","side":"buy","symbol":symbol,"filled_qty":filled,"avg_price":avg_price})
        return filled, avg_price

    def sell_qty(self, symbol: str, qty: float) -> tuple[float, float]:
        mid, bid, ask = self._abort_if_bad(symbol)

        # limit-first post-only on ask
        limit_price = ask
        params = {"postOnly": self.cfg.post_only} if self.cfg.post_only else {}
        log({"event":"ORDER_SUBMIT","side":"sell","type":"limit","symbol":symbol,"qty":qty,"price":limit_price})
        order = self.ex.create_limit_sell_order(symbol, qty, limit_price, params=params)

        start = time.time()
        filled = 0.0
        proceeds = 0.0

        while True:
            o = self.ex.fetch_order(order["id"], symbol)
            f = float(o.get("filled") or 0.0)
            avg = o.get("average") or limit_price
            filled = f
            proceeds = f * float(avg)

            if o.get("status") in ("closed","filled") or (qty > 0 and f >= qty * 0.999):
                break

            if time.time() - start >= self.cfg.order_ttl_sec:
                log({"event":"ORDER_TTL","symbol":symbol,"order_id":order["id"],"filled":filled})
                try:
                    self.ex.cancel_order(order["id"], symbol)
                except Exception:
                    pass
                break

            time.sleep(self.cfg.poll_interval_sec)

        remaining = max(0.0, qty - filled)
        if remaining > 0:
            mid2, _, _ = self._abort_if_bad(symbol)
            slip = abs(mid2 - mid) / mid
            if slip > self.cfg.max_slip_pct[symbol]:
                raise RuntimeError(f"Slippage too high {slip:.4%} > {self.cfg.max_slip_pct[symbol]:.4%}")
            log({"event":"ORDER_FALLBACK","side":"sell","type":"market","symbol":symbol,"qty":remaining})
            mo = self.ex.create_market_sell_order(symbol, remaining)
            try:
                mo2 = self.ex.fetch_order(mo["id"], symbol)
                f2 = float(mo2.get("filled") or remaining)
                a2 = float(mo2.get("average") or mid2)
            except Exception:
                f2, a2 = remaining, mid2
            filled += f2
            proceeds += f2 * a2

        if filled <= 0:
            raise RuntimeError("Sell failed: 0 filled")
        avg_price = proceeds / filled
        log({"event":"ORDER_DONE","side":"sell","symbol":symbol,"filled_qty":filled,"avg_price":avg_price})
        return filled, avg_price
