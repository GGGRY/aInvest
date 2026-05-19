"""
可视化模块 — 绘制回测结果
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# 设置中文字体
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def plot_result(df: pd.DataFrame, title: str = "回测结果") -> None:
    """
    绘制回测结果全景图：净值曲线 + 买卖信号 + 回撤曲线。

    Args:
        df: 回测完成后的 DataFrame，必须包含 equity, benchmark_equity, close, signal
        title: 图表标题
    """
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [3, 2, 1.5]})
    fig.suptitle(title, fontsize=14, fontweight="bold")

    # ---- 第一栏: 净值曲线 + 买卖点 ----
    ax1 = axes[0]
    ax1.plot(df.index, df["equity"], label="策略净值", color="#1f77b4", linewidth=1.2)
    ax1.plot(df.index, df["benchmark_equity"], label="买入持有基准", color="#d62728", alpha=0.6, linewidth=0.8)

    # 标注买入/卖出信号点
    buy_signals = df[df["signal"] > df["signal"].shift(1).fillna(0)]
    sell_signals = df[df["signal"] < df["signal"].shift(1).fillna(0)]

    buy_price = df.loc[buy_signals.index, "close"]
    sell_price = df.loc[sell_signals.index, "close"]

    ax1.scatter(buy_signals.index, buy_price, marker="^", color="green", s=40, alpha=0.8, label="买入信号")
    ax1.scatter(sell_signals.index, sell_price, marker="v", color="red", s=40, alpha=0.8, label="卖出信号")

    ax1.set_ylabel("净值")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(True, alpha=0.3)

    # ---- 第二栏: 收盘价 + 均线 + 成交量 ----
    ax2 = axes[1]
    ax2.plot(df.index, df["close"], label="收盘价", color="#333", linewidth=0.8)
    if "ma5" in df.columns:
        ax2.plot(df.index, df["ma5"], label="MA5", alpha=0.6, linewidth=0.6)
    if "ma20" in df.columns:
        ax2.plot(df.index, df["ma20"], label="MA20", alpha=0.6, linewidth=0.6)

    # 持仓区间着色（基于价格轴范围）
    price_max = df[["close"] + [c for c in ["ma5", "ma10", "ma20", "ma60"] if c in df.columns]].max().max()
    price_min = df[["close"] + [c for c in ["ma5", "ma10", "ma20", "ma60"] if c in df.columns]].min().min()
    ax2.fill_between(
        df.index, price_min, price_max,
        where=df["signal"] == 1, color="green", alpha=0.08, label="持仓区间",
    )

    # 成交量柱状图（右轴）
    ax2_vol = ax2.twinx()
    ax2_vol.bar(df.index, df["volume"], width=1, color="gray", alpha=0.15)
    ax2_vol.set_ylabel("成交量", fontsize=8, color="gray")
    ax2_vol.tick_params(axis="y", labelsize=7, colors="gray")
    ax2_vol.set_ylim(0, df["volume"].max() * 3)

    ax2.set_ylabel("价格")
    ax2.legend(loc="upper left", fontsize=8)
    ax2.grid(True, alpha=0.3)

    # ---- 第三栏: 回撤曲线 ----
    ax3 = axes[2]
    equity_curve = df["equity"]
    peak = equity_curve.cummax()
    drawdown = (equity_curve - peak) / peak * 100
    ax3.fill_between(df.index, 0, drawdown, color="red", alpha=0.3)
    ax3.plot(df.index, drawdown, color="red", linewidth=0.6)
    ax3.set_ylabel("回撤 (%)")
    ax3.set_xlabel("日期")
    ax3.grid(True, alpha=0.3)
    ax3.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))

    plt.tight_layout()
    plt.show()
