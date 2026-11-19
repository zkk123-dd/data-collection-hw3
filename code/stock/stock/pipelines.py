# -*- coding: utf-8 -*-
"""作业②：股票行情数据管道——写入 MySQL。

与作业③ 使用同一个库 spider_db，表名 stock_info。
字段类型按「金额三位小数、成交量整数」设计，避免数值被截断。
"""

from datetime import datetime

import pymysql

DB_CONF = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "123456",
    "charset": "utf8mb4",
}


class MysqlPipeline:
    """把 StockItem 写入 MySQL 的 stock_info 表。"""

    def __init__(self):
        """初始化连接占位。"""
        self.conn = None
        self.cursor = None

    def open_spider(self, spider):
        """启动时连库、建库建表。

        :param spider: 当前爬虫实例
        """
        self.conn = pymysql.connect(**DB_CONF, autocommit=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute(
            "CREATE DATABASE IF NOT EXISTS spider_db "
            "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
        )
        self.cursor.execute("USE spider_db")
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_info (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
                seq INT NULL COMMENT '序号',
                stock_code VARCHAR(10) NOT NULL COMMENT '股票代码',
                stock_name VARCHAR(32) NULL COMMENT '股票名称',
                latest_price DECIMAL(12,3) NULL COMMENT '最新报价',
                change_percent DECIMAL(10,3) NULL COMMENT '涨跌幅%',
                change_amount DECIMAL(10,3) NULL COMMENT '涨跌额',
                volume BIGINT NULL COMMENT '成交量(手)',
                amplitude DECIMAL(10,3) NULL COMMENT '振幅%',
                high_price DECIMAL(12,3) NULL COMMENT '最高',
                low_price DECIMAL(12,3) NULL COMMENT '最低',
                open_price DECIMAL(12,3) NULL COMMENT '今开',
                prev_close DECIMAL(12,3) NULL COMMENT '昨收',
                crawl_time DATETIME NULL COMMENT '采集时间',
                UNIQUE KEY uk_code (stock_code)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='A股实时行情'
            """
        )
        self.conn.commit()
        spider.logger.info("stock_info 表已就绪")

    def process_item(self, item, spider):
        """单条 Item 入库，同一代码重复则覆盖。

        :param item: StockItem 实例
        :param spider: 当前爬虫实例
        :return: 原样返回 item
        """
        sql = (
            "INSERT INTO stock_info "
            "(seq, stock_code, stock_name, latest_price, change_percent, change_amount, "
            " volume, amplitude, high_price, low_price, open_price, prev_close, crawl_time) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "seq=VALUES(seq), stock_name=VALUES(stock_name), latest_price=VALUES(latest_price), "
            "change_percent=VALUES(change_percent), change_amount=VALUES(change_amount), "
            "volume=VALUES(volume), amplitude=VALUES(amplitude), high_price=VALUES(high_price), "
            "low_price=VALUES(low_price), open_price=VALUES(open_price), "
            "prev_close=VALUES(prev_close), crawl_time=VALUES(crawl_time)"
        )
        self.cursor.execute(
            sql,
            (
                item.get("seq"),
                item.get("stock_code"),
                item.get("stock_name"),
                item.get("latest_price"),
                item.get("change_percent"),
                item.get("change_amount"),
                item.get("volume"),
                item.get("amplitude"),
                item.get("high"),
                item.get("low"),
                item.get("open_price"),
                item.get("prev_close"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        self.conn.commit()
        return item

    def close_spider(self, spider):
        """收尾关闭连接。

        :param spider: 当前爬虫实例
        """
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        spider.logger.info("数据库连接已关闭")
