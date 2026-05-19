# aInvest

量化策略回测框架，支持 A 股和美股的双均线策略与 AH 溢价轮动策略。

## 安装

```bash
pip install -r requirements.txt
```

## 快速开始

**双均线策略（A 股）**

```bash
python ma_cross_main.py --symbol 000001 --short 5 --long 20
```

**双均线策略（美股）**

```bash
python ma_cross_main.py --market us --symbol AAPL --short 5 --long 20
```

**AH 溢价轮动策略**

```bash
python ah_main.py --top 10 --rebalance 20 --start 2022-01-01
```

## 项目结构

| 目录 | 说明 |
|------|------|
| `strategies/` | 策略实现（双均线、AH溢价轮动） |
| `backtest/` | 回测引擎与绩效指标 |
| `indicators/` | 技术指标计算 |
| `data/` | 数据获取 |
| `visualization/` | 可视化绘图 |
| `notebooks/` | Jupyter notebook 示例 |
