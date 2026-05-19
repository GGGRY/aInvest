"""
aInvest — 量化策略回测框架入口

用法:
    python main.py                          # 默认：A股 000001 双均线策略
    python main.py --symbol 600519 --short 5 --long 20
    python main.py --market us --symbol AAPL
"""

import argparse
from data import Fetcher
from indicators import compute_all
from strategies import MACrossStrategy
from backtest import BacktestEngine, performance_summary
from visualization import plot_result


def main():
    parser = argparse.ArgumentParser(description="量化策略回测")
    parser.add_argument("--market", default="a", choices=["a", "us"], help="市场：a (A股) 或 us (美股)")
    parser.add_argument("--symbol", default="000001", help="股票代码")
    parser.add_argument("--start", default="2020-01-01", help="起始日期")
    parser.add_argument("--end", default=None, help="截止日期")
    parser.add_argument("--short", type=int, default=5, help="短期均线周期")
    parser.add_argument("--long", type=int, default=20, help="长期均线周期")
    args = parser.parse_args()

    # 1. 获取数据
    print(f"📡 获取行情数据: {args.market.upper()} {args.symbol} ...")
    if args.market == "a":
        df = Fetcher.a_stock(args.symbol, start=args.start, end=args.end)
    else:
        df = Fetcher.us_stock(args.symbol, start=args.start, end=args.end)

    if df.empty:
        print("❌ 未获取到数据，请检查股票代码和日期范围")
        return

    print(f"   数据条数: {len(df)}")

    # 2. 计算指标
    print("📊 计算技术指标 ...")
    df = compute_all(df)

    # 3. 创建策略 & 回测
    strategy = MACrossStrategy(short=args.short, long=args.long)
    engine = BacktestEngine()
    result = engine.run(df, strategy)

    # 4. 绩效评估
    metrics = performance_summary(result)

    print(f"\n{'='*50}")
    print(f"  策略: {strategy.name}")
    print(f"  股票: {args.market.upper()} {args.symbol}")
    print(f"{'='*50}")
    for k, v in metrics.items():
        unit = "%" if any(w in k for w in ["收益率", "波动率", "回撤", "胜率"]) else ""
        print(f"  {k}: {v}{unit}")
    print(f"{'='*50}")

    # 5. 可视化
    print("\n📈 生成回测图表 ...")
    plot_result(result, title=f"{strategy.name} — {args.symbol}")


if __name__ == "__main__":
    main()
