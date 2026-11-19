# -*- coding: utf-8 -*-
"""作业②：东方财富行情数据采集（浏览器上下文取数）。

为什么不在 Spider 里直接 requests？
    东方财富的行情数据全部由 push2.eastmoney.com 的接口异步推送，
    页面 HTML 里没有任何表格数据；而且该接口会对非浏览器的 TLS 指纹
    直接断开连接（requests 请求一律 RemoteDisconnected）。
    因此这里用 Playwright 驱动真实浏览器，在页面上下文内 fetch 接口，
    把结果落成 JSON，交给 Scrapy 的 Spider 走 Item -> Pipeline -> MySQL。

    XPath 的完整用法见作业③（中国银行外汇牌价），那一页是真正的
    服务端渲染 HTML 表格，XPath 才有对象可解析。

输出：data/stock_raw.json   [{seq, stock_code, stock_name, ...}, ...]
"""

import json
import os
import sys

for _key in list(os.environ):
    if "proxy" in _key.lower():
        os.environ.pop(_key, None)

from playwright.sync_api import sync_playwright

# 目标条数：学号 102402148 后三位 148
TARGET_COUNT = 148
# 每页取 100 条，够 148 只只需两页
PAGE_SIZE = 100

# 沪深京 A 股板块过滤条件
MARKET_FILTER = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"

# 需要向接口索取的字段，与作业表头一一对应
FIELDS = "f12,f14,f2,f3,f4,f5,f6,f7,f15,f16,f17,f18"

BASE_URL = "https://push2.eastmoney.com/api/qt/clist/get"
REFERER_PAGE = "https://quote.eastmoney.com/center/gridlist.html"

OUTPUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..", "data", "stock_raw.json"
)


def build_api_url(page_no):
    """拼出第 page_no 页的接口地址。

    :param page_no: 页码，从 1 开始
    :return: 完整 URL
    """
    return (
        f"{BASE_URL}?pn={page_no}&pz={PAGE_SIZE}&po=1&np=1&fltt=2&invt=2"
        f"&fid=f3&fs={MARKET_FILTER}&fields={FIELDS}"
    )


def fetch_page(page, page_no):
    """在浏览器上下文里请求一页行情数据。

    :param page: Playwright 的 Page 对象
    :param page_no: 页码
    :return: diff 列表（每项是一只股票）
    """
    script = """async (url) => {
        const resp = await fetch(url, {credentials: 'include'});
        return await resp.text();
    }"""
    raw = page.evaluate(script, build_api_url(page_no))
    payload = json.loads(raw)
    data = payload.get("data") or {}
    return data.get("diff") or []


def to_float(value):
    """把接口返回的数值规范化，'-' 之类的占位符返回 None。

    :param value: 原始值
    :return: float 或 None
    """
    if value in (None, "-", ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main():
    """抓取足够条数的行情并写入 JSON。"""
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge",
            headless=True,
            args=["--no-proxy-server", "--disable-blink-features=AutomationControlled"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        # 先进一次东财页面，让后续 fetch 带上同源上下文
        page.goto(REFERER_PAGE, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)

        page_no = 1
        while len(rows) < TARGET_COUNT:
            diff = fetch_page(page, page_no)
            if not diff:
                print(f"[停止] 第 {page_no} 页没有数据")
                break
            print(f"[接口] 第 {page_no} 页取到 {len(diff)} 条")
            rows.extend(diff)
            page_no += 1
            if page_no > 10:
                break
        browser.close()

    # 截断到学号规定的条数
    rows = rows[:TARGET_COUNT]

    records = []
    for seq, row in enumerate(rows, start=1):
        records.append({
            "seq": seq,
            "stock_code": row.get("f12"),
            "stock_name": row.get("f14"),
            "latest_price": to_float(row.get("f2")),
            "change_percent": to_float(row.get("f3")),
            "change_amount": to_float(row.get("f4")),
            "volume": to_float(row.get("f5")),
            "amplitude": to_float(row.get("f7")),
            "high": to_float(row.get("f15")),
            "low": to_float(row.get("f16")),
            "open_price": to_float(row.get("f17")),
            "prev_close": to_float(row.get("f18")),
        })

    out_path = os.path.abspath(OUTPUT)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fp:
        json.dump(records, fp, ensure_ascii=False, indent=2)

    print(f"[完成] 共 {len(records)} 条，已写入 {out_path}")
    for rec in records[:3]:
        print("  ", rec)


if __name__ == "__main__":
    sys.exit(main())
