from __future__ import annotations
import json
from pathlib import Path
from dataclasses import asdict
from typing import Dict
from .strategy import Position

STATE_PATH = Path("state.json")

def load_positions() -> Dict[str, Position]:
    if not STATE_PATH.exists():
        return {}
    raw = json.loads(STATE_PATH.read_text())
    out = {}
    for sym, d in raw.items():
        out[sym] = Position(**d)
    return out

def save_positions(pos: Dict[str, Position]):
    raw = {sym: asdict(p) for sym, p in pos.items()}
    STATE_PATH.write_text(json.dumps(raw, indent=2, default=str))
