# -*- coding: utf-8 -*-
"""作业③：中国银行外汇牌价 Spider。

目标站点：https://www.boc.cn/sourcedb/whpj/
页面为服务端渲染的 HTML 表格，直接用 XPath 定位每个 tr / td 即可拿到数据。
"""

import scrapy

from forex.items import ForexItem


class ForexSpider(scrapy.Spider):
    """抓取中国银行外汇牌价页面上的全部币种。"""

    name = "forex"
    allowed_domains = ["boc.cn"]
    start_urls = ["https://www.boc.cn/sourcedb/whpj/"]

    # 表头关键字，用于跳过表头行而不是靠固定下标
    HEADER_WORD = "货币名称"

    def parse(self, response):
        """解析牌价表格。

        页面结构：
            <table>
              <tr><td colspan=..>【点击进入历史牌价检索】...</td></tr>
              <tr><th>货币名称</th><th>现汇买入价</th>...</tr>
              <tr><td>阿联酋迪拉姆</td><td>180.79</td>...</tr>
            </table>

        :param response: 牌价页面响应
        :yield: ForexItem
        """
        # 逐行扫描表格，只保留有 7 个单元格的数据行
        for tr in response.xpath("//table//tr"):
            tds = tr.xpath("./td")
            if len(tds) < 7:
                continue

            # 取每个单元格的纯文本并去空白
            cells = [self._clean(td.xpath("string(.)").get()) for td in tds]
            if not cells or cells[0] == self.HEADER_WORD:
                continue

            item = ForexItem()
            item["currency"] = cells[0]
            item["tbp"] = cells[1]
            item["cbp"] = cells[2]
            item["tsp"] = cells[3]
            item["csp"] = cells[4]
            item["boccp"] = cells[5]
            item["quote_time"] = cells[6]
            yield item

    @staticmethod
    def _clean(text):
        """去除文本中的空白与不间断空格。

        :param text: 原始文本
        :return: 清理后的字符串
        """
        if text is None:
            return ""
        return text.replace("\xa0", " ").strip()
