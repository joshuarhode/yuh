from __future__ import annotations
import random
import numpy as np
import pandas as pd
from dataclasses import replace
from .config import BotConfig
from .backtest import backtest_symbol

def max_drawdown(eq: pd.Series) -> float:
    peak = eq.cummax()
    dd = (eq/peak) - 1.0
    return float(dd.min()) if len(dd) else 0.0

def score_from_trades(final_eq: float, trades: pd.DataFrame) -> float:
    # crude risk-adjusted score
    ret = final_eq - 1.0
    n = len(trades) if trades is not None else 0
    # churn penalty
    churn = n / 2000.0
    # penalty if too few trades (dead bot)
    dead = 0.02 if n < 3 else 0.0
    return float(ret - 0.2*churn - dead)

def make_splits(index: pd.DatetimeIndex, train_days=45, test_days=15, step_days=15):
    idx = index.sort_values()
    cur = idx[0]
    end = idx[-1]
    splits = []
    while True:
        tr_s = cur
        tr_e = tr_s + pd.Timedelta(days=train_days)
        te_s = tr_e
        te_e = te_s + pd.Timedelta(days=test_days)
        if te_e > end:
            break
        splits.append((tr_s, tr_e, te_s, te_e))
        cur = cur + pd.Timedelta(days=step_days)
    return splits

def sample_cfg(base: BotConfig, rng: random.Random) -> BotConfig:
    # sample a few knobs; keep ranges realistic
    total_costs = rng.uniform(0.003, 0.008)
    k_sol = rng.uniform(1.7, 2.4)
    k_doge = rng.uniform(2.0, 2.9)
    base_tp_sol = rng.uniform(0.05, 0.10)
    base_tp_doge = rng.uniform(0.06, 0.14)
    boost_tp_sol = rng.uniform(max(base_tp_sol+0.03, 0.10), 0.18)
    boost_tp_doge = rng.uniform(max(base_tp_doge+0.04, 0.12), 0.20)

    return BotConfig(
        total_costs=total_costs,
        symbols=base.symbols,
        bankroll_usd=base.bankroll_usd,
        azure_monthly_usd=base.azure_monthly_usd,
        max_total_exposure=base.max_total_exposure,
        max_per_asset_exposure=base.max_per_asset_exposure,
        doge_size_mult=base.doge_size_mult,
        structure_band=base.structure_band,
        ema200_slope_block=base.ema200_slope_block,
        entry_lookback_15m=base.entry_lookback_15m,
        vwap_lookback_15m=base.vwap_lookback_15m,
        tp_cap=base.tp_cap,
        tp_decay_at_h=base.tp_decay_at_h,
        tp_decay_mult=base.tp_decay_mult,
        time_stop_h=base.time_stop_h,
        time_ext_h=base.time_ext_h,
        trend_permissive=base.trend_permissive,
        wallet_bearish=base.wallet_bearish,
        wallet_supportive=base.wallet_supportive,
        x_boost=base.x_boost,
    )

def optimize(base_cfg: BotConfig, df15_by_sym: dict, df4_by_sym: dict, trials=200, seed=42):
    rng = random.Random(seed)
    # common index
    common = None
    for sym in base_cfg.symbols:
        idx = df15_by_sym[sym].index
        common = idx if common is None else common.intersection(idx)
    splits = make_splits(common, 45, 15, 15)
    if len(splits) < 3:
        raise RuntimeError("Not enough data for walk-forward splits")

    best_cfg = base_cfg
    best_score = -1e9

    for i in range(trials):
        cfg = sample_cfg(base_cfg, rng)
        # patch k + tp dicts
        cfg.k_band["SOL/USD"] = rng.uniform(1.7, 2.4)
        cfg.k_band["DOGE/USD"] = rng.uniform(2.0, 2.9)
        cfg.base_tp["SOL/USD"] = rng.uniform(0.05, 0.10)
        cfg.base_tp["DOGE/USD"] = rng.uniform(0.06, 0.14)
        cfg.boost_tp["SOL/USD"] = rng.uniform(max(cfg.base_tp["SOL/USD"]+0.03, 0.10), 0.18)
        cfg.boost_tp["DOGE/USD"] = rng.uniform(max(cfg.base_tp["DOGE/USD"]+0.04, 0.12), 0.20)

        scores = []
        for _, _, te_s, te_e in splits:
            for sym in base_cfg.symbols:
                df15 = df15_by_sym[sym].loc[te_s:te_e]
                df4  = df4_by_sym[sym].loc[te_s:te_e]
                eq, trades = backtest_symbol(cfg, df15, df4, sym, bankroll_usd=base_cfg.bankroll_usd)
                scores.append(score_from_trades(eq, trades))
        sc = float(np.mean(scores)) if scores else -1e9
        if sc > best_score:
            best_score = sc
            best_cfg = cfg
            print(f"[best] {i+1}/{trials} score={best_score:.6f} costs={cfg.total_costs:.4f} "
                  f"k_sol={cfg.k_band['SOL/USD']:.2f} k_doge={cfg.k_band['DOGE/USD']:.2f} "
                  f"tp_sol={cfg.base_tp['SOL/USD']:.2f}/{cfg.boost_tp['SOL/USD']:.2f} "
                  f"tp_doge={cfg.base_tp['DOGE/USD']:.2f}/{cfg.boost_tp['DOGE/USD']:.2f}")
    return best_cfg
