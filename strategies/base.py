"""
策略基类 — 所有策略都继承此基类并实现 generate_signals 方法。
"""

import pandas as pd
from abc import ABC, abstractmethod


class Strategy(ABC):
    """
    策略基类。

    子类需要实现:
        generate_signals(df) → pd.Series
            返回值为: 1 (买入/持有), 0 (空仓), -1 (卖出/做空)
    """

    def __init__(self, name: str = "BaseStrategy"):
        self.name = name

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        根据输入数据生成交易信号。

        Args:
            df: 包含 OHLCV 和各项技术指标的 DataFrame

        Returns:
            signal: pd.Series, 值域为 {1, 0, -1}
        """
        ...

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        执行策略，将信号附加到 DataFrame 上。

        Returns:
            包含 'signal' 和 'position' 列的 DataFrame
        """
        result = df.copy()
        result["signal"] = self.generate_signals(result)
        position = result["signal"].where(result["signal"] != 0).ffill().fillna(0).astype(int)
        result["position"] = position
        return result
