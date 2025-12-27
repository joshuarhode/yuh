from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import List, Union

import pandas as pd

from .telemetry import log


def _parse_timeframe(tf: str):
    """Accepts strings like '1Hour', '15Min', '1Day', '4H' and returns an alpaca-py TimeFrame."""
    try:
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    except Exception as e:  # pragma: no cover
        raise RuntimeError("alpaca-py is required for data fetching. Install: pip install alpaca-py") from e

    tf = tf.strip()

    # Normalize common shorthand
    if tf.upper().endswith("H") and tf[:-1].isdigit():
        n = int(tf[:-1])
        return TimeFrame(n, TimeFrameUnit.Hour)

    m = re.fullmatch(r"(\d+)(Min|Minute|Minutes|Hour|H|Day|D)", tf, flags=re.IGNORECASE)
    if not m:
        # fall back to 1Hour
        return TimeFrame(1, TimeFrameUnit.Hour)

    n = int(m.group(1))
    unit = m.group(2).lower()
    if unit in ("min", "minute", "minutes"):
        return TimeFrame(n, TimeFrameUnit.Minute)
    if unit in ("hour", "h"):
        return TimeFrame(n, TimeFrameUnit.Hour)
    if unit in ("day", "d"):
        return TimeFrame(n, TimeFrameUnit.Day)

    return TimeFrame(1, TimeFrameUnit.Hour)


def fetch_crypto_bars(symbol: Union[str, List[str]], days: int, timeframe: str) -> pd.DataFrame:
    """Fetch crypto OHLCV bars from Alpaca using alpaca-py.

    Returns a DataFrame indexed by UTC timestamp with columns:
    open, high, low, close, volume

    Notes:
    - Requires APCA_API_KEY_ID and APCA_API_SECRET_KEY in env/.env.
    - This implementation is for running locally or on your own server.
    """

    api_key = os.getenv("APCA_API_KEY_ID")
    api_secret = os.getenv("APCA_API_SECRET_KEY")
    if not api_key or not api_secret:
        raise RuntimeError(
            "Missing Alpaca keys. Set APCA_API_KEY_ID and APCA_API_SECRET_KEY in your environment or .env file."
        )

    from alpaca.data.historical import CryptoHistoricalDataClient
    from alpaca.data.requests import CryptoBarsRequest

    tf = _parse_timeframe(timeframe)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    client = CryptoHistoricalDataClient(api_key, api_secret)
    req = CryptoBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=tf,
        start=start,
        end=end,
        feed="us",
    )

    resp = client.get_crypto_bars(req)
    df = resp.df
    if df is None or df.empty:
        raise RuntimeError(f"No bars returned for {symbol} ({timeframe}, {days}d)")

    # alpaca-py returns MultiIndex (symbol, timestamp) when multiple symbols.
    # When a single symbol is requested, it may still be multi-indexed depending on version.
    if isinstance(df.index, pd.MultiIndex):
        # If symbol is a list, user likely wants one dataframe per symbol; our bot calls per-symbol.
        if isinstance(symbol, str):
            try:
                df = df.xs(symbol)
            except Exception:
                # sometimes the index level name differs; fall back to selecting the first level value
                df = df[df.index.get_level_values(0) == symbol]
                df.index = df.index.get_level_values(-1)
        else:
            # collapse by timestamp; keep the last symbol encountered (not ideal, but avoids crashing)
            df = df.reset_index().set_index("timestamp").sort_index()

    # Ensure UTC index
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    # Keep/rename columns to match bot expectations
    cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[cols].copy().sort_index()

    log({"event": "DATA", "symbol": str(symbol), "rows": int(len(df)), "timeframe": timeframe})
    return df
