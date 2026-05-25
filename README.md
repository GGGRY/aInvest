# aInvest

量化策略回测框架，支持 A 股和美股的双均线策略、AH 溢价轮动策略，以及财务报表导出。

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

可通过 `--start` 和 `--end` 指定回测区间（默认起始 2020-01-01）。

**AH 溢价轮动策略**

```bash
# 完整回测
python ah_main.py --top 10 --rebalance 20 --start 2022-01-01

# 仅查看最新 AH 溢价排名
python ah_main.py --rank --top 20
```

可通过 `--end` 指定截止日期，`--commission` 和 `--slippage` 调整交易成本。

**财务报表导出**

```bash
python financial_report.py --symbol 000001
```

将关键指标、利润表、资产负债表、现金流量表导出为 HTML 文件，输出到 `output/` 目录。支持按报告期筛选和分页浏览。

## 项目结构

| 目录 | 说明 |
|------|------|
| `strategies/` | 策略实现（双均线、AH溢价轮动） |
| `backtest/` | 回测引擎与绩效指标 |
| `indicators/` | 技术指标计算（MA、MACD、RSI、布林带等） |
| `data/` | 数据获取（A股/美股行情、AH配对、汇率、财务报表） |
| `visualization/` | 回测可视化（净值曲线、信号标注、回撤） |
| `templates/` | HTML 模板（财务报表） |

入口文件 `ma_cross_main.py`、`ah_main.py`、`financial_report.py` 位于项目根目录，数据缓存存储在 `.cache/` 目录下。
