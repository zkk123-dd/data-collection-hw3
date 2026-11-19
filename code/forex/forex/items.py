# -*- coding: utf-8 -*-
"""作业③：中国银行外汇牌价数据项定义。

把页面表格的一行映射成一个 Item，字段名与作业要求的三列表头保持一致
（Currency / TBP / CBP / TSP / CSP / Time）。
"""

import scrapy


class ForexItem(scrapy.Item):
    """一条外汇牌价记录。"""

    # 货币名称，例如「阿联酋迪拉姆」
    currency = scrapy.Field()
    # 现汇买入价（Telegraphic Buying Price）
    tbp = scrapy.Field()
    # 现钞买入价（Cash Buying Price）
    cbp = scrapy.Field()
    # 现汇卖出价（Telegraphic Selling Price）
    tsp = scrapy.Field()
    # 现钞卖出价（Cash Selling Price）
    csp = scrapy.Field()
    # 中行折算价（Bank of China Conversion Price），页面有该列，一并保留
    boccp = scrapy.Field()
    # 牌价发布时间，例如 2026/11/19 23:45:51
    quote_time = scrapy.Field()
    # 采集时间，由管道写入，便于区分多次采集
    crawl_time = scrapy.Field()
