# -*- coding: utf-8 -*-
"""第三次作业：生成博客用截图（代码页 / 终端页 / 数据表 / 图片墙）。

做法：
    1. 代码用 Pygments 高亮成 HTML，Playwright 渲染后按元素截图；
    2. 终端输出套一个深色终端样式的 HTML；
    3. MySQL 查询结果排版成表格截图；
    4. 下载的图片拼成图片墙；
    5. 统一用 PIL 叠加「102402148 周凯」斜向水印。
"""

import base64
import html
import io
import os
import re
import sys

for _key in list(os.environ):
    if "proxy" in _key.lower():
        os.environ.pop(_key, None)

import pymysql
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer, SqlLexer

BASE = os.path.dirname(os.path.abspath(__file__))
SHOT_DIR = os.path.join(BASE, "shots")
IMG_DIR = os.path.join(BASE, "code", "images", "images")
DATA_DIR = os.path.join(BASE, "data")

# 截图参数
VIEW_W = 880          # 渲染视口宽
CODE_FONT = 13        # 代码字号
CODE_MAX_LINES = 30   # 每张代码图最多行数
CODE_MAX_H = 6.6      # 单图最大 CSS 高度，超了就拆

os.makedirs(SHOT_DIR, exist_ok=True)

PYG_STYLE = HtmlFormatter(style="monokai").get_style_defs(".highlight")

BASE_CSS = f"""
* {{ box-sizing: border-box; }}
body {{ margin:0; padding:0; background:#ffffff;
       font-family: "Consolas","Courier New",monospace; }}
{PYG_STYLE}
.highlight {{ display:inline-block; }}
.highlight pre {{ margin:0; padding:14px 16px; font-size:{CODE_FONT}px; line-height:1.55;
          background:#272822; color:#f8f8f2; display:inline-block;
          white-space:pre; }}
.highlight .linenos {{ color:#75715e; user-select:none;
          border-right:1px solid #444; padding-right:10px; margin-right:10px; }}
"""

TERM_CSS = """
body { margin:0; background:#ffffff; font-family:"Consolas","Courier New",monospace; }
.term { display:inline-block; width:900px; background:#1e1e1e; border-radius:6px;
        overflow:hidden; }
.bar { background:#3c3c3c; padding:6px 10px; display:flex; align-items:center; gap:6px; }
.dot { width:11px; height:11px; border-radius:50%; flex:none; display:inline-block; }
.d1 { background:#ff5f56; } .d2 { background:#ffbd2e; } .d3 { background:#27c93f; }
.title { color:#bbbbbb; font-size:12px; margin-left:8px; }
pre.body { margin:0; padding:12px 14px; color:#d4d4d4; font-size:12.5px;
           line-height:1.5; white-space:pre-wrap; word-break:break-all; }
.hl-ok { color:#4ec9b0; } .hl-warn { color:#dcdcaa; } .hl-key { color:#569cd6; }
"""


# ------------------------------------------------------------------ 水印

def add_watermark(path):
    """给截图叠加斜向半透明水印。

    :param path: 图片路径
    """
    img = Image.open(path).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    text = "102402148 周凯"
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 26)
    except OSError:
        font = ImageFont.load_default()

    # 先在一张透明图上写文字，再旋转平铺
    tw, th = draw.textbbox((0, 0), text, font=font)[2:]
    tile = Image.new("RGBA", (tw + 60, th + 40), (255, 255, 255, 0))
    td = ImageDraw.Draw(tile)
    td.text((30, 20), text, font=font, fill=(120, 120, 120, 70))
    tile = tile.rotate(25, expand=True)

    step_x, step_y = tile.width + 40, tile.height + 40
    for y in range(-tile.height, img.height, step_y):
        for x in range(-tile.width, img.width, step_x):
            overlay.paste(tile, (x, y), tile)

    Image.alpha_composite(img, overlay).convert("RGB").save(path, quality=92)


# ------------------------------------------------------------------ 通用截图

def shoot(page, element, out_name, pad=8):
    """按元素实际尺寸截图并加水印。

    :param page: Playwright Page
    :param element: 要截的元素句柄
    :param out_name: 输出文件名
    :param pad: 四边留白
    """
    box = element.bounding_box()
    h = int(box["height"] + pad * 2)
    w = max(int(box["width"] + pad * 2), 300)
    page.set_viewport_size({"width": min(w + 20, 1800), "height": h})
    path = os.path.join(SHOT_DIR, out_name)
    element.screenshot(path=path)
    add_watermark(path)
    print(f"  [shot] {out_name}  {box['width']:.0f}x{box['height']:.0f}")


def shot_code(page, src_path, prefix, max_lines=CODE_MAX_LINES):
    """把源码切成若干段，每段生成一张代码截图。

    :param page: Playwright Page
    :param src_path: 源文件路径
    :param prefix: 输出文件名前缀
    :param max_lines: 每张最多多少行
    :return: 生成的文件名列表
    """
    with open(src_path, "r", encoding="utf-8") as fp:
        lines = fp.read().split("\n")
    # 去掉尾部空行
    while lines and not lines[-1].strip():
        lines.pop()

    made = []
    for idx, start in enumerate(range(0, len(lines), max_lines), start=1):
        chunk = lines[start:start + max_lines]
        src = "\n".join(chunk)
        # 用 linenos="inline" 让每行自带行号；注意不能同时用 nowrap，
        # 否则 Pygments 会忽略行号设置
        body = highlight(
            src,
            PythonLexer(),
            HtmlFormatter(style="monokai", linenos="inline", linenostart=start + 1),
        )
        doc = f"<html><head><meta charset='utf-8'><style>{BASE_CSS}</style></head>" \
              f"<body>{body}</body></html>"
        page.set_content(doc)
        el = page.query_selector(".highlight")
        name = f"{prefix}_{idx:02d}.png"
        shoot(page, el, name)
        made.append(name)
    return made


def shot_terminal(page, text, title, out_name, max_line=400):
    """渲染一段终端输出并截图。

    :param page: Playwright Page
    :param text: 终端文本
    :param title: 窗口标题
    :param out_name: 输出文件名
    :param max_line: 单行最大字符数，超出截断
    """
    safe = []
    for line in text.split("\n"):
        line = line.rstrip()
        if len(line) > max_line:
            line = line[:max_line] + " ..."
        safe.append(html.escape(line))
    body = "\n".join(safe)
    doc = f"""<html><head><meta charset='utf-8'><style>{TERM_CSS}</style></head><body>
    <div class='term'>
      <div class='bar'><span class='dot d1'></span><span class='dot d2'></span>
      <span class='dot d3'></span><span class='title'>{html.escape(title)}</span></div>
      <pre class='body'>{body}</pre>
    </div></body></html>"""
    page.set_content(doc)
    el = page.query_selector(".term")
    shoot(page, el, out_name)


def shot_table(page, headers, rows, out_name, title=""):
    """把二维数据渲染成表格截图。

    :param page: Playwright Page
    :param headers: 表头列表
    :param rows: 数据行
    :param out_name: 输出文件名
    :param title: 表格上方标题
    """
    th = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    trs = []
    for row in rows:
        tds = "".join(
            f"<td>{html.escape('' if v is None else str(v))}</td>" for v in row
        )
        trs.append(f"<tr>{tds}</tr>")
    doc = f"""<html><head><meta charset='utf-8'><style>
    body{{margin:0;background:#fff;font-family:"Microsoft YaHei",sans-serif;}}
    .wrap{{display:inline-block;padding:14px;}}
    .cap{{font-size:13px;color:#333;margin-bottom:8px;font-weight:600;}}
    table{{border-collapse:collapse;font-size:12px;}}
    th{{background:#2c5f8a;color:#fff;padding:6px 10px;border:1px solid #b8cfe0;
        white-space:nowrap;}}
    td{{padding:5px 10px;border:1px solid #d6e0e8;color:#222;white-space:nowrap;}}
    tr:nth-child(even) td{{background:#f4f8fb;}}
    </style></head><body><div class='wrap'>
    <div class='cap'>{html.escape(title)}</div>
    <table><thead><tr>{th}</tr></thead><tbody>{''.join(trs)}</tbody></table>
    </div></body></html>"""
    page.set_content(doc)
    el = page.query_selector(".wrap")
    shoot(page, el, out_name)


def shot_imagewall(page, out_name, limit=36, cols=6, cell=150):
    """把下载的图片拼成图片墙。

    :param page: Playwright Page
    :param out_name: 输出文件名
    :param limit: 最多取多少张
    :param cols: 每行张数
    :param cell: 单格边长（像素）
    """
    files = sorted(f for f in os.listdir(IMG_DIR) if f.lower().endswith((".jpg", ".png")))
    files = files[:limit]
    cells = []
    for fn in files:
        path = os.path.join(IMG_DIR, fn)
        img = Image.open(path).convert("RGB")
        img.thumbnail((cell, cell))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        b64 = base64.b64encode(buf.getvalue()).decode()
        cells.append(
            f"<div class='cell'><img src='data:image/jpeg;base64,{b64}'/>"
            f"<span>{fn[:14]}</span></div>"
        )
    doc = f"""<html><head><meta charset='utf-8'><style>
    body{{margin:0;background:#fff;font-family:"Microsoft YaHei",sans-serif;}}
    .wall{{display:grid;grid-template-columns:repeat({cols},{cell}px);gap:10px;
           padding:14px;width:max-content;}}
    .cell{{text-align:center;}}
    .cell img{{width:{cell}px;height:{cell}px;object-fit:contain;
               border:1px solid #e0e6ec;border-radius:4px;background:#fafafa;}}
    .cell span{{display:block;font-size:10px;color:#666;margin-top:3px;
                overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
    </style></head><body><div class='wall'>{''.join(cells)}</div></body></html>"""
    page.set_content(doc)
    el = page.query_selector(".wall")
    shoot(page, el, out_name)


# ------------------------------------------------------------------ 主流程

def query(sql):
    """执行查询并返回 (表头, 数据行)。

    :param sql: SQL 语句
    :return: (表头列表, 行列表)
    """
    conn = pymysql.connect(host="127.0.0.1", port=3306, user="root",
                           password="123456", database="spider_db", charset="utf8mb4")
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    headers = [d[0] for d in cur.description]
    cur.close()
    conn.close()
    return headers, rows


def main():
    """依次生成所有截图。"""
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True,
                                    args=["--no-proxy-server"])
        page = browser.new_page(viewport={"width": VIEW_W, "height": 800})

        print("[1] 作业① 代码")
        shot_code(page, os.path.join(BASE, "code", "images", "dd_image_crawler.py"),
                  "code_hw1")

        print("[2] 作业② 代码")
        shot_code(page, os.path.join(BASE, "code", "stock", "fetch_stock_data.py"),
                  "code_hw2_fetch")
        shot_code(page, os.path.join(BASE, "code", "stock", "stock", "items.py"),
                  "code_hw2_items", max_lines=40)
        shot_code(page, os.path.join(BASE, "code", "stock", "stock", "pipelines.py"),
                  "code_hw2_pipe")
        shot_code(page, os.path.join(BASE, "code", "stock", "stock", "spiders",
                                     "stock_spider.py"),
                  "code_hw2_spider", max_lines=40)

        print("[3] 作业③ 代码")
        shot_code(page, os.path.join(BASE, "code", "forex", "forex", "items.py"),
                  "code_hw3_items", max_lines=40)
        shot_code(page, os.path.join(BASE, "code", "forex", "forex", "pipelines.py"),
                  "code_hw3_pipe")
        shot_code(page, os.path.join(BASE, "code", "forex", "forex", "spiders",
                                     "forex_spider.py"),
                  "code_hw3_spider", max_lines=40)

        print("[4] 终端输出")
        log1 = os.path.join(DATA_DIR, "images_run.log")
        if os.path.exists(log1):
            with open(log1, "r", encoding="utf-8", errors="ignore") as fp:
                text = fp.read()
            # 只保留关键行：列表统计 + 首尾若干条下载记录
            lines = [l for l in text.split("\n") if l.strip()]
            # 关键统计行：目标、约束、每页解析量、两个模式的汇总
            key_lines = [l for l in lines
                         if any(k in l for k in ("目标站点", "约束：", "[列表]",
                                                "单线程完成", "多线程完成"))]
            downloads = [l for l in lines if l.startswith("[下载]")]
            skipped = max(0, len(downloads) - 9)
            merged = (key_lines
                      + ["", f"  ... 省略中间 {skipped} 条（单线程与多线程各下载一遍）...", ""]
                      + downloads[:6]
                      + ["", "  ... 省略中间部分 ...", ""]
                      + downloads[-3:])
            shot_terminal(page, "\n".join(merged), "dd_image_crawler.py 运行结果",
                          "term_hw1.png")

        print("[5] 数据表")
        h, r = query("SELECT seq,stock_code,stock_name,latest_price,change_percent,"
                     "change_amount,volume,amplitude,high_price,low_price,open_price,"
                     "prev_close FROM stock_info ORDER BY seq LIMIT 18")
        shot_table(page, h, r, "db_stock.png", "MySQL: spider_db.stock_info（前 18 条）")

        h, r = query("SELECT currency,tbp,cbp,tsp,csp,boccp,quote_time FROM boc_forex "
                     "ORDER BY id LIMIT 20")
        shot_table(page, h, r, "db_forex.png", "MySQL: spider_db.boc_forex（前 20 条）")

        print("[6] 图片墙")
        shot_imagewall(page, "images_wall.png")

        browser.close()
    print("全部截图完成，输出目录：", SHOT_DIR)


if __name__ == "__main__":
    sys.exit(main())
