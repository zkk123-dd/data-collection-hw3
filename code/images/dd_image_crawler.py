# -*- coding: utf-8 -*-
"""第三次作业 作业①：图片爬虫（单线程 / 多线程两种实现）。

目标站点：当当网搜索结果页（https://search.dangdang.com/）
爬取思路：
    1. 按 page_index 逐页抓列表页，解析出每件商品的图片地址；
    2. 把 200px 的中图地址（-1_b_）换成原图地址（-1_u_）；
    3. 地址去重后截断到学号规定的图片上限；
    4. 分别用单线程和多线程把图片下载到 images/ 目录，并统计耗时。

学号 102402148：
    总页数上限   = 学号后 2 位  -> 48 页
    图片数量上限 = 学号后 3 位  -> 148 张

用法：
    python dd_image_crawler.py --mode single
    python dd_image_crawler.py --mode multi --threads 10
"""

import argparse
import os
import queue
import re
import threading
import time
from urllib.parse import quote

import requests

# ---------------------------------------------------------------- 全局配置

# 学号推导出的两个约束值，改学号只需改这里
STU_ID = "102402148"
MAX_PAGES = int(STU_ID[-2:])          # 48 页
MAX_IMAGES = int(STU_ID[-3:])         # 148 张

KEYWORD = "书包"
BASE_URL = "https://search.dangdang.com/"

# 图片保存目录（相对本文件所在目录，避免受启动位置影响）
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")

# 请求头，带上 UA 与来源，避免服务端直接拒绝
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.dangdang.com/",
}

# 商品图地址：src 或 data-original 都兼容，单双引号都收
IMG_PATTERN = re.compile(r"""(?:src|data-original)=['"](//img[^'"]*?-1_b_[^'"]+\.jpg)['"]""")

# 列表页请求超时（秒）
PAGE_TIMEOUT = 20
# 图片请求超时（秒）
IMG_TIMEOUT = 30


# ---------------------------------------------------------------- 抓取列表页

def build_page_url(page_index):
    """拼出第 page_index 页的搜索地址。

    :param page_index: 页码，从 1 开始
    :return: 完整 URL
    """
    return f"{BASE_URL}?key={quote(KEYWORD)}&act=input&page_index={page_index}"


def fetch_html(url, retry=3):
    """抓取一个页面并返回 HTML 文本。

    当当搜索页是 GBK 编码，直接按 GBK 解码，避免中文变乱码。

    :param url: 页面地址
    :param retry: 失败重试次数
    :return: HTML 字符串，全部失败返回空串
    """
    for attempt in range(1, retry + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=PAGE_TIMEOUT)
            resp.encoding = "gbk"
            return resp.text
        except requests.RequestException as exc:
            print(f"[警告] 第 {attempt} 次抓取失败：{url} -> {exc}")
            time.sleep(1)
    return ""


def parse_image_urls(html):
    """从列表页 HTML 中提取商品图地址。

    :param html: 列表页文本
    :return: 图片地址列表（已转为 https 绝对地址与原图尺寸）
    """
    urls = []
    for raw in IMG_PATTERN.findall(html):
        # 页面里是 //img3m9.ddimg.cn/... 这种缺协议的地址
        full = "https:" + raw
        # -1_b_ 是 200px 中图，-1_u_ 是原图，替换后清晰度更高
        urls.append(full.replace("-1_b_", "-1_u_"))
    return urls


def collect_image_urls(max_pages=MAX_PAGES, limit=MAX_IMAGES):
    """翻页收集图片地址，去重后截断到上限。

    :param max_pages: 最多翻多少页
    :param limit: 最多收集多少个图片地址
    :return: (图片地址列表, 实际翻页数)
    """
    seen = set()
    result = []
    pages_done = 0

    for page_index in range(1, max_pages + 1):
        if len(result) >= limit:
            break
        url = build_page_url(page_index)
        html = fetch_html(url)
        if not html:
            print(f"[警告] 第 {page_index} 页为空，跳过")
            continue

        pages_done += 1
        page_urls = parse_image_urls(html)
        added = 0
        for img_url in page_urls:
            if img_url in seen:
                continue
            seen.add(img_url)
            result.append(img_url)
            added += 1
            if len(result) >= limit:
                break
        print(f"[列表] 第 {page_index:>2} 页：本页解析 {len(page_urls)} 张，新增 {added} 张，累计 {len(result)} 张")

    return result[:limit], pages_done


# ---------------------------------------------------------------- 下载图片

def make_filename(index, img_url):
    """根据序号与地址生成保存文件名。

    优先用当当的商品编号（形如 1508098919），便于追溯来源。

    :param index: 序号，从 1 开始
    :param img_url: 图片地址
    :return: 文件名
    """
    match = re.search(r"/(\d+)-1_u_", img_url)
    goods_id = match.group(1) if match else str(index)
    return f"{index:03d}_{goods_id}.jpg"


def save_image(index, img_url, lock=None):
    """下载一张图片并写入 images 目录。

    :param index: 序号，用于命名与保序
    :param img_url: 图片地址
    :param lock: 多线程时传入的锁，用于串行化打印
    :return: (序号, 地址, 文件名, 字节数, 是否成功)
    """
    filename = make_filename(index, img_url)
    path = os.path.join(IMG_DIR, filename)
    try:
        resp = requests.get(img_url, headers=HEADERS, timeout=IMG_TIMEOUT)
        if resp.status_code != 200 or not resp.content:
            raise ValueError(f"HTTP {resp.status_code}")
        with open(path, "wb") as fp:
            fp.write(resp.content)
        if lock:
            with lock:
                print(f"[下载] {filename:<22} {len(resp.content):>8} 字节  {img_url}")
        else:
            print(f"[下载] {filename:<22} {len(resp.content):>8} 字节  {img_url}")
        return index, img_url, filename, len(resp.content), True
    except Exception as exc:
        if lock:
            with lock:
                print(f"[失败] {filename:<22} {exc}  {img_url}")
        else:
            print(f"[失败] {filename:<22} {exc}  {img_url}")
        return index, img_url, filename, 0, False


def download_single(urls):
    """单线程：按顺序一张张下载。

    :param urls: 图片地址列表
    :return: (成功数, 总字节数, 耗时秒)
    """
    start = time.perf_counter()
    ok_count = 0
    total_bytes = 0
    for i, url in enumerate(urls, start=1):
        _, _, _, size, ok = save_image(i, url)
        if ok:
            ok_count += 1
            total_bytes += size
    return ok_count, total_bytes, time.perf_counter() - start


def download_multi(urls, threads=10):
    """多线程：把任务放进队列，由多个线程并发消费。

    结果按下标写回列表，保证顺序与 URL 列表一致（不能用 append，否则乱序）。

    :param urls: 图片地址列表
    :param threads: 线程数
    :return: (成功数, 总字节数, 耗时秒)
    """
    task_queue = queue.Queue()
    for i, url in enumerate(urls, start=1):
        task_queue.put((i, url))

    lock = threading.Lock()
    results = {}

    def worker():
        """线程工作函数：不断取任务直到队列为空。"""
        while True:
            try:
                index, url = task_queue.get_nowait()
            except queue.Empty:
                return
            try:
                _, _, _, size, ok = save_image(index, url, lock)
                results[index] = (ok, size)
            finally:
                task_queue.task_done()

    start = time.perf_counter()
    workers = [threading.Thread(target=worker, name=f"downloader-{k}") for k in range(threads)]
    for t in workers:
        t.start()
    for t in workers:
        t.join()
    elapsed = time.perf_counter() - start

    ok_count = sum(1 for ok, _ in results.values() if ok)
    total_bytes = sum(size for ok, size in results.values() if ok)
    return ok_count, total_bytes, elapsed


# ---------------------------------------------------------------- 入口

def parse_args():
    """解析命令行参数。

    :return: argparse.Namespace
    """
    parser = argparse.ArgumentParser(description="当当商品图片爬虫：单线程 / 多线程")
    parser.add_argument("--mode", choices=["single", "multi", "both"], default="both",
                        help="single=仅单线程，multi=仅多线程，both=先单后多（默认）")
    parser.add_argument("--threads", type=int, default=10, help="多线程模式的线程数，默认 10")
    parser.add_argument("--pages", type=int, default=MAX_PAGES, help=f"最多翻页数，默认 {MAX_PAGES}")
    parser.add_argument("--limit", type=int, default=MAX_IMAGES, help=f"最多下载图片数，默认 {MAX_IMAGES}")
    return parser.parse_args()


def main():
    """主流程：收集地址 -> 按模式下载 -> 打印汇总。"""
    args = parse_args()
    os.makedirs(IMG_DIR, exist_ok=True)

    print("=" * 78)
    print(f"目标站点：当当网搜索页    关键词：{KEYWORD}")
    print(f"约束：总页数 ≤ {args.pages} 页，图片数 ≤ {args.limit} 张，保存目录：{IMG_DIR}")
    print("=" * 78)

    t0 = time.perf_counter()
    urls, pages_done = collect_image_urls(args.pages, args.limit)
    collect_cost = time.perf_counter() - t0
    print("-" * 78)
    print(f"[列表] 共翻 {pages_done} 页，得到 {len(urls)} 个不重复的图片地址，耗时 {collect_cost:.2f}s")
    print("-" * 78)

    if not urls:
        print("[结束] 没有拿到任何图片地址，请检查网络或页面结构是否变化")
        return

    if args.mode in ("single", "both"):
        print("\n>>> 单线程下载开始")
        ok, size, cost = download_single(urls)
        print(f"<<< 单线程完成：成功 {ok}/{len(urls)} 张，共 {size/1024/1024:.2f} MB，耗时 {cost:.2f}s")

    if args.mode in ("multi", "both"):
        print(f"\n>>> 多线程下载开始（{args.threads} 个线程）")
        ok, size, cost = download_multi(urls, args.threads)
        print(f"<<< 多线程完成：成功 {ok}/{len(urls)} 张，共 {size/1024/1024:.2f} MB，耗时 {cost:.2f}s")


if __name__ == "__main__":
    main()
