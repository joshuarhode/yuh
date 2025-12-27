"""Compatibility wrapper.

Older code referenced beastbot.alpaca.fetch_crypto_bars.
The real implementation lives in beastbot.data_alpaca_tool.fetch_crypto_bars.
"""

from .data_alpaca_tool import fetch_crypto_bars  # noqa: F401
