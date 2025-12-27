def test_exec_smoke():
    class FakeEx:
        def __init__(self):
            self.ob = {"bids": [[99,1]], "asks": [[101,1]]}
            self.orders = {}
        def fetch_order_book(self,s): return self.ob
        def create_limit_buy_order(self,s,q,p,params=None):
            self.orders["1"]={"id":"1","status":"open","filled":0,"average":p}
            return self.orders["1"]
        def fetch_order(self,i,s): return self.orders[i]
        def cancel_order(self,i,s): self.orders[i]["status"]="canceled"
        def create_market_buy_order(self,s,q): return {"id":"m1","filled":q}
        def create_limit_sell_order(self,s,q,p,params=None): return {"id":"2","status":"closed","filled":q,"average":p}
        def create_market_sell_order(self,s,q): return {"id":"m2","filled":q}
    from beastbot.execution_ccxt import RealBroker, ExecConfig
    ex = FakeEx()
    cfg = ExecConfig({"SOL/USD": 0.2}, {"SOL/USD": 0.5}, order_ttl_sec=0, poll_interval_sec=0.01, post_only=True)
    rb = RealBroker(ex, cfg)
    filled, avg = rb.buy_notional("SOL/USD", 100.0)
    assert filled > 0 and avg > 0
