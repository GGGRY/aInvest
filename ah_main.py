"""
AH溢价轮动策略 — 回测入口

用法:
    python ah_main.py                                      # 默认参数
    python ah_main.py --top 10 --rebalance 20 --start 2022-01-01
    python ah_main.py --top 5 --rebalance 60 --start 2020-01-01
"""

import argparse
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from data.ah_fetcher import build_premium_panel
from strategies.ah_premium import AHPremiumStrategy

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def plot_ah_result(result: dict, title: str = "") -> None:
    """绘制AH策略回测结果"""
    equity = result["equity"]
    benchmark = result["benchmark_equity"]
    holdings_log = result["holdings_log"]

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [3, 2, 1.5]})
    fig.suptitle(title, fontsize=14, fontweight="bold")

    # ---- 第一栏: 净值曲线 + 超额收益 ----
    ax1 = axes[0]
    ax1.plot(equity.index, equity.values, label="策略净值", color="#1f77b4", linewidth=1.2)
    ax1.plot(benchmark.index, benchmark.values, label="等权全AH基准", color="#d62728", alpha=0.6, linewidth=0.8)
    ax1.fill_between(
        equity.index, equity.values, benchmark.values,
        where=equity.values >= benchmark.values,
        color="green", alpha=0.08, label="超额收益区间",
    )
    ax1.set_ylabel("净值")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(True, alpha=0.3)

    # ---- 第二栏: 持仓数量变化 ----
    ax2 = axes[1]
    ax2.bar(
        holdings_log["date"], holdings_log["n_holdings"],
        width=max(1, (equity.index[-1] - equity.index[0]).days / len(holdings_log) * 0.6),
        color="#1f77b4", alpha=0.7,
    )
    ax2.set_ylabel("持仓数量")
    ax2.set_ylim(0, max(holdings_log["n_holdings"].max() + 2, 12))
    ax2.grid(True, alpha=0.3)

    # ---- 第三栏: 回撤 ----
    ax3 = axes[2]
    peak = equity.cummax()
    drawdown = (equity - peak) / peak * 100
    ax3.fill_between(equity.index, 0, drawdown, color="red", alpha=0.3)
    ax3.plot(equity.index, drawdown, color="red", linewidth=0.6)
    ax3.set_ylabel("回撤 (%)")
    ax3.set_xlabel("日期")
    ax3.grid(True, alpha=0.3)
    ax3.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))

    plt.tight_layout()
    plt.show()


def main():
    parser = argparse.ArgumentParser(description="AH溢价轮动策略回测")
    parser.add_argument("--top", type=int, default=10, help="持仓股票数量（默认10）")
    parser.add_argument("--rebalance", type=int, default=20, help="调仓频率/交易日（默认20）")
    parser.add_argument("--start", default="2022-01-01", help="起始日期")
    parser.add_argument("--end", default=None, help="截止日期")
    parser.add_argument("--commission", type=float, default=0.0003, help="佣金费率")
    parser.add_argument("--slippage", type=float, default=0.001, help="滑点费率")
    parser.add_argument("--verbose", action="store_true", default=True, help="打印调仓明细（默认开启）")
    parser.add_argument("--no-verbose", dest="verbose", action="store_false", help="不打印调仓明细")
    args = parser.parse_args()

    # 1. 构建AH溢价面板
    print(f"构建AH溢价面板 (起始: {args.start}) ...")
    panel = build_premium_panel(start=args.start, end=args.end)

    # 2. 运行策略
    strategy = AHPremiumStrategy(
        top_n=args.top,
        rebalance_freq=args.rebalance,
        commission=args.commission,
        slippage=args.slippage,
    )

    print(f"\n运行策略: {strategy.name}")
    result = strategy.run(panel=panel)

    # 3. 打印绩效
    metrics = result["metrics"]
    print(f"\n{'='*55}")
    print(f"  策略: {strategy.name}")
    print(f"  数据: {panel.index.get_level_values('date')[0].date()} ~ {panel.index.get_level_values('date')[-1].date()}")
    print(f"{'='*55}")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    print(f"{'='*55}")

    # 4. 调仓明细
    hl = result["holdings_log"].copy()
    # 构建名称映射
    name_map = {}
    for (dt, code), row in panel.iterrows():
        name_map[code] = row.get("name", "")
    name_map = {k: v for k, v in name_map.items() if v}

    def _format_stocks(codes_str):
        if not codes_str:
            return "—"
        return ", ".join(name_map.get(c, c) for c in codes_str.split(","))

    if "verbose" not in args or args.verbose:
        print(f"\n{'='*80}")
        print(f"  调仓明细 ({len(hl)} 次)")
        print(f"{'='*80}")
        print(f"{'日期':<12} {'持仓数':<6} {'调入':<40} {'调出':<40}")
        print(f"{'-'*12} {'-'*6} {'-'*40} {'-'*40}")
        for _, log in hl.iterrows():
            dt = log["date"].strftime("%Y-%m-%d") if hasattr(log["date"], "strftime") else str(log["date"])[:10]
            print(f"{dt:<12} {log['n_holdings']:<6} {_format_stocks(log['buy']):<40} {_format_stocks(log['sell']):<40}")

    # 5. 可视化
    print("\n生成回测图表...")
    plot_ah_result(
        result,
        title=f"{strategy.name}  (起始: {args.start})",
    )


if __name__ == "__main__":
    main()
