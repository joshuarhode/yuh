from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Fill:
    qty: float
    price: float

class PaperBroker:
    def buy_notional(self, symbol: str, notional_usd: float, price: float) -> Fill:
        return Fill(qty=notional_usd/price, price=price)

    def sell_qty(self, symbol: str, qty: float, price: float) -> Fill:
        return Fill(qty=qty, price=price)
