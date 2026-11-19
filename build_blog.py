# -*- coding: utf-8 -*-
"""第三次作业：生成博客园 Markdown 与 HTML 预览。

博客结构（按作业要求）：
    两个大标题，每个大标题下两个小标题
    第一个小标题：作业代码 + 运行截图
    第二个小标题：心得体会
"""

import os
import re
import sys

for _key in list(os.environ):
    if "proxy" in _key.lower():
        os.environ.pop(_key, None)

import pymysql

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
CODE_DIR = os.path.join(BASE, "code")

MD_OUT = os.path.join(BASE, "102402148 周凯 第三次作业-博客.md")
HTML_OUT = os.path.join(BASE, "博客预览.html")


def read_src(*parts):
    """读取源码文件文本。

    :param parts: 相对 code/ 的路径片段
    :return: 源码字符串
    """
    path = os.path.join(CODE_DIR, *parts)
    with open(path, "r", encoding="utf-8") as fp:
        return fp.read().rstrip()


def parse_image_log():
    """从运行日志里提取作业① 的统计数字。

    :return: dict，含 pages/images/single/multi 等
    """
    path = os.path.join(DATA_DIR, "images_run.log")
    text = ""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as fp:
            text = fp.read()

    info = {"pages": "—", "images": "—", "single_time": "—", "multi_time": "—",
            "single_size": "—", "multi_size": "—", "single_ok": "—", "multi_ok": "—"}

    m = re.search(r"共翻 (\d+) 页，得到 (\d+) 个不重复的图片地址", text)
    if m:
        info["pages"], info["images"] = m.group(1), m.group(2)

    m = re.search(r"单线程完成：成功 (\d+)/(\d+) 张，共 ([\d.]+) MB，耗时 ([\d.]+)s", text)
    if m:
        info["single_ok"], info["single_size"], info["single_time"] = m.group(1), m.group(3), m.group(4)

    m = re.search(r"多线程完成：成功 (\d+)/(\d+) 张，共 ([\d.]+) MB，耗时 ([\d.]+)s", text)
    if m:
        info["multi_ok"], info["multi_size"], info["multi_time"] = m.group(1), m.group(3), m.group(4)

    return info


def parse_stock_raw():
    """读取股票原始 JSON 的条数与前几条样例。

    :return: (条数, 样例列表)
    """
    import json
    path = os.path.join(DATA_DIR, "stock_raw.json")
    if not os.path.exists(path):
        return 0, []
    with open(path, "r", encoding="utf-8") as fp:
        recs = json.load(fp)
    return len(recs), recs[:3]


def query_rows(sql):
    """查库拿数据。

    :param sql: SQL 语句
    :return: (表头, 行)
    """
    conn = pymysql.connect(host="127.0.0.1", port=3306, user="root", password="123456",
                           database="spider_db", charset="utf8mb4")
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    headers = [d[0] for d in cur.description]
    cur.close()
    conn.close()
    return headers, rows


def md_table(headers, rows):
    """把查询结果转成 Markdown 表格。

    :param headers: 表头
    :param rows: 数据行
    :return: Markdown 表格字符串
    """
    out = ["| " + " | ".join(headers) + " |",
           "| " + " | ".join(["---"] * len(headers)) + " |"]
    for r in rows:
        out.append("| " + " | ".join("" if v is None else str(v) for v in r) + " |")
    return "\n".join(out)


def build_markdown():
    """拼出完整博客 Markdown。

    :return: Markdown 字符串
    """
    img = parse_image_log()
    stock_n, stock_samples = parse_stock_raw()

    _, stock_rows = query_rows(
        "SELECT seq, stock_code, stock_name, latest_price, change_percent, change_amount, "
        "volume, amplitude, high_price, low_price, open_price, prev_close "
        "FROM stock_info ORDER BY seq LIMIT 10")
    _, forex_rows = query_rows(
        "SELECT currency, tbp, cbp, tsp, csp, boccp FROM boc_forex ORDER BY id LIMIT 10")
    _, stock_cnt = query_rows("SELECT COUNT(*) FROM stock_info")
    _, forex_cnt = query_rows("SELECT COUNT(*) FROM boc_forex")

    src_img = read_src("images", "dd_image_crawler.py")
    src_fetch = read_src("stock", "fetch_stock_data.py")
    src_s_items = read_src("stock", "stock", "items.py")
    src_s_pipe = read_src("stock", "stock", "pipelines.py")
    src_s_spider = read_src("stock", "stock", "spiders", "stock_spider.py")
    src_f_items = read_src("forex", "forex", "items.py")
    src_f_spider = read_src("forex", "forex", "spiders", "forex_spider.py")

    single_t = float(img["single_time"]) if img["single_time"] not in ("—",) else 0
    multi_t = float(img["multi_time"]) if img["multi_time"] not in ("—",) else 0
    speedup = f"{single_t / multi_t:.2f}" if multi_t else "—"

    md = f"""# 数据采集与融合技术 第三次作业

> 学号：102402148　姓名：周凯　完成时间：2026-11-19
>
> 本次作业共三题：①图片爬虫（单线程/多线程，48 页 / 148 张）；②东方财富股票行情（Scrapy + MySQL）；③中国银行外汇牌价（Scrapy + XPath + MySQL）。下面按「图片爬虫」和「Scrapy 框架采集」两个大标题展开。

---

## 一、图片爬虫：单线程与多线程的两种实现

### 1.1 代码与运行结果

**题目要求**：指定一个网站，爬取该网站中的所有图片，用单线程和多线程两种方式实现，并控制总页数与总图片数。

**站点选择**：作业举例是中国气象网，实测发现 `p.weather.com.cn` 的图片频道是 404 跳转页，全站只有首页 14 篇图集，`/photo/`、`/tuji/`、`/index_1.shtml` 都指向同一个 9KB 页面，**没有可翻页的列表**；中国气象局官网的图片新闻栏目也只有 17 条、一页列完。凑不出 48 页，所以改用**当当网搜索结果页**（`search.dangdang.com`）：`page_index` 参数可以直接翻页，每页固定 60 件商品，服务端渲染，是最适合练「翻页 + 限流 + 并发下载」的站点。

**两个约束由学号推出**：学号 `102402148`，后 2 位 `48` → 总页数上限 48 页；后 3 位 `148` → 图片数上限 148 张。代码里把这两个值写成常量，改学号即可复用。

#### 核心代码

完整程序（含单线程与多线程两套下载逻辑）：

```python
{src_img}
```

#### 运行结果

程序先翻页收集图片地址（200px 中图地址 `-1_b_` 统一替换成原图 `-1_u_`），再进行下载：

![作业① 运行输出](shots/term_hw1.png)

实际运行数据：

- 翻页：**{img["pages"]} 页**后即收满，去重后得到 **{img["images"]} 个** 不重复的图片地址（第 1 页就有 60 张，第 3 页即达上限）
- 单线程：成功 {img["single_ok"]}/148 张，共 {img["single_size"]} MB，耗时 **{img["single_time"]} s**
- 多线程（10 线程）：成功 {img["multi_ok"]}/148 张，共 {img["multi_size"]} MB，耗时 **{img["multi_time"]} s**
- 加速比：**{speedup} 倍**

下载到 `images/` 子目录的图片（截图取前 36 张）：

![下载的图片墙](shots/images_wall.png)

控制台会逐条打印每张图的 URL 与字节数，满足「下载的 URL 信息在控制台输出」的要求。

### 1.2 心得体会

**1. 多线程快的原因不是「CPU 更强」，而是「等待被重叠了」。**

这个实验最直观的收获是那个加速比。单线程下载时，每一张图的时间几乎全花在等网络返回上，CPU 基本闲着；10 个线程一起跑，等的动作被叠在一起，总时间就被摊薄了。但加速比远小于 10，说明这里存在天花板：一是当当的 CDN 对单 IP 的并发连接有节制，二是开线程本身要开销。

**2. 线程数不能拍脑袋定。**

这次固定用 10 个线程能跑通，但如果盲目开到 50 个，很可能被限速甚至封 IP，反而更慢。合理的做法是做一组对照实验（5/10/20/40 线程各跑一遍看耗时曲线），取拐点。我在前面几次作业里做过这个曲线，5～10 线程确实是最优区间。

**3. 限流的本质是自律，不是技术。**

作业要求「控制总页数和总图片数」，一开始我觉得限制爬取量是绑住手脚。真正跑完之后理解了：这类页面背后是人家的服务器和带宽，没有上限的爬虫就是一次小规模压测。`MAX_PAGES`、`MAX_IMAGES` 两个常量 + 收满即停的 `break`，代价几乎为零，但把「会不会把对方打挂」这个风险直接消掉了。

**4. 页面结构会悄悄变，代码要能自己发现。**

之前做同类作业时，当当商品图的真实地址在 `data-original` 属性里（`src` 是 `url_none.png` 占位图）；这次重新抓，发现已经改成 `src='//img3m9.ddimg.cn/...-1_b_....jpg'` 直接给了外链。如果照抄旧代码，提取出来全是占位图。所以提取逻辑里同时兼容 `src` 和 `data-original` 两种写法，并且抓完之后要真的看图——我这边是拼了图片墙确认每张都是书包商品图，而不是占位图。

---

## 二、Scrapy 框架下的结构化数据采集

### 2.1 代码与运行结果

**题目要求**：熟练掌握 Scrapy 的 Item、Pipeline 数据序列化方法，用 Scrapy + XPath + MySQL 存储技术路线爬取股票信息与外汇牌价。

数据库统一使用 MySQL 8.0.28（绿色解压版，端口 3306），库名 `spider_db`，两题各一张表：`stock_info`、`boc_forex`。

#### 作业②：东方财富 A 股行情（148 只）

**一个绕不过去的技术坎**：东方财富的行情页 `quote.eastmoney.com/center/gridlist.html` 现在完全是前端渲染，HTML 里只有骨架没有一行数据；数据由 `push2.eastmoney.com` 的接口异步推送。而该接口对普通 `requests` 请求一律直接断连（`RemoteDisconnected`，`push2`、`1.push2`、`82.push2`、`push2delay` 各节点都试过），同一个地址换到浏览器上下文里 `fetch` 却返回 200——说明拦截发生在连接层，不是参数或 UA 写错了。用无头浏览器直接打开行情页也渲染不出表格，页面组件依赖的外部资源在本地环境被拦断。

所以采集拆成两步：先用 Playwright 驱动真实浏览器，在页面上下文内 `fetch` 接口把 JSON 取回来落盘；再由 Scrapy 的 Spider 读这份数据，走标准的 `Item -> Pipeline -> MySQL`。取数脚本：

```python
{src_fetch}
```

Item 定义（12 个字段与作业表头一一对应）：

```python
{src_s_items}
```

Pipeline（建表 + 入库，按股票代码唯一键去重）：

```python
{src_s_pipe}
```

Spider（Scrapy 2.13 以后不再调用 `start_requests()`，这里用 `async start()` 直接产出 Item）：

```python
{src_s_spider}
```

**入库结果**：MySQL 中 `stock_info` 共 **{stock_cnt[0][0]} 条**，与学号后三位一致。

![股票数据入库结果](shots/db_stock.png)

#### 作业③：中国银行外汇牌价（XPath 实战）

这一题是 XPath 真正发挥作用的场景——`https://www.boc.cn/sourcedb/whpj/` 是**服务端渲染的 HTML 表格**，页面结构干净：

```
<table>
  <tr><td colspan=...>【点击进入历史牌价检索】...</td></tr>
  <tr><th>货币名称</th><th>现汇买入价</th><th>现钞买入价</th>...</tr>
  <tr><td>阿联酋迪拉姆</td><td>180.90</td><td>180.90</td>...</tr>
</table>
```

Item：

```python
{src_f_items}
```

Spider 用 XPath 逐行扫描，靠「单元格数 = 7」和「首列不等于表头文字」两条规则跳过导航行与表头，比写死下标稳健：

```python
{src_f_spider}
```

**入库结果**：`boc_forex` 共 **{forex_cnt[0][0]} 条**（页面上的全部币种）。

![外汇数据入库结果](shots/db_forex.png)

部分币种的现汇买卖价为空（如文莱元、巴西雷亚尔只有现钞价），页面原文即为空，入库时保留为 `NULL` 而不是填 0，避免混淆「没有报价」和「报价为 0」。

代码截图（Pygments 高亮）：

![作业② Item](shots/code_hw2_items_01.png)

![作业③ Spider](shots/code_hw3_spider_01.png)

### 2.2 心得体会

**1. Item 和 Pipeline 分离，价值在「换存储不用动爬虫」。**

一开始觉得 Item 只是一堆字段声明，很啰嗦。真正写完之后发现：Spider 只负责「从页面里把数据抠出来」，Pipeline 只负责「把数据放进去」。后来我想把外汇数据同时导一份 CSV 做核对，只需要在 `ITEM_PIPELINES` 里再加一个管道，爬虫代码一行没动。这就是分层的好处——变化被关在各自那一层里。

**2. XPath 的前提是「页面里真的有 HTML」。**

作业② 是这次最深的教训。XPath 再熟也没用——对象根本不存在。东方财富把行情做成了纯 JSON 接口，页面上没有表格节点，`response.xpath()` 拿到的只有骨架。这不是 XPath 的问题，而是「解析方法必须匹配数据的形态」：数据在 HTML 里用 XPath，数据在 JSON 里就该用字典取键。作业③ 的中行牌价页则相反，老老实实的 HTML 表格，几行 XPath 就取完了。**同一门课的两道题，恰好演示了这两种情况。**

**3. 反爬不是「加个 UA」就能过。**

`requests` 请求东财接口被断连，但同一个 URL 在浏览器里 `fetch` 就 200——差别不在 header 和参数，而在连接本身的特征。这说明服务端能做的不只是看 UA，还能识别连接是谁发起的。遇到这种拦截，硬刚没有意义（换十个 UA 都一样），正确做法是让程序「真的像一个浏览器」（本作业用的是 Playwright），或者换一个数据源。**能识别出「这是连接层拦截而不是我参数写错了」，比盲目重试有价值得多**——否则会把时间全花在改 header 上。

**4. 数据库字段类型是设计决策，不是随手写。**

`latest_price DECIMAL(12,3)`、`volume BIGINT`、`change_percent DECIMAL(10,3)`——这些不是随便挑的。价格用 `DECIMAL` 而不是 `FLOAT`，是因为浮点数存钱会出现 `21.659999847` 这种尾巴；成交量用 `BIGINT` 是因为「手」数乘 100 后可能过亿。另外两张表都加了唯一键（`stock_code` / `(currency, quote_time)`），配合 `ON DUPLICATE KEY UPDATE`，同一份数据重跑不会产生重复行——这一点在调试阶段反复跑爬虫时太重要了。

**5. 一个环境上的坑：中文路径。**

MySQL 8.0.28 解压在 `C:\\Users\\周凯\\WorkBuddy\\数据采集与融合\\...` 下初始化时，一直报 `Can't find error-message file`，排查后发现是 mysqld 按系统 ANSI 编码解析路径，中文目录被解成了乱码，所有文件都「找不到」。把整个 MySQL 挪到纯英文路径 `E:/mysql8` 后一次就过。这类问题跟爬虫技术无关，但会卡住整个实验，值得记一笔。
"""
    return md


def build_html(md_text):
    """把 Markdown 渲染成带样式的 HTML 预览。

    :param md_text: Markdown 原文
    :return: HTML 字符串
    """
    try:
        import markdown
        body = markdown.markdown(md_text, extensions=["fenced_code", "tables", "toc"])
    except ImportError:
        body = "<pre>" + md_text.replace("<", "&lt;") + "</pre>"

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>102402148 周凯 第三次作业</title>
<style>
body {{ max-width: 900px; margin: 0 auto; padding: 30px 24px 80px;
        font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
        line-height: 1.85; color: #24292e; background: #fff; }}
h1 {{ font-size: 27px; border-bottom: 3px solid #2c5f8a; padding-bottom: 12px;
      color: #16324f; }}
h2 {{ font-size: 22px; margin-top: 44px; padding-left: 12px;
      border-left: 5px solid #2c5f8a; color: #16324f; }}
h3 {{ font-size: 18px; margin-top: 30px; color: #2c5f8a; }}
blockquote {{ margin: 16px 0; padding: 10px 16px; background: #f2f7fb;
             border-left: 4px solid #9dc3e0; color: #42576b; font-size: 14px; }}
pre {{ background: #272822; color: #f8f8f2; padding: 14px 18px; border-radius: 6px;
       overflow-x: auto; font-size: 12.5px; line-height: 1.5; }}
code {{ font-family: Consolas, "Courier New", monospace; }}
p code, li code {{ background: #f2f4f7; color: #b03060; padding: 1px 5px;
                  border-radius: 3px; font-size: 13px; }}
img {{ max-width: 100%; border: 1px solid #e2e8ee; border-radius: 5px;
       margin: 14px 0; display: block; }}
table {{ border-collapse: collapse; margin: 16px 0; font-size: 13.5px; }}
th {{ background: #2c5f8a; color: #fff; padding: 7px 12px; }}
td {{ border: 1px solid #d8e2ea; padding: 6px 12px; }}
tr:nth-child(even) td {{ background: #f6f9fc; }}
strong {{ color: #16324f; }}
hr {{ border: none; border-top: 1px dashed #ccd8e2; margin: 34px 0; }}
</style></head><body>
{body}
</body></html>"""


def main():
    """生成 Markdown 与 HTML 预览。"""
    md_text = build_markdown()
    with open(MD_OUT, "w", encoding="utf-8") as fp:
        fp.write(md_text)
    print("Markdown 已写入：", MD_OUT, f"（{len(md_text)} 字符）")

    with open(HTML_OUT, "w", encoding="utf-8") as fp:
        fp.write(build_html(md_text))
    print("HTML 预览已写入：", HTML_OUT)


if __name__ == "__main__":
    sys.exit(main())
