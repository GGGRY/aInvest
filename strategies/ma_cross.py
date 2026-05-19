"""
双均线交叉策略 — 最简单的趋势跟踪策略。

规则:
  - 短期均线上穿长期均线 → 买入信号 (1)
  - 短期均线下穿长期均线 → 卖出信号 (0)
"""

import pandas as pd
from .base import Strategy


class MACrossStrategy(Strategy):
    """
    双均线交叉策略。

    参数:
        short: 短期均线周期 (默认 5)
        long: 长期均线周期 (默认 20)
    """

    def __init__(self, short: int = 5, long: int = 20):
        super().__init__(name=f"MA_Cross_{short}_{long}")
        self.short = short
        self.long = long

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        ma_short = df["close"].rolling(window=self.short).mean()
        ma_long = df["close"].rolling(window=self.long).mean()

        # 短线上穿长线 → 买入
        signal = pd.Series(0, index=df.index, dtype=int)
        signal[ma_short > ma_long] = 1
        return signal
