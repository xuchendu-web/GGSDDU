# -*- coding: utf-8 -*-
"""下载全部 A 股场内 ETF 历史日线数据(新浪接口:不复权收盘价 + 真实成交额)。

说明:东财历史 K 线接口在本环境不可用(数据中心 IP 被拒),改用新浪接口。
新浪价格为不复权价,对有分红的基金收益略有低估(保守方向)。
输出:data/etf_daily.parquet 长表(code, name, date, open, close, amount)
"""
import os
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

import akshare as ak
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

OUT_PATH = os.path.join(DATA_DIR, "etf_daily.parquet")
LIST_PATH = os.path.join(DATA_DIR, "etf_list.csv")


def get_etf_list() -> pd.DataFrame:
    if os.path.exists(LIST_PATH):
        return pd.read_csv(LIST_PATH, dtype={"code": str})
    df = ak.fund_etf_spot_em()
    df = df[["代码", "名称"]].rename(columns={"代码": "code", "名称": "name"})
    df = df.drop_duplicates(subset="code").reset_index(drop=True)
    df.to_csv(LIST_PATH, index=False)
    return df


def to_sina_symbol(code: str) -> str:
    return ("sh" if code.startswith("5") else "sz") + code


def fetch_one(code: str, name: str, retries: int = 3) -> pd.DataFrame | None:
    for i in range(retries):
        try:
            df = ak.fund_etf_hist_sina(symbol=to_sina_symbol(code))
            if df is None or df.empty:
                return None
            df = df[["date", "open", "close", "amount"]].copy()
            df["code"] = code
            df["name"] = name
            return df
        except Exception:
            if i == retries - 1:
                print(f"FAIL {code} {name}", flush=True)
                traceback.print_exc()
            time.sleep(1 + i * 2)
    return None


def main():
    etfs = get_etf_list()
    print(f"共 {len(etfs)} 只场内基金", flush=True)
    frames = []
    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_one, r.code, r.name): r.code for r in etfs.itertuples()}
        for fut in as_completed(futs):
            df = fut.result()
            done += 1
            if df is not None:
                frames.append(df)
            if done % 100 == 0:
                print(f"{done}/{len(etfs)} 完成, 成功 {len(frames)}", flush=True)
    full = pd.concat(frames, ignore_index=True)
    full["date"] = pd.to_datetime(full["date"])
    for col in ("open", "close", "amount"):
        full[col] = pd.to_numeric(full[col], errors="coerce")
    full = full.sort_values(["code", "date"]).reset_index(drop=True)
    full.to_parquet(OUT_PATH, index=False)
    print(f"保存 {OUT_PATH}: {full.shape}, {full['code'].nunique()} 只基金, "
          f"日期范围 {full['date'].min()} ~ {full['date'].max()}", flush=True)


if __name__ == "__main__":
    main()
