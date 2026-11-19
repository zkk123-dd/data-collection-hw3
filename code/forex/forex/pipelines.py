# -*- coding: utf-8 -*-
"""作业③：外汇牌价数据管道——写入 MySQL。

Item 经 Spider 产出后，由本管道序列化并 INSERT 到 boc_forex 表。
表结构在 open_spider 中自动创建，避免手工建表漏字段。
"""

from datetime import datetime

import pymysql

# 数据库连接参数，与作业②保持一致
DB_CONF = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "charset": "utf8mb4",
}


class MysqlPipeline:
    """把 ForexItem 写入 MySQL 的 boc_forex 表。"""

    def __init__(self):
        """初始化连接与游标占位。"""
        self.conn = None
        self.cursor = None

    def open_spider(self, spider):
        """爬虫启动时连库并确保表存在。

        :param spider: 当前爬虫实例
        """
        # 建库语句放在连接之后执行，避免库不存在导致连接失败
        self.conn = pymysql.connect(**DB_CONF, autocommit=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute(
            "CREATE DATABASE IF NOT EXISTS spider_db "
            "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
        )
        self.cursor.execute("USE spider_db")
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS boc_forex (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
                currency VARCHAR(32) NOT NULL COMMENT '货币名称',
                tbp DECIMAL(12,4) NULL COMMENT '现汇买入价',
                cbp DECIMAL(12,4) NULL COMMENT '现钞买入价',
                tsp DECIMAL(12,4) NULL COMMENT '现汇卖出价',
                csp DECIMAL(12,4) NULL COMMENT '现钞卖出价',
                boccp DECIMAL(12,4) NULL COMMENT '中行折算价',
                quote_time VARCHAR(24) NULL COMMENT '牌价发布时间',
                crawl_time DATETIME NULL COMMENT '采集时间',
                UNIQUE KEY uk_currency_time (currency, quote_time)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='中国银行外汇牌价'
            """
        )
        self.conn.commit()
        spider.logger.info("boc_forex 表已就绪")

    def process_item(self, item, spider):
        """单条 Item 入库，重复则更新价格。

        :param item: ForexItem 实例
        :param spider: 当前爬虫实例
        :return: 原样返回 item，交给后续管道
        """
        sql = (
            "INSERT INTO boc_forex "
            "(currency, tbp, cbp, tsp, csp, boccp, quote_time, crawl_time) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "tbp=VALUES(tbp), cbp=VALUES(cbp), tsp=VALUES(tsp), "
            "csp=VALUES(csp), boccp=VALUES(boccp), crawl_time=VALUES(crawl_time)"
        )
        self.cursor.execute(
            sql,
            (
                item.get("currency"),
                self._to_num(item.get("tbp")),
                self._to_num(item.get("cbp")),
                self._to_num(item.get("tsp")),
                self._to_num(item.get("csp")),
                self._to_num(item.get("boccp")),
                item.get("quote_time"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        self.conn.commit()
        return item

    def close_spider(self, spider):
        """爬虫结束时关闭游标与连接。

        :param spider: 当前爬虫实例
        """
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        spider.logger.info("数据库连接已关闭")

    @staticmethod
    def _to_num(value):
        """把页面文本转成可入库的数值，空值与非法值返回 None。

        :param value: 单元格文本
        :return: float 或 None
        """
        if not value:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
