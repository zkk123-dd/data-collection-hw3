# 数据采集与融合技术 第三次作业

学号：102402148　姓名：周凯

## 作业内容

| 题目 | 目标站点 | 技术路线 | 产出 |
| --- | --- | --- | --- |
| 作业① 图片爬虫 | 当当网搜索结果页 | requests + threading / queue | 48 页上限、148 张原图，单线程与 10 线程对照 |
| 作业② 股票行情 | 东方财富 A 股 | Scrapy + Item/Pipeline + MySQL | 148 只股票，12 个字段入库 |
| 作业③ 外汇牌价 | 中国银行外汇牌价 | Scrapy + XPath + MySQL | 全部 45 个币种入库 |

## 目录结构

```
第三次作业/
├── code/
│   ├── images/                     作业① 图片爬虫
│   │   └── dd_image_crawler.py     单线程 / 多线程两种实现
│   ├── stock/                      作业② Scrapy 工程
│   │   ├── fetch_stock_data.py     浏览器上下文取数（东财接口）
│   │   └── stock/
│   │       ├── items.py            StockItem
│   │       ├── pipelines.py        MySQL 管道
│   │       └── spiders/stock_spider.py
│   └── forex/                      作业③ Scrapy 工程
│       └── forex/
│           ├── items.py            ForexItem
│           ├── pipelines.py        MySQL 管道
│           └── spiders/forex_spider.py   XPath 解析表格
├── data/                           运行日志与原始数据
├── shots/                          博客用截图（含水印）
├── 102402148 周凯 第三次作业-博客.md
└── 博客预览.html
```

## 运行方式

### 环境

- Python 3.13，依赖：`requests`、`scrapy`、`pymysql`、`playwright`、`pygments`、`Pillow`
- MySQL 8.0（本机 3306，账号 `root` / `123456`，库 `spider_db`，管道会自动建库建表）

### 作业① 图片爬虫

```bash
cd code/images
python dd_image_crawler.py --mode single          # 仅单线程
python dd_image_crawler.py --mode multi --threads 10   # 仅多线程
python dd_image_crawler.py --mode both --threads 10   # 两种都跑，便于对比
```

学号推导的两个上限写在文件顶部：`MAX_PAGES = 48`、`MAX_IMAGES = 148`。

### 作业② 股票行情

```bash
cd code/stock
python fetch_stock_data.py     # 先用浏览器取数，落 data/stock_raw.json
scrapy crawl stock             # 再走 Item -> Pipeline -> MySQL
```

> 说明：东方财富的行情页已改为纯前端渲染，数据由 `push2.eastmoney.com` 接口推送，
> 且该接口对非浏览器的 TLS 指纹直接断连。因此取数用 Playwright 在页面上下文内
> `fetch`，入库仍走标准 Scrapy 管道。

### 作业③ 外汇牌价

```bash
cd code/forex
scrapy crawl forex
```

## 实测结果

| 指标 | 数值 |
| --- | --- |
| 作业① 翻页 / 去重后图片数 | 3 页 / 148 张（第 3 页即达上限） |
| 作业① 单线程耗时 | 71.14 s |
| 作业① 10 线程耗时 | 3.97 s（加速 17.92 倍） |
| 作业② 入库条数 | 148 条 |
| 作业③ 入库条数 | 45 条（全部币种） |
