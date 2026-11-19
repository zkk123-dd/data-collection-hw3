# -*- coding: utf-8 -*-
"""作业②：A 股行情 Spider。

数据来源说明：
    东方财富的行情页（quote.eastmoney.com/center/gridlist.html）是纯前端渲染，
    HTML 里只有骨架，数据由 push2.eastmoney.com 的接口异步推送，且该接口对
    非浏览器请求直接断连。因此采集分两步：
        1. fetch_stock_data.py  用 Playwright 在浏览器上下文里请求接口，
           把 148 条原始行情落成 data/stock_raw.json；
        2. 本 Spider 读取该文件，逐条产出 StockItem，交给 Pipeline 写 MySQL。

    Scrapy 2.13 以后不再调用 start_requests()，这里用 async start() 直接
    产出 Item，Item 会正常流经 ITEM_PIPELINES。
"""

import json
import os

import scrapy

from stock.items import StockItem

# 原始数据文件：code/stock/stock/spiders -> 上四级 -> 第三次作业/data
JSON_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "data", "stock_raw.json")
)


class StockSpider(scrapy.Spider):
    """把采集好的行情记录逐条送入管道。"""

    name = "stock"
    allowed_domains = []

    async def start(self):
        """Scrapy 2.13+ 的入口：直接产出 Item。

        :yield: StockItem
        """
        if not os.path.exists(JSON_PATH):
            self.logger.error("找不到原始数据文件：%s，请先运行 fetch_stock_data.py", JSON_PATH)
            return

        with open(JSON_PATH, "r", encoding="utf-8") as fp:
            records = json.load(fp)

        self.logger.info("从 %s 读到 %d 条行情", JSON_PATH, len(records))
        for rec in records:
            item = StockItem()
            for field in item.fields:
                item[field] = rec.get(field)
            yield item
