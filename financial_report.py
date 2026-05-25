"""
财务报告导出工具 — 将利润表/资产负债表/现金流量表导出为 HTML 文件。
数据源: akshare stock_financial_report_sina (新浪财经)

用法:
    python financial_report.py --symbol 000001
    python financial_report.py --symbol 600519
"""

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from data.financial_fetcher import (
    fetch_balance_sheet,
    fetch_income_statement,
    fetch_cash_flow,
    fetch_financial_abstract,
)

REPORT_TYPES = ["利润表", "资产负债表", "现金流量表"]

_INCOME_HIGHLIGHT = {
    "营业总收入",
    "营业总成本",
    "营业利润", "利润总额", "净利润",
    "归属于母公司所有者的净利润", "归属于母公司的净利润",
}

_CASHFLOW_HIGHLIGHT = {
    "经营活动产生的现金流量",
    "经营活动现金流入小计",
    "经营活动现金流出小计",
    "经营活动产生的现金流量净额",
    "投资活动产生的现金流量",
    "投资活动现金流入小计",
    "投资活动现金流出小计",
    "投资活动产生的现金流量净额",
    "筹资活动产生的现金流量",
    "筹资活动现金流入小计",
    "筹资活动现金流出小计",
    "筹资活动产生的现金流量净额",
}

_BALANCE_HIGHLIGHT = {
    "流动资产",
    "流动资产合计",
    "非流动资产",
    "非流动资产合计",
    "资产总计",
    "流动负债",
    "流动负债合计",
    "非流动负债",
    "非流动负债合计",
    "负债合计",
    "所有者权益(或股东权益)合计",
    "负债和所有者权益(或股东权益)总计",
    "所有者权益（或股东权益）合计",
    "负债和所有者权益（或股东权益）总计",
}

_ABSTRACT_HIGHLIGHT = {
    "营业总收入", "净利润","归母净利润",
    "扣非净利润", "经营现金流量净额",
    "基本每股收益", "稀释每股收益",
    "净资产收益率(ROE)", "总资产收益率",
    "毛利率", "销售净利率", "期间费用率",
    "资产负债率",
    "营业总收入增长率", "归属母公司净利润增长率",
}

# ── stock name lookup ──────────────────────────────────────────────

_NAME_CACHE = Path(__file__).parent / ".cache" / "stock_names.pkl"


def _get_stock_name_map() -> dict:
    """全量A股代码→名称映射（本地缓存，避免重复网络请求）。"""
    if _NAME_CACHE.exists():
        try:
            return pd.read_pickle(_NAME_CACHE)
        except Exception:
            pass

    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        mapping = dict(zip(df["code"].astype(str), df["name"]))
    except Exception:
        return {}

    if mapping:
        _NAME_CACHE.parent.mkdir(parents=True, exist_ok=True)
        pd.to_pickle(mapping, _NAME_CACHE)
    return mapping


def _lookup_stock_name(symbol: str) -> str:
    symbol = str(symbol).strip().zfill(6)
    return _get_stock_name_map().get(symbol, "")


# ── helpers ────────────────────────────────────────────────────────

def _fmt_value(val) -> str:
    if pd.isna(val):
        return "—"
    try:
        num = float(val)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return str(val)
    yi = num / 1e8
    if abs(yi) >= 0.01:
        return f"{yi:,.2f}亿"
    return f"{num:,.0f}"


def _format_period(dt: pd.Timestamp) -> str:
    """将日期转为中文报告期名称，如 2024年报、2024一季报。"""
    y = dt.year
    m = dt.month
    if m == 12:
        return f"{y}年报"
    elif m == 3:
        return f"{y}一季报"
    elif m == 6:
        return f"{y}中报"
    elif m == 9:
        return f"{y}三季报"
    return dt.strftime("%Y-%m-%d")


def _build_json(raw: pd.DataFrame, report_type: str) -> str:
    """Build compact JSON for a financial table: {d, m, h, v}.

    v[metric_idx][date_idx] yields the pre-formatted display string.
    """
    if raw.empty:
        return '{"d":[],"m":[],"h":[],"v":[]}'

    df = raw.copy()
    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.sort_values(date_col, ascending=False)

    dates = [_format_period(d) for d in df[date_col]]
    metric_cols = [c for c in df.columns if c != date_col]

    highlight_map = {
        "利润表": _INCOME_HIGHLIGHT,
        "现金流量表": _CASHFLOW_HIGHLIGHT,
        "资产负债表": _BALANCE_HIGHLIGHT,
    }
    highlight_set = highlight_map.get(report_type, set())
    highlights = [m for m in metric_cols if m in highlight_set]

    n_dates = len(df)
    values = []
    for mi in range(len(metric_cols)):
        row_vals = []
        for di in range(n_dates):
            row_vals.append(_fmt_value(df.iloc[di][metric_cols[mi]]))
        values.append(row_vals)

    data = {"d": dates, "m": list(metric_cols), "h": highlights, "v": values}
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _fmt_abstract_value(val, metric_name: str) -> str:
    """Format financial abstract value based on metric type (amount / percentage / per-share)."""
    if pd.isna(val):
        return "—"
    try:
        num = float(val)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return str(val)

    if any(kw in metric_name for kw in ("率", "收益率", "利润率", "占比", "比例")):
        return f"{num:.2f}%"

    if "每股" in metric_name:
        return f"{num:.4f}"

    yi = num / 1e8
    if abs(yi) >= 0.01:
        return f"{yi:,.2f}亿"
    wan = num / 1e4
    if abs(wan) >= 0.01:
        return f"{wan:,.2f}万"
    return f"{num:,.0f}"


def _build_abstract_json(raw: pd.DataFrame) -> str:
    """Build JSON for financial abstract data from stock_financial_abstract.

    The raw DataFrame has columns ['选项', '指标', '20260331', '20251231', ...].
    """
    if raw is None or raw.empty:
        return '{"d":[],"m":[],"h":[],"v":[]}'

    df = raw.copy()
    date_cols = [c for c in df.columns if c not in ("选项", "指标")]
    parsed_dates = pd.to_datetime(date_cols, format="%Y%m%d", errors="coerce")
    sorted_pairs = sorted(zip(date_cols, parsed_dates), key=lambda x: x[1], reverse=True)
    sorted_cols = [p[0] for p in sorted_pairs]
    dates = [_format_period(d) for _, d in sorted(zip(date_cols, parsed_dates), key=lambda x: x[1], reverse=True)]

    metrics = df["指标"].tolist()
    categories = df["选项"].tolist() if "选项" in df.columns else [""] * len(metrics)

    unique_categories = set(c for c in categories if c)
    if len(unique_categories) > 1:
        display_names = [f"{c}→{m}" if c else m for c, m in zip(categories, metrics)]
    else:
        display_names = list(metrics)

    highlights = [dn for dn, m in zip(display_names, metrics) if m in _ABSTRACT_HIGHLIGHT]

    n_dates = len(sorted_cols)
    values = []
    for mi in range(len(metrics)):
        row_vals = []
        for di in range(n_dates):
            row_vals.append(_fmt_abstract_value(df.iloc[mi][sorted_cols[di]], metrics[mi]))
        values.append(row_vals)

    data = {"d": dates, "m": display_names, "h": highlights, "v": values}
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _to_single_quarter(df: pd.DataFrame) -> pd.DataFrame:
    """将累计报表数据转换为单季度数据（同一年内后一季度减前一季度）。"""
    if df.empty:
        return df
    date_col = df.columns[0]
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], format="%Y%m%d", errors="coerce")
    df = df.sort_values(date_col, ascending=True)  # 最早的在前
    df["_year"] = df[date_col].dt.year
    metric_cols = [c for c in df.columns if c not in (date_col, "_year")]
    for col in metric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    result_rows = []
    for _year, group in df.groupby("_year", sort=True):
        group = group.sort_values(date_col, ascending=True)
        prev_row = None
        for _idx, row in group.iterrows():
            if prev_row is None:
                result_rows.append(row)
            else:
                new_row = row.copy()
                for col in metric_cols:
                    if pd.notna(row[col]) and pd.notna(prev_row[col]):
                        new_row[col] = row[col] - prev_row[col]
                    else:
                        new_row[col] = float("nan")
                result_rows.append(new_row)
            prev_row = row

    result = pd.DataFrame(result_rows)
    result = result.drop(columns=["_year"])
    result = result.sort_values(date_col, ascending=False)  # 最新的在前
    return result


# ── HTML template ──────────────────────────────────────────────────

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _load_template(name: str) -> str:
    return (_TEMPLATE_DIR / name).read_text(encoding="utf-8")


def _count_metrics(df: pd.DataFrame) -> tuple:
    """返回 (指标数, 报告期数)。"""
    if df.empty:
        return 0, 0
    date_col = df.columns[0]
    metric_count = len(df.columns) - 1
    period_count = len(df)
    return metric_count, period_count


def generate_html(symbol: str, stock_name: str) -> tuple[str, str]:
    name = stock_name or symbol

    df_abstract = fetch_financial_abstract(symbol)
    df_income = fetch_income_statement(symbol)
    df_balance = fetch_balance_sheet(symbol)
    df_cashflow = fetch_cash_flow(symbol)

    if df_abstract is not None and not df_abstract.empty:
        ca = len(df_abstract)  # 指标数（行数）
        pa = len([c for c in df_abstract.columns if c not in ("选项", "指标")])  # 报告期数
    else:
        ca, pa = 0, 0
    ci, pi = _count_metrics(df_income)
    cb, pb = _count_metrics(df_balance)
    cc, pc = _count_metrics(df_cashflow)

    # 最近报告期（取利润表最新日期）
    date_col = df_income.columns[0]
    latest_date = pd.to_datetime(df_income[date_col], format="%Y%m%d", errors="coerce").max()
    latest_period = _format_period(latest_date)

    template = _load_template("financial_report.html")
    html = template.format(
        stock_name=name,
        symbol=symbol,
        count_abstract=ca, count_abstract_periods=pa,
        count_income=ci, count_income_periods=pi,
        count_balance=cb, count_balance_periods=pb,
        count_cashflow=cc, count_cashflow_periods=pc,
        data_abstract=_build_abstract_json(df_abstract),
        data_income=_build_json(df_income, "利润表"),
        data_income_sq=_build_json(_to_single_quarter(df_income), "利润表"),
        data_balance=_build_json(df_balance, "资产负债表"),
        data_cashflow=_build_json(df_cashflow, "现金流量表"),
        data_cashflow_sq=_build_json(_to_single_quarter(df_cashflow), "现金流量表"),
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
    )
    return html, latest_period


def main():
    parser = argparse.ArgumentParser(
        description="导出股票财务三张表为 HTML 文件"
    )
    parser.add_argument("--symbol", required=True, help="股票代码，如 000001、600519")
    args = parser.parse_args()

    print(f"正在查找 {args.symbol} 股票名称 ...")
    stock_name = _lookup_stock_name(args.symbol)
    if stock_name:
        print(f"  名称: {stock_name}")
    else:
        print(f"  未查到名称，将用代码代替")

    print("正在获取财务数据 ...")
    print("  [1/4] 关键指标 ...")
    print("  [2/4] 利润表 ...")
    print("  [3/4] 资产负债表 ...")
    print("  [4/4] 现金流量表 ...")

    html, latest_period = generate_html(args.symbol, stock_name)

    out_dir = Path.cwd() / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{args.symbol}_{stock_name or args.symbol}_{latest_period}.html"
    out_path = out_dir / filename
    out_path.write_text(html, encoding="utf-8")

    print(f"\n已保存 → {out_path}")
    print("用浏览器打开该文件即可切换查看三张报表。")


if __name__ == "__main__":
    main()
