"""
回测引擎 — 模拟交易并计算绩效
"""

import pandas as pd
import numpy as np

from strategies import Strategy


class BacktestEngine:
    """
    回测引擎。将策略产生的信号模拟为实际持仓，并计算收益曲线。

    Parameters:
        initial_capital: 初始资金 (默认 100000)
        commission: 手续费率 (默认 0.0003，即万三)
        slippage: 滑点 (默认 0.001，即 0.1%)
    """

    def __init__(
        self,
        initial_capital: float = 100_000,
        commission: float = 0.0003,
        slippage: float = 0.001,
    ):
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage

    def run(self, df: pd.DataFrame, strategy: Strategy) -> pd.DataFrame:
        """
        执行回测。

        Args:
            df: 包含 OHLCV 和指标列的 DataFrame
            strategy: 策略实例

        Returns:
            包含信号、仓位、收益、净值等列的完整回测结果 DataFrame
        """
        result = strategy.run(df)

        position = result["position"]

        # 计算扣除滑点后的日收益
        daily_return = result["returns"] - self.slippage * position.diff().abs()

        # 扣除手续费（只在调仓日收取）
        turnover = position.diff().abs()
        daily_return -= turnover * self.commission

        # 策略收益 = 持仓 * 日收益
        result["strategy_returns"] = daily_return * position.shift(1).fillna(0)
        result["equity"] = (1 + result["strategy_returns"]).cumprod() * self.initial_capital

        # 基准收益（买入持有）
        result["benchmark_returns"] = result["returns"].fillna(0)
        result["benchmark_equity"] = (1 + result["benchmark_returns"]).cumprod() * self.initial_capital

        return result
