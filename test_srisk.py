from datetime import datetime, timezone
from beastbot.risk import RiskState, update_period_starts, check_breakers, on_trade_close

def test_daily_dd_halt():
    rs = RiskState()
    now = datetime.now(timezone.utc)
    update_period_starts(rs, now, 1.0)
    check_breakers(rs, 0.95, 0.03, 0.50, 99)
    assert rs.halted

def test_consec_losses_halt():
    rs = RiskState()
    for _ in range(4):
        on_trade_close(rs, -0.01)
    check_breakers(rs, 1.0, 0.99, 0.99, 4)
    assert rs.halted
