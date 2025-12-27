from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from .telemetry import log, alert

@dataclass
class CrashGuard:
    count: int = 0
    last: datetime | None = None

    def hit(self, exc: Exception, window_minutes: int = 30, max_crashes: int = 3):
        now = datetime.now(timezone.utc)
        if self.last and (now - self.last) < timedelta(minutes=window_minutes):
            self.count += 1
        else:
            self.count = 1
        self.last = now
        alert(f"CRASH {self.count}: {exc}")
        log({"event":"CRASH", "count":self.count, "err":str(exc)})
        if self.count >= max_crashes:
            raise SystemExit(f"Crash loop: {self.count} crashes in {window_minutes}m")

def assert_fresh(latest_ts, max_age_minutes: int = 30):
    now = datetime.now(timezone.utc)
    age = (now - latest_ts.to_pydatetime()).total_seconds() / 60.0
    if age > max_age_minutes:
        msg = f"STALE_DATA age={age:.1f}m"
        alert(msg)
        raise RuntimeError(msg)
