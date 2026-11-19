# 数据采集与融合技术 第三次作业

**学号**：102402148　**姓名**：周凯　**完成时间**：2026-11-19

本作业共三题：图片爬虫（单线程/多线程）、东方财富股票行情、中国银行外汇牌价。后两题均使用 Scrapy 框架 + MySQL 存储。

---

## 一、作业要求与完成情况

| 题目 | 作业要求 | 实际交付 |
| --- | --- | --- |
| 作业① | 指定一个网站爬取全部图片；单线程 + 多线程；总页数 = 学号后 2 位（48 页）；图片数 = 学号后 3 位（148 张） | 当当网商品图，**48 页上限 / 148 张原图**；单线程 71.14 s，10 线程 3.97 s |
| 作业② | Scrapy + XPath + MySQL 爬股票信息，表头自定义 | 东方财富 A 股 **148 只**，12 个字段入库 `stock_info` |
| 作业③ | Scrapy + XPath + MySQL 爬外汇数据 | 中国银行外汇牌价 **45 个币种**入库 `boc_forex` |

作业① 的图片保存在 `code/images/images/` 子目录，控制台逐条输出每张图的 URL 与字节数。

---

## 二、环境与依赖

| 项目 | 版本 / 说明 |
| --- | --- |
| Python | 3.13 |
| Scrapy | 2.19.0 |
| MySQL | 8.0.28（绿色解压版，端口 3306，`root` / `123456`，库 `spider_db`） |
| 其他依赖 | `requests`、`pymysql`、`playwright`（channel=msedge）、`pygments`、`Pillow` |

> **MySQL 位置**：本机装在 `E:/mysql8`。不能放在中文路径下——mysqld 按系统 ANSI 编码解析路径，中文目录会被解成乱码，报 `Can't find error-message file` 与 `Permission denied`。启动方式见 `启动MySQL.bat`，或手动执行：
>
> ```
> E:\mysql8\mysql-8.0.28-winx64\bin\mysqld.exe --defaults-file=E:\mysql8\my.ini --console
> ```
>
> 管道里已写 `CREATE DATABASE IF NOT EXISTS` 和 `CREATE TABLE IF NOT EXISTS`，首次运行会自动建库建表。

---

## 三、作业① 图片爬虫

### 3.1 为什么目标站点不是中国气象网

作业举例是中国气象网，实测后放弃，原因如下：

| 站点 | 实测结果 |
| --- | --- |
| `p.weather.com.cn`（中国天气网图片频道） | `/photo/`、`/tuji/`、`/index_1.shtml` 全部重定向到 404 页；全站只有首页 14 篇图集 |
| `www.cma.gov.cn`（中国气象局图片新闻） | 17 条新闻一页列完，无分页 |
| `pic.people.com.cn`（人民网图片） | 栏目页仅 15 KB 空壳，列表由 JS 加载 |
| 中新网 / 新华网图片频道 | 本机网络不可达 |

这些站点都凑不出 48 页。最终选择**当当网搜索结果页**：`page_index` 参数可直接翻页、每页固定 60 件商品、服务端渲染，能同时满足"页数"和"图片数"两个限制。

### 3.2 实现要点

- **学号推导上限**：`MAX_PAGES = int(STU_ID[-2:])` → 48，`MAX_IMAGES = int(STU_ID[-3:])` → 148，写在文件顶部，改学号即可复用。
- **图片地址提取**：商品图现在是 `src='//img3m9.ddimg.cn/...-1_b_....jpg'` 直出外链（不再是早先的 `data-original` 懒加载），正则同时兼容 `src` 与 `data-original` 两种写法、单双引号都收。
- **取原图**：把 `-1_b_`（200px 中图）替换为 `-1_u_`（原图），单张从约 16 KB 提升到 120~320 KB。
- **去重与截断**：用 `set` 记录已见地址，累计到 148 张立即 `break`，第 3 页即收满。
- **两种下载实现**：
  - 单线程：`for` 循环顺序下载；
  - 多线程：`queue.Queue` 装任务 → N 个 `threading.Thread` 跑同一 worker → `get_nowait()` + `queue.Empty` 退出 → 结果按下标写回字典（不能用 `append`，否则顺序乱）。

### 3.3 运行

```bash
cd code/images
python dd_image_crawler.py --mode single               # 仅单线程
python dd_image_crawler.py --mode multi --threads 10   # 仅多线程
python dd_image_crawler.py --mode both --threads 10    # 两种都跑，输出对比
```

### 3.4 实测结果

| 指标 | 数值 |
| --- | --- |
| 翻页数 | 3 页（第 3 页达 148 张上限） |
| 去重后图片地址 | 148 个 |
| 单线程 | 148/148 张，25.30 MB，**71.14 s** |
| 10 线程 | 148/148 张，25.30 MB，**3.97 s** |
| 加速比 | **17.92 倍** |

加速比远大于线程数（17.92 > 10），说明单线程的时间几乎全耗在网络等待上；但继续增加线程会遇到 CDN 对单 IP 的并发节制，收益递减。

---

## 四、作业② 股票行情（东方财富）

### 4.1 接口拦截与绕行

东方财富的行情页 `quote.eastmoney.com/center/gridlist.html` 已改为纯前端渲染，HTML 里只有骨架、没有一行数据；数据由 `push2.eastmoney.com` 异步推送。该接口对普通 `requests` 请求一律直接断连（`RemoteDisconnected`），`push2`、`1.push2`、`82.push2`、`push2delay` 四个节点均试过；而同一个地址在浏览器上下文里 `fetch` 返回 200——**拦截发生在连接层，不是参数或 UA 写错**。

用无头浏览器直接打开行情页也渲染不出表格（页面依赖的外部资源在本地被拦断），所以取数拆成两步：

1. `fetch_stock_data.py`：Playwright 打开东财页面 → 在页面上下文 `page.evaluate` 里 `fetch` 接口 → 取两页（每页 100 条）→ 截断到 148 条 → 写入 `data/stock_raw.json`；
2. `scrapy crawl stock`：Spider 读 JSON，逐条产出 `StockItem` → Pipeline 写 MySQL。

接口字段与作业表头的对应关系：

| 作业表头 | 接口字段 | 数据库列 |
| --- | --- | --- |
| 股票代码 | `f12` | `stock_code` |
| 股票名称 | `f14` | `stock_name` |
| 最新报价 | `f2` | `latest_price` |
| 涨跌幅 | `f3` | `change_percent` |
| 涨跌额 | `f4` | `change_amount` |
| 成交量 | `f5` | `volume` |
| 振幅 | `f7` | `amplitude` |
| 最高 | `f15` | `high_price` |
| 最低 | `f16` | `low_price` |
| 今开 | `f17` | `open_price` |
| 昨收 | `f18` | `prev_close` |

### 4.2 Scrapy 侧实现

- `items.py`：`StockItem` 定义 12 个字段；
- `pipelines.py`：`open_spider` 建库建表，`process_item` 用 `ON DUPLICATE KEY UPDATE` 按 `stock_code` 去重；
- `spiders/stock_spider.py`：**Scrapy 2.13 以后不再调用 `start_requests()`**，改用 `async start()` 直接产出 Item，Item 仍正常流经 `ITEM_PIPELINES`。

### 4.3 运行与结果

```bash
cd code/stock
python fetch_stock_data.py    # 取数，落 data/stock_raw.json
scrapy crawl stock            # Item -> Pipeline -> MySQL
```

入库 **148 条**，与学号后三位一致。前几条样例：

| seq | 代码 | 名称 | 最新价 | 涨跌幅 | 成交量 | 振幅 | 最高 | 最低 | 今开 | 昨收 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 301348 | 蓝箭电子 | 21.660 | 20.000 | 375545 | 20.780 | 21.660 | 17.910 | 18.070 | 18.050 |
| 2 | 301030 | *ST仕净 | 2.880 | 20.000 | 211105 | 19.580 | 2.880 | 2.410 | 2.410 | 2.400 |
| 3 | 301391 | 卡莱特 | 55.980 | 19.970 | 153827 | 12.520 | 55.990 | 50.150 | 50.900 | 46.660 |

---

## 五、作业③ 外汇牌价（中国银行）

### 5.1 XPath 解析

`https://www.boc.cn/sourcedb/whpj/` 是**服务端渲染的 HTML 表格**，XPath 才有对象可解析。页面结构：

```
<table>
  <tr><td colspan=...>【点击进入历史牌价检索】...</td></tr>     ← 导航行，跳过
  <tr><th>货币名称</th><th>现汇买入价</th><th>现钞买入价</th>...</tr>   ← 表头，跳过
  <tr><td>阿联酋迪拉姆</td><td>180.90</td><td>180.90</td>...</tr>       ← 数据行
</table>
```

遍历 `//table//tr`，用两条规则跳过非数据行：单元格数 `< 7` 的跳过、首列等于"货币名称"的跳过。比写死行下标稳健，页面增删 banner 行也不会错位。

字段映射：`货币名称 → currency`、`现汇买入价 → tbp`、`现钞买入价 → cbp`、`现汇卖出价 → tsp`、`现钞卖出价 → csp`、`中行折算价 → boccp`、`发布日期 → quote_time`。

### 5.2 运行与结果

```bash
cd code/forex
scrapy crawl forex
```

入库 **45 条**（页面全部币种）。部分币种只有现钞价、现汇价为空（如文莱元、巴西雷亚尔），入库时保留为 `NULL` 而不是 0，避免混淆"没有报价"和"报价为 0"。

---

## 六、数据库设计

库名 `spider_db`，UTF8MB4，两张表。

**`stock_info`**（A 股行情）

| 列 | 类型 | 说明 |
| --- | --- | --- |
| id | INT AUTO_INCREMENT | 主键 |
| seq | INT | 序号 |
| stock_code | VARCHAR(10) | 股票代码，**唯一键** |
| stock_name | VARCHAR(32) | 名称 |
| latest_price | DECIMAL(12,3) | 最新价 |
| change_percent | DECIMAL(10,3) | 涨跌幅 % |
| change_amount | DECIMAL(10,3) | 涨跌额 |
| volume | BIGINT | 成交量（手） |
| amplitude | DECIMAL(10,3) | 振幅 % |
| high_price / low_price | DECIMAL(12,3) | 最高 / 最低 |
| open_price / prev_close | DECIMAL(12,3) | 今开 / 昨收 |
| crawl_time | DATETIME | 采集时间 |

**`boc_forex`**（外汇牌价）

| 列 | 类型 | 说明 |
| --- | --- | --- |
| id | INT AUTO_INCREMENT | 主键 |
| currency | VARCHAR(32) | 货币名称 |
| tbp / cbp / tsp / csp | DECIMAL(12,4) | 现汇买入/现钞买入/现汇卖出/现钞卖出 |
| boccp | DECIMAL(12,4) | 中行折算价 |
| quote_time | VARCHAR(24) | 牌价发布时间 |
| crawl_time | DATETIME | 采集时间 |

唯一键 `(currency, quote_time)`，配合 `ON DUPLICATE KEY UPDATE`，重复运行不会产生重复行。

> 价格字段用 `DECIMAL` 而非 `FLOAT`：浮点存金额会出现 `21.659999847` 这类尾数。

---

## 七、踩坑记录

1. **mysqld 不接受中文路径**。解压在 `C:\Users\周凯\WorkBuddy\数据采集与融合\...` 下初始化时报 `Can't find error-message file ...share\errmsg.sys`，实为路径被按 ANSI 解码成乱码，所有文件都"找不到"。挪到 `E:/mysql8` 一次通过。另外 8.0 的 `errmsg.sys` 在 `share/english/`，需复制到 `share/` 根目录。
2. **`skip-name-resolve` 会让 `root@localhost` 连不上 `127.0.0.1`**，报 `1130 Host is not allowed`。去掉该参数，或另建 `root@'127.0.0.1'` 用户。
3. **Pygments 行号**：`HtmlFormatter(nowrap=True, linenos="inline")` 行号无效——`nowrap` 会忽略行号设置。正确写法是 `linenos="inline"` 且不加 `nowrap`，再截 `.highlight` 元素。
4. **截图宽度会循环放大**：若按元素宽度设视口、而元素又撑满视口（`min-width:100%` 或截的是外层 `div`），每张图宽度会递增（实测一路涨到 1800 px）。代码块要 `display:inline-block` 且不设 `min-width`，截 `pre` 而非外层容器。
5. **当当商品图结构变过**：早先真实地址在 `data-original`（`src` 是 `url_none.png` 占位图），现在是 `src` 直出 `-1_b_` 外链。照抄旧代码会全拿到占位图。
6. **同花顺 `q.10jqka.com.cn` 有头浏览器可渲染**（20 行/页），但默认列缺成交量、最高、最低、今开、昨收，字段不全，未采用。

---

## 八、目录结构

```
第三次作业/
├── code/
│   ├── images/                         作业① 图片爬虫
│   │   ├── dd_image_crawler.py         单线程 / 多线程两种实现
│   │   └── images/                     148 张下载的原图
│   ├── stock/                          作业② Scrapy 工程
│   │   ├── fetch_stock_data.py         浏览器上下文取数
│   │   ├── scrapy.cfg
│   │   └── stock/
│   │       ├── items.py                StockItem
│   │       ├── pipelines.py            MySQL 管道
│   │       └── spiders/stock_spider.py
│   └── forex/                          作业③ Scrapy 工程
│       ├── scrapy.cfg
│       └── forex/
│           ├── items.py                ForexItem
│           ├── pipelines.py            MySQL 管道
│           └── spiders/forex_spider.py XPath 解析表格
├── data/                               运行日志与原始 JSON
├── shots/                              博客与文档用截图（含学号水印）
├── 102402148 周凯 第三次作业-博客.md    博客园投稿正文
├── 博客预览.html                        博客排版预览
├── make_shots.py                       截图生成脚本
├── build_blog.py                       博客生成脚本
├── 启动MySQL.bat                        数据库启动脚本
└── README.md                           本文件
```

---

## 九、博客

按作业要求写成两个大标题、每个大标题下两个小标题（第一个小标题放代码与截图，第二个写心得）：

- `102402148 周凯 第三次作业-博客.md` —— 博客园投稿正文，代码以代码块形式嵌入
- `博客预览.html` —— 渲染后的排版预览

> 投稿到博客园时，Markdown 中的图片为本地相对路径 `shots/xxx.png`，需在编辑器里重新上传这 33 张截图。
