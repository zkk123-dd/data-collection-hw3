# -*- coding: utf-8 -*-
"""作业②：股票行情数据项定义。

字段与作业要求的表头一一对应：
    序号 / 股票代码 / 股票名称 / 最新报价 / 涨跌幅 / 涨跌额
    成交量 / 振幅 / 最高 / 最低 / 今开 / 昨收
"""

import scrapy


class StockItem(scrapy.Item):
    """一条 A 股行情记录。"""

    # 序号，按抓取顺序编号
    seq = scrapy.Field()
    # 股票代码，例如 301348
    stock_code = scrapy.Field()
    # 股票名称，例如 蓝箭电子
    stock_name = scrapy.Field()
    # 最新报价（元）
    latest_price = scrapy.Field()
    # 涨跌幅，单位 %
    change_percent = scrapy.Field()
    # 涨跌额（元）
    change_amount = scrapy.Field()
    # 成交量（手）
    volume = scrapy.Field()
    # 振幅，单位 %
    amplitude = scrapy.Field()
    # 当日最高价
    high = scrapy.Field()
    # 当日最低价
    low = scrapy.Field()
    # 今开价
    open_price = scrapy.Field()
    # 昨收价
    prev_close = scrapy.Field()
