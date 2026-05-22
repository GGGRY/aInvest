"""
AH股数据获取模块 — 获取AH配对股票的A股和H股历史行情，计算H/A溢价率
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional
import akshare as ak

from .fetcher import Fetcher

CACHE_DIR = Path(__file__).parent.parent / ".cache"


def _cached(code: str, market: str, func, **kwargs) -> pd.DataFrame:
    """带文件缓存的通用数据获取"""
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / f"{market}_{code}.pkl"
    if path.exists():
        return pd.read_pickle(path)
    df = func(**kwargs)
    df.to_pickle(path)
    return df


def _is_stale(df: pd.DataFrame) -> bool:
    """缓存数据是否需要更新（非 DatetimeIndex 或最后日期早于昨天）。"""
    if not isinstance(df.index, pd.DatetimeIndex):
        return True
    today = pd.Timestamp.today().normalize()
    return df.index.max().normalize() < today - pd.Timedelta(days=1)


def _fetch_h_stock(h_code: str) -> pd.DataFrame:
    """获取并处理H股历史数据。"""
    raw = ak.stock_hk_daily(symbol=h_code, adjust="qfq")
    raw = raw.copy()
    raw["date"] = pd.to_datetime(raw["date"])
    raw = raw.set_index("date").sort_index()
    return raw[["close"]].rename(columns={"close": "h_close"})


def _clean_name(name: str) -> str:
    """清洗股票名称，去除空格和全角/半角差异，便于匹配"""
    return name.replace(" ", "").replace("　", "").replace("Ａ", "A").replace("Ｂ", "B").replace("*", "")


def _strip_suffix(s: str) -> str:
    """去除常见公司后缀"""
    for sfx in ["股份", "有限", "集团", "企业", "控股", "科技", "实业", "工业", "国际"]:
        if s.endswith(sfx) and len(s) > len(sfx) + 1:
            s = s[: -len(sfx)]
    return s


# H股名称 → A股代码的手动映射（名称差异太大无法自动匹配的）
_MANUAL_MAP: dict[str, str] = {
    "第一拖拉机股份": "601038",
    "四川成渝高速公路": "601107",
    "江苏宁沪高速公路": "600377",
    "深圳高速公路股份": "600548",
    "安徽皖通高速公路": "600012",
    "马鞍山钢铁股份": "600808",
    "上海石油化工股份": "600688",
    "中国石油化工股份": "600028",
    "中国石油股份": "601857",
    "中国海洋石油": "600938",
    "华能国际电力股份": "600011",
    "华电国际电力股份": "600027",
    "中国南方航空股份": "600029",
    "中国东方航空股份": "600115",
    "北京北辰实业股份": "601588",
    "南京熊猫电子股份": "600775",
    "山东新华制药股份": "000756",
    "天津创业环保股份": "600874",
    "中国人民保险集团": "601319",
    "万科企业": "000002",
    "中广核电力": "003816",
    "华虹半导体": "688347",
    "上海复旦": "688385",
    "丽珠医药": "000513",
    "东鹏饮料": "605499",
    "重庆农村商业银行": "601077",
    "晨鸣纸业": "000488",
    "中州证券": "601375",
    "红星美凯龙": "601828",
    "中国能源建设": "601868",
    "中石化油服": "600871",
    "长飞光纤光缆": "601869",
    "康希诺生物": "688185",
    "昊海生物科技": "688366",
    "安德利果汁": "605198",
    "中信建投证券": "601066",
    "中海油田服务": "601808",
    "福莱特玻璃": "601865",
    "绿色动力环保": "601330",
    "中国交通建设": "601800",
    "京城机电股份": "600860",
    "新天绿色能源": "600956",
    "中国光大银行": "601818",
    "国恩科技": "002768",
    "迈威生物-B": "688062",
}


_NAME_CACHE: Optional[pd.DataFrame] = None


def get_ah_pairs() -> pd.DataFrame:
    """
    获取当前AH股配对列表。

    通过腾讯财经的AH股列表与A股代码列表按名称匹配，建立 A股代码 ↔ H股代码 映射。
    先用精确匹配，再用去后缀匹配，最后用手动映射。

    Returns:
        DataFrame with columns [a_code, h_code, name]
    """
    global _NAME_CACHE

    # AH股列表（腾讯数据源，返回H股代码+名称）
    ah_spot = ak.stock_zh_ah_spot()
    ah_names = {
        _clean_name(row["名称"]): str(row["代码"]).zfill(5)
        for _, row in ah_spot.iterrows()
    }

    # A股代码-名称映射
    if _NAME_CACHE is None:
        _NAME_CACHE = ak.stock_info_a_code_name()
    a_lookup = {
        _clean_name(row["name"]): str(row["code"])
        for _, row in _NAME_CACHE.iterrows()
    }
    # 再建一个去后缀的索引
    a_stripped = {}
    for clean_name, code in a_lookup.items():
        s = _strip_suffix(clean_name)
        if s not in a_stripped and len(s) >= 3:
            a_stripped[s] = code

    rows = []
    for name, h_code in ah_names.items():
        a_code = None

        # 1) 精确匹配
        if name in a_lookup:
            a_code = a_lookup[name]
        # 2) 手动映射
        elif name in _MANUAL_MAP:
            a_code = _MANUAL_MAP[name]
        # 3) 去后缀匹配
        else:
            stripped = _strip_suffix(name)
            a_code = a_stripped.get(stripped)

        if a_code:
            rows.append({"a_code": a_code, "h_code": h_code, "name": name})

    return pd.DataFrame(rows)


def get_fx_history(start: str, end: str) -> pd.Series:
    """
    获取港币兑人民币中间价历史数据（分年拉取）。

    历史年份使用缓存，当前年份每次重新拉取以保证最新数据。

    Returns:
        Series, index=date, value=CNY per 100 HKD
    """
    CACHE_DIR.mkdir(exist_ok=True)
    start_year = int(start[:4])
    end_year = int(datetime.today().strftime("%Y") if end is None else end[:4])
    current_year = datetime.today().year

    frames = []
    for yr in range(start_year, end_year + 1):
        cache_path = CACHE_DIR / f"fx_cnyhkd_{yr}.pkl"

        if yr < current_year and cache_path.exists():
            raw = pd.read_pickle(cache_path)
        else:
            raw = ak.currency_boc_sina(
                symbol="港币",
                start_date=f"{yr}0101",
                end_date=f"{yr}1231",
            )
            if not raw.empty:
                raw.to_pickle(cache_path)

        if raw.empty:
            continue
        frames.append(raw)

    if not frames:
        raise RuntimeError("无法获取汇率数据")

    raw_all = pd.concat(frames)
    fx = pd.Series(
        pd.to_numeric(raw_all["央行中间价"], errors="coerce").values,
        index=pd.to_datetime(raw_all["日期"]),
        name="fx",
    )
    fx = fx.dropna().sort_index()
    return fx.loc[start:end]


def fetch_pair_data(a_code: str, h_code: str, start: str, end: str) -> Optional[pd.DataFrame]:
    """
    获取单对AH股的历史数据，支持增量更新缓存。

    A股：缓存存在时仅抓取最后日期至今的新数据，合并后保存。
    H股：ak.stock_hk_daily 不支持日期过滤，缓存过期时全量重新拉取。

    Returns:
        DataFrame with columns [a_close, h_close], index=date
        如果任一边数据获取失败，返回 None
    """
    CACHE_DIR.mkdir(exist_ok=True)

    # --- A股：增量更新 ---
    a_path = CACHE_DIR / f"a_{a_code}.pkl"
    try:
        if a_path.exists():
            a_full = pd.read_pickle(a_path)
            if _is_stale(a_full):
                new_start = (a_full.index.max() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
                try:
                    new_df = Fetcher.a_stock(a_code, start=new_start)
                    if not new_df.empty:
                        a_full = pd.concat([a_full, new_df])
                        a_full = a_full[~a_full.index.duplicated(keep="last")]
                        a_full.sort_index(inplace=True)
                        a_full.to_pickle(a_path)
                except Exception:
                    pass  # 增量失败则沿用旧缓存，下次再试
        else:
            a_full = Fetcher.a_stock(a_code, start="1990-01-01", end="2099-12-31")
            a_full.to_pickle(a_path)
    except Exception:
        return None

    # --- H股：过期则全量重取 ---
    h_path = CACHE_DIR / f"h_{h_code}.pkl"
    try:
        if h_path.exists():
            h_df = pd.read_pickle(h_path)
            if _is_stale(h_df):
                h_df = _fetch_h_stock(h_code)
                h_df.to_pickle(h_path)
        else:
            h_df = _fetch_h_stock(h_code)
            h_df.to_pickle(h_path)
    except Exception:
        return None

    a_close = a_full[["close"]].rename(columns={"close": "a_close"})

    # 切片到用户请求的区间
    merged = a_close.join(h_df, how="inner").loc[start:end]
    if merged.empty:
        return None
    return merged


def build_premium_panel(
    start: str = "2022-01-01",
    end: Optional[str] = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    构建所有AH股的溢价率面板数据。

    Args:
        start: 起始日期
        end: 截止日期
        verbose: 是否打印进度

    Returns:
        MultiIndex DataFrame: (date, stock_code) → [a_close, h_close, fx, premium]
    """
    if end is None:
        end = datetime.today().strftime("%Y-%m-%d")

    pairs = get_ah_pairs()
    fx = get_fx_history(start, end)

    frames = []
    total = len(pairs)
    for i, (_, row) in enumerate(pairs.iterrows()):
        a_code, h_code, name = row["a_code"], row["h_code"], row["name"]
        pair_df = fetch_pair_data(a_code, h_code, start, end)
        if pair_df is None:
            continue

        pair_df["stock"] = a_code
        pair_df["name"] = name
        frames.append(pair_df)

        if verbose and (i + 1) % 30 == 0:
            print(f"  [{i+1}/{total}] 已加载 {a_code} {name} ({len(pair_df)} 条)")

    if not frames:
        raise RuntimeError("没有成功获取任何AH股数据")

    panel = pd.concat(frames, axis=0)
    panel = panel.reset_index().rename(columns={"index": "date", "date": "date"})
    panel = panel.set_index(["date", "stock"]).sort_index()

    # 合并汇率，计算溢价率: (H_price_HKD * fx/100) / A_price_RMB - 1
    panel["fx"] = np.nan
    for dt in panel.index.get_level_values("date").unique():
        if dt in fx.index:
            panel.loc[(dt, slice(None)), "fx"] = fx.loc[dt]

    panel["premium"] = (panel["h_close"] * panel["fx"] / 100) / panel["a_close"] - 1
    panel = panel.dropna(subset=["premium"])

    if verbose:
        dates = panel.index.get_level_values("date").unique()
        stocks = panel.index.get_level_values("stock").unique()
        print(f"\n面板构建完成: {len(dates)} 个交易日 × {len(stocks)} 只股票")

    return panel
