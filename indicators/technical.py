"""
常用技术指标计算 — 不依赖第三方 TA 库，纯 pandas/numpy 实现
"""

import pandas as pd
import numpy as np


def sma(series: pd.Series, period: int) -> pd.Series:
    """简单移动平均"""
    return series.rolling(window=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """指数移动平均"""
    return series.ewm(span=period, adjust=False).mean()


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """
    MACD 指标。

    Returns:
        DataFrame 包含 DIF, DEA, MACD_hist 三列
    """
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    dif = ema_fast - ema_slow
    dea = ema(dif, signal)
    hist = 2 * (dif - dea)
    return pd.DataFrame({"DIF": dif, "DEA": dea, "MACD_hist": hist})


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """相对强弱指标 RSI"""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def bollinger(close: pd.Series, period: int = 20, std_dev: int = 2) -> pd.DataFrame:
    """
    布林带。

    Returns:
        DataFrame 包含 upper, middle, lower 三列
    """
    middle = sma(close, period)
    std = close.rolling(window=period).std()
    return pd.DataFrame({
        "upper": middle + std_dev * std,
        "middle": middle,
        "lower": middle - std_dev * std,
    })


def volume_ratio(volume: pd.Series, period: int = 5) -> pd.Series:
    """量比：当日成交量 / 过去N日均量"""
    avg_vol = volume.rolling(window=period).mean()
    return volume / avg_vol


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    """
    一次性计算所有常用指标，添加到原 DataFrame 中。

    Args:
        df: 包含 open, high, low, close, volume 列的 DataFrame

    Returns:
        添加了指标列的新 DataFrame
    """
    result = df.copy()
    close = result["close"]

    result["ma5"] = sma(close, 5)
    result["ma10"] = sma(close, 10)
    result["ma20"] = sma(close, 20)
    result["ma60"] = sma(close, 60)

    macd_df = macd(close)
    result["dif"] = macd_df["DIF"]
    result["dea"] = macd_df["DEA"]
    result["macd_hist"] = macd_df["MACD_hist"]

    result["rsi14"] = rsi(close, 14)

    bb = bollinger(close)
    result["bb_upper"] = bb["upper"]
    result["bb_middle"] = bb["middle"]
    result["bb_lower"] = bb["lower"]

    result["vol_ratio"] = volume_ratio(result["volume"])

    result["returns"] = close.pct_change()
    result["log_returns"] = np.log(close / close.shift(1))

    return result
