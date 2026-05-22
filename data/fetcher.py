"""
数据获取模块 — 支持 A股 (akshare/新浪财经) 和美股 (yfinance)
"""

import pandas as pd
from datetime import datetime
from typing import Optional


def _add_exchange_prefix(symbol: str) -> str:
    """根据股票代码自动添加交易所前缀: 6开头→sh, 其他→sz"""
    if symbol.startswith("6"):
        return f"sh{symbol}"
    return f"sz{symbol}"


class Fetcher:
    """统一的行情数据获取接口"""

    @staticmethod
    def a_stock(symbol: str, start: str = "2020-01-01", end: Optional[str] = None) -> pd.DataFrame:
        """
        获取 A股 日线数据（新浪财经数据源）。

        Args:
            symbol: 股票代码，如 '000001'（平安银行）、'600519'（贵州茅台）
            start: 起始日期 'YYYY-MM-DD'
            end: 截止日期，默认今天

        Returns:
            DataFrame，列包含: date, open, high, low, close, volume
        """
        if end is None:
            end = datetime.today().strftime("%Y-%m-%d")

        import akshare as ak

        full_symbol = _add_exchange_prefix(symbol)

        raw = ak.stock_zh_a_daily(
            symbol=full_symbol,
            start_date=start.replace("-", ""),
            end_date=end.replace("-", ""),
            adjust="qfq",  # 前复权
        )

        df = pd.DataFrame({
            "date": pd.to_datetime(raw["date"]),
            "open": raw["open"].astype(float),
            "high": raw["high"].astype(float),
            "low": raw["low"].astype(float),
            "close": raw["close"].astype(float),
            "volume": raw["volume"].astype(float),
        })
        df.set_index("date", inplace=True)
        df.sort_index(inplace=True)
        return df

    @staticmethod
    def us_stock(symbol: str, start: str = "2020-01-01", end: Optional[str] = None) -> pd.DataFrame:
        """
        获取美股日线数据。

        Args:
            symbol: 股票代码，如 'AAPL'、'MSFT'
            start: 起始日期 'YYYY-MM-DD'
            end: 截止日期，默认今天

        Returns:
            DataFrame，列包含: date, open, high, low, close, volume
        """
        if end is None:
            end = datetime.today().strftime("%Y-%m-%d")

        import yfinance as yf

        ticker = yf.Ticker(symbol)
        raw = ticker.history(start=start, end=end)

        df = pd.DataFrame({
            "date": pd.to_datetime(raw.index),
            "open": raw["Open"].astype(float),
            "high": raw["High"].astype(float),
            "low": raw["Low"].astype(float),
            "close": raw["Close"].astype(float),
            "volume": raw["Volume"].astype(float),
        })
        df.set_index("date", inplace=True)
        df.sort_index(inplace=True)
        return df

    @staticmethod
    def index(symbol: str, start: str = "2020-01-01", end: Optional[str] = None) -> pd.DataFrame:
        """
        获取指数日线数据（沪深300、上证指数等）。

        Args:
            symbol: 指数代码，如 '000300'（沪深300）、'000001'（上证指数）
            start: 起始日期
            end: 截止日期

        Returns:
            DataFrame 标准 OHLCV 格式
        """
        if end is None:
            end = datetime.today().strftime("%Y-%m-%d")

        import akshare as ak

        raw = ak.stock_zh_index_daily(symbol=f"sh{symbol}" if symbol.startswith("000") else f"sz{symbol}")
        raw["date"] = pd.to_datetime(raw["date"])

        mask = (raw["date"] >= start) & (raw["date"] <= end)
        raw = raw[mask]

        df = pd.DataFrame({
            "date": raw["date"],
            "open": raw["open"].astype(float),
            "high": raw["high"].astype(float),
            "low": raw["low"].astype(float),
            "close": raw["close"].astype(float),
            "volume": raw["volume"].astype(float),
        })
        df.set_index("date", inplace=True)
        df.sort_index(inplace=True)
        return df
