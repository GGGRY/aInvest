"""
AH溢价轮动策略 — 按H/A溢价率排名，持有溢价最高的前N只A股，等权配置，定期调仓。
"""

import pandas as pd
import numpy as np
from typing import Optional
from data.ah_fetcher import build_premium_panel
from backtest.metrics import annualized_return, annualized_volatility, max_drawdown, sharpe_ratio


class AHPremiumStrategy:
    """
    AH溢价轮动策略。

    每个调仓日，计算所有AH配对股在当天的H/A溢价率，按溢价从高到低排序，
    买入前 top_n 只，等权配置。若持仓股票在调仓日排名跌出 top_n 则卖出。

    H/A溢价率 = (H股价格_港币 * 汇率/100) / A股价格_人民币 - 1
    溢价率越高，说明H股相对越贵（或A股相对越便宜），买入相对低估的A股。
    """

    def __init__(
        self,
        top_n: int = 10,
        rebalance_freq: int = 20,
        commission: float = 0.0003,
        slippage: float = 0.001,
    ):
        """
        Args:
            top_n: 持有的股票数量
            rebalance_freq: 调仓频率（交易日）
            commission: 佣金费率
            slippage: 滑点费率
        """
        self.top_n = top_n
        self.rebalance_freq = rebalance_freq
        self.commission = commission
        self.slippage = slippage

    @property
    def name(self) -> str:
        return f"AH溢价轮动(top{self.top_n}, {self.rebalance_freq}日调仓)"

    def run(
        self,
        panel: Optional[pd.DataFrame] = None,
        start: str = "2022-01-01",
        end: Optional[str] = None,
    ) -> dict:
        """
        执行回测。

        Args:
            panel: 预构建的面板数据，若为 None 则自动构建
            start: 起始日期
            end: 截止日期

        Returns:
            dict with keys:
                equity: Series — 组合净值曲线
                benchmark_equity: Series — 等权全AH股基准净值
                holdings_log: DataFrame — 每次调仓的持仓记录
                trades: DataFrame — 所有交易的记录
                metrics: dict — 绩效指标
        """
        if panel is None:
            panel = build_premium_panel(start=start, end=end)

        dates = sorted(panel.index.get_level_values("date").unique())
        stocks = sorted(panel.index.get_level_values("stock").unique())

        # 确定调仓日期
        rebalance_dates = dates[:: self.rebalance_freq]
        if dates[-1] not in rebalance_dates:
            rebalance_dates = list(rebalance_dates) + [dates[-1]]

        # 净值计算用每日矩阵（date × stock）
        daily_returns = self._build_return_matrix(panel, dates, stocks)

        # 持仓权重矩阵（date × stock）
        weight_matrix = pd.DataFrame(0.0, index=dates, columns=stocks)
        holdings_log_records = []

        current_holdings = set()
        current_weights = {}

        for i, rday in enumerate(rebalance_dates):
            # 获取当天的溢价率排名
            day_data = panel.loc[rday] if rday in panel.index.get_level_values("date") else None
            if day_data is None or day_data.empty:
                continue

            premiums = day_data["premium"].dropna().sort_values(ascending=False)
            top_stocks = set(premiums.head(self.top_n).index)

            # 卖出不在 top_n 的持仓
            to_sell = current_holdings - top_stocks

            # 买入新进入 top_n 的股票
            to_buy = top_stocks - current_holdings

            # 更新持仓
            current_holdings = top_stocks
            if len(current_holdings) > 0:
                weight = 1.0 / len(current_holdings)
                current_weights = {s: weight for s in current_holdings}
            else:
                current_weights = {}

            holdings_log_records.append({
                "date": rday,
                "holdings": ",".join(sorted(current_holdings)),
                "n_holdings": len(current_holdings),
                "buy": ",".join(sorted(to_buy)),
                "sell": ",".join(sorted(to_sell)),
            })

            # 填充权重：从当前调仓日到下一个调仓日
            if i + 1 < len(rebalance_dates):
                next_day_idx = dates.index(rebalance_dates[i + 1])
            else:
                next_day_idx = len(dates)
            cur_day_idx = dates.index(rday)
            for s, w in current_weights.items():
                if s in weight_matrix.columns:
                    weight_matrix.iloc[cur_day_idx:next_day_idx, weight_matrix.columns.get_loc(s)] = w

        # 计算组合每日收益
        portfolio_daily_return = (daily_returns * weight_matrix).sum(axis=1)

        # 扣除交易成本
        turnover = weight_matrix.diff().abs().sum(axis=1)
        cost_daily = turnover * (self.commission + self.slippage)
        # 只在调仓日扣成本
        cost_daily.loc[~cost_daily.index.isin(rebalance_dates)] = 0.0
        portfolio_daily_return = portfolio_daily_return - cost_daily

        # 基准: 等权持有所有AH股
        benchmark_weight = pd.DataFrame(1.0 / len(stocks), index=dates, columns=stocks)
        benchmark_daily = (daily_returns * benchmark_weight).sum(axis=1)

        # 净值
        equity = (1 + portfolio_daily_return).cumprod()
        benchmark_equity = (1 + benchmark_daily).cumprod()

        # 交易记录
        trades = self._build_trade_log(holdings_log_records, weight_matrix, panel, rebalance_dates)

        # 绩效
        metrics = self._calc_metrics(equity, benchmark_equity, portfolio_daily_return)

        return {
            "equity": equity,
            "benchmark_equity": benchmark_equity,
            "weight_matrix": weight_matrix,
            "holdings_log": pd.DataFrame(holdings_log_records),
            "trades": trades,
            "metrics": metrics,
        }

    # -------------------------------------------------------------------
    # 内部方法
    # -------------------------------------------------------------------

    def _build_return_matrix(self, panel, dates, stocks) -> pd.DataFrame:
        """从面板构建日收益矩阵"""
        close_matrix = pd.DataFrame(np.nan, index=dates, columns=stocks)
        for (dt, code), row in panel.iterrows():
            if dt in close_matrix.index and code in close_matrix.columns:
                close_matrix.loc[dt, code] = row["a_close"]
        close_matrix = close_matrix.ffill()
        return close_matrix.pct_change().fillna(0.0)

    def _build_trade_log(self, holdings_log, weight_matrix, panel, rebalance_dates):
        """从持仓日志和权重矩阵重建每笔交易的记录"""
        records = []
        for _, log in pd.DataFrame(holdings_log).iterrows():
            dt = log["date"]
            buy_list = log["buy"].split(",") if log["buy"] else []
            sell_list = log["sell"].split(",") if log["sell"] else []

            for code in buy_list:
                price = self._get_price(panel, dt, code)
                if price is None:
                    continue
                records.append({"date": dt, "stock": code, "action": "buy", "price": price})

            for code in sell_list:
                price = self._get_price(panel, dt, code)
                if price is None:
                    continue
                records.append({"date": dt, "stock": code, "action": "sell", "price": price})

        return pd.DataFrame(records)

    def _get_price(self, panel, date, stock):
        try:
            return panel.loc[(date, stock), "a_close"]
        except (KeyError, TypeError):
            return None

    def _calc_metrics(self, equity, benchmark_equity, daily_returns) -> dict:
        ann_ret = annualized_return(equity)
        ann_vol = annualized_volatility(equity)
        mdd = max_drawdown(equity)
        sr = sharpe_ratio(equity)
        bench_ret = annualized_return(benchmark_equity)

        # 超额收益
        excess = ann_ret - bench_ret

        # 胜率 (日)
        win_rate = (daily_returns > 0).sum() / max(len(daily_returns), 1)

        return {
            "累计收益率": f"{equity.iloc[-1] - 1:.2%}",
            "年化收益率": f"{ann_ret:.2%}",
            "年化波动率": f"{ann_vol:.2%}",
            "夏普比率": f"{sr:.2f}",
            "最大回撤": f"{mdd:.2%}",
            "基准年化收益": f"{bench_ret:.2%}",
            "超额收益": f"{excess:.2%}",
            "日胜率": f"{win_rate:.2%}",
        }
