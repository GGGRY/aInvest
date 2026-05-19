"""
业绩指标计算
"""

import pandas as pd
import numpy as np

TRADING_DAYS = 252


def annualized_return(equity: pd.Series) -> float:
    """从净值序列计算年化收益率"""
    if len(equity) < 2:
        return 0.0
    years = len(equity) / TRADING_DAYS
    total = equity.iloc[-1] / equity.iloc[0] - 1
    return (1 + total) ** (1 / years) - 1 if years > 0 else 0.0


def annualized_volatility(equity: pd.Series) -> float:
    """从净值序列计算年化波动率"""
    returns = equity.pct_change().dropna()
    return returns.std() * np.sqrt(TRADING_DAYS)


def max_drawdown(equity: pd.Series) -> float:
    """从净值序列计算最大回撤（返回负值）"""
    peak = equity.cummax()
    drawdown = (equity - peak) / peak
    return drawdown.min()


def sharpe_ratio(equity: pd.Series, risk_free: float = 0.03) -> float:
    """从净值序列计算夏普比率"""
    returns = equity.pct_change().dropna()
    excess = returns.mean() * TRADING_DAYS - risk_free
    vol = returns.std() * np.sqrt(TRADING_DAYS)
    return excess / vol if vol > 0 else 0.0


def performance_summary(df: pd.DataFrame, risk_free: float = 0.03) -> dict:
    """
    计算策略绩效指标。

    Args:
        df: 必须包含 'returns'（日收益率）和 'position'（仓位）列
        risk_free: 无风险利率（默认 3%）

    Returns:
        包含所有绩效指标的字典
    """
    strategy_returns = df["returns"] * df["position"].shift(1).fillna(0)
    cumulative = (1 + strategy_returns).cumprod()

    total_return = cumulative.iloc[-1] - 1 if len(cumulative) > 0 else 0

    # 年化收益率（一年按 252 个交易日算）
    years = len(strategy_returns) / 252
    annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

    # 年化波动率
    annual_vol = strategy_returns.std() * np.sqrt(252)

    # 夏普比率
    sharpe = (annual_return - risk_free) / annual_vol if annual_vol > 0 else 0

    # 最大回撤
    peak = cumulative.cummax()
    drawdown = (cumulative - peak) / peak
    max_drawdown = drawdown.min()

    # 胜率
    trades = strategy_returns[strategy_returns != 0]
    win_rate = (trades > 0).mean() if len(trades) > 0 else 0

    # 盈亏比
    avg_win = trades[trades > 0].mean() if len(trades[trades > 0]) > 0 else 0
    avg_loss = abs(trades[trades < 0].mean()) if len(trades[trades < 0]) > 0 else 0
    profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float("inf")

    # 卡尔玛比率（年化收益 / 最大回撤绝对值）
    calmar = annual_return / abs(max_drawdown) if max_drawdown < 0 else 0

    return {
        "累计收益率": round(total_return * 100, 2),
        "年化收益率": round(annual_return * 100, 2),
        "年化波动率": round(annual_vol * 100, 2),
        "夏普比率": round(sharpe, 2),
        "最大回撤": round(max_drawdown * 100, 2),
        "胜率": round(win_rate * 100, 2),
        "盈亏比": round(profit_loss_ratio, 2),
        "卡尔玛比率": round(calmar, 2),
    }
