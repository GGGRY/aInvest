"""
财务数据获取模块 — 基于 akshare 新浪财经数据源，获取利润表/资产负债表等核心指标。

数据源: ak.stock_financial_abstract() → 新浪财经
缓存策略: .cache/fa_{symbol}.pkl, 一次性缓存全部历史数据
"""

import pandas as pd
from pathlib import Path
from typing import Optional

CACHE_DIR = Path(__file__).parent.parent / ".cache"

# akshare stock_financial_report_sina 的 stock 参数格式为 "sh600519" / "sz000001"
_SZ_PREFIXES = ("000", "001", "002", "003", "004", "300", "301", "302")


def _to_sina_code(symbol: str) -> str:
    """将纯数字代码转换为新浪格式（sz000001 / sh600519）。"""
    symbol = str(symbol).strip()
    if symbol.startswith(("sh", "sz", "SH", "SZ")):
        return symbol.lower()
    if symbol.startswith(_SZ_PREFIXES):
        return f"sz{symbol}"
    return f"sh{symbol}"


def _fetch_sina_report(symbol: str, report_type: str) -> pd.DataFrame:
    """
    调用 akshare 新浪接口获取指定报表，带本地缓存。

    Args:
        symbol: 纯数字股票代码（如 000001）
        report_type: "资产负债表" / "利润表" / "现金流量表"

    Returns:
        DataFrame，列为 ['报告日', '科目1', '科目2', ...]
    """
    code = _to_sina_code(symbol)
    cache_path = CACHE_DIR / f"sina_{code}_{report_type}.pkl"

    if cache_path.exists():
        return pd.read_pickle(cache_path)

    try:
        import akshare as ak
        df = ak.stock_financial_report_sina(stock=code, symbol=report_type)
    except Exception:
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_pickle(cache_path)
    return df


def fetch_balance_sheet(symbol: str) -> pd.DataFrame:
    """获取资产负债表。返回 DataFrame，列为 ['报告日', '货币资金', '资产总计', ...]"""
    return _fetch_sina_report(symbol, "资产负债表")


def fetch_income_statement(symbol: str) -> pd.DataFrame:
    """获取利润表。返回 DataFrame，列为 ['报告日', '营业总收入', '净利润', ...]"""
    return _fetch_sina_report(symbol, "利润表")


def fetch_cash_flow(symbol: str) -> pd.DataFrame:
    """获取现金流量表。返回 DataFrame，列为 ['报告日', '经营活动现金流量净额', ...]"""
    return _fetch_sina_report(symbol, "现金流量表")

# 利润表科目在中国财报中为累计值（YTD），需按年度做差得到单季度值
CUMULATIVE_METRICS = {
    "营业总收入", "营业成本", "净利润", "归母净利润",
    "扣非净利润", "营业利润", "利润总额", "营业支出",
}


def fetch_financial_abstract(symbol: str) -> Optional[pd.DataFrame]:
    """
    获取单只股票的财务摘要数据（全部历史期间）。

    Returns:
        DataFrame, 列为 ['选项', '指标', '20260331', '20251231', ...]
        日期列为 float64，值为原始金额（元）或百分比。
        返回 None 表示获取失败。
    """
    cache_path = CACHE_DIR / f"fa_{symbol}.pkl"

    if cache_path.exists():
        return pd.read_pickle(cache_path)

    try:
        import akshare as ak
        df = ak.stock_financial_abstract(symbol=symbol)
    except Exception:
        return None

    if df is None or df.empty:
        return None

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_pickle(cache_path)
    return df


def _extract_metric_series(raw: pd.DataFrame, metric: str) -> pd.Series:
    """从宽表中提取指定指标的时序数据，返回 DatetimeIndex Series。"""
    mask = raw["指标"] == metric
    if not mask.any():
        available = raw["指标"].unique().tolist()
        raise ValueError(f"指标 '{metric}' 不存在。可用指标: {available[:20]}...")

    row = raw[mask].iloc[0]
    date_cols = [c for c in raw.columns if c not in ("选项", "指标")]
    s = row[date_cols]
    s.index = pd.to_datetime(s.index, format="%Y%m%d")
    s = s.sort_index()
    s = pd.to_numeric(s, errors="coerce")
    return s


def get_single_quarter(raw: pd.DataFrame, metric: str) -> pd.Series:
    """
    将累计值（YTD）转换为单季度值。

    对于利润表科目（累计制），Q1=Q1_YTD, Q2=Q2_YTD-Q1_YTD, ...
    对于比率类指标（ROE、毛利率等），直接使用原始值。
    """
    s = _extract_metric_series(raw, metric)

    if metric not in CUMULATIVE_METRICS:
        return s

    result = []
    for year, group in s.groupby(s.index.year):
        group = group.sort_index()
        sq = group.diff().fillna(group)  # Q1 = Q1_YTD, Q2 = Q2-Q1, ...
        result.append(sq)

    out = pd.concat(result).sort_index()
    out.name = metric
    return out


def get_ttm(single_quarter: pd.Series) -> pd.Series:
    """Trailing Twelve Months: 最近4个季度求和。"""
    ttm = single_quarter.rolling(window=4, min_periods=4).sum()
    ttm.name = f"{single_quarter.name}_TTM"
    return ttm


def get_financial_metric(symbol: str, metric: str) -> Optional[dict]:
    """
    一站式获取单只股票的财务指标。

    Returns:
        dict: {symbol, metric, single_quarter, ttm, raw} 或 None（获取失败时）
    """
    raw = fetch_financial_abstract(symbol)
    if raw is None:
        return None

    try:
        sq = get_single_quarter(raw, metric)
    except ValueError as e:
        print(f"错误: {e}")
        return None

    return {
        "symbol": symbol,
        "metric": metric,
        "single_quarter": sq,
        "ttm": get_ttm(sq),
        "raw": raw,
    }


def list_available_metrics(symbol: str) -> Optional[list]:
    """列出某股票所有可用的财务指标名称。"""
    raw = fetch_financial_abstract(symbol)
    if raw is None:
        return None
    return raw["指标"].unique().tolist()
