"""
Bilibili 首页视频爬虫脚本
=======================
功能：爬取 B 站首页热门视频的标题、作者、链接、播放量、弹幕数等信息。
原理：调用 B 站公开 API（无需登录），稳定高效。
依赖：Python 3.7+, requests

使用方法：
  1. 安装依赖：   pip install requests
  2. 运行脚本：   python bilibili_scraper.py
  3. 查看输出：   结果保存在 bilibili_videos.csv 中

进阶用法：
  python bilibili_scraper.py --count 50          # 爬取 50 条（默认 30）
  python bilibili_scraper.py --category 1         # 按分区爬取（1=动画, 3=音乐, 4=游戏...）
  python bilibili_scraper.py --json               # 输出为 JSON 格式
  python bilibili_scraper.py --region 1           # 按频道爬取（0=综合, 1=动画, 13=游戏...）
"""

import requests
import csv
import json
import argparse
import sys
from datetime import datetime
from typing import Optional

# ── 请求头，模拟浏览器避免被拦截 ──
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
}

# ── B 站 API 端点 ──
POPULAR_API = "https://api.bilibili.com/x/web-interface/popular"
DYNAMIC_API = "https://api.bilibili.com/x/web-interface/dynamic/region"


def fetch_popular_videos(count: int = 30, region: int = 0) -> list[dict]:
    """
    爬取 B 站首页热门视频。

    参数:
        count:  期望获取的视频数量（实际以 API 返回为准，通常 ≤50）
        region: 频道 ID
                - 0:  综合热门（默认）
                - 1:  动画 / 番剧
                - 3:  音乐
                - 4:  游戏
                - 5:  知识
                - 13: 游戏（备用）
                - 119: 鬼畜
                - 等等...

    返回:
        视频信息字典列表，每个字典包含:
        - title:        标题
        - author:       作者
        - bvid:         视频 BV 号
        - url:          视频链接
        - cover:        封面图链接
        - play_count:   播放量
        - danmaku_count:弹幕数
        - duration:     时长
        - pubdate:      发布时间
    """
    params = {
        "ps": min(count, 50),  # 每页最多 50
        "pn": 1,
    }
    if region:
        params["rid"] = region

    try:
        resp = requests.get(POPULAR_API, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[错误] 请求失败: {e}", file=sys.stderr)
        return []

    data = resp.json()

    # B 站 API 返回格式: {"code": 0, "message": "0", "data": {"list": [...]}}
    if data.get("code") != 0:
        print(f"[错误] API 返回异常: {data.get('message', '未知错误')}", file=sys.stderr)
        return []

    videos = data.get("data", {}).get("list", [])
    if not videos:
        # 尝试无 región 参数重试
        if region:
            print("[提示] 指定频道无数据，尝试获取综合热门...", file=sys.stderr)
            return fetch_popular_videos(count=count, region=0)
        print("[错误] API 未返回任何视频数据", file=sys.stderr)
        return []

    results = []
    for item in videos:
        bvid = item.get("bvid", "")
        results.append({
            "title":         item.get("title", ""),
            "author":        item.get("owner", {}).get("name", "未知"),
            "bvid":          bvid,
            "url":           f"https://www.bilibili.com/video/{bvid}" if bvid else "",
            "cover":         item.get("pic", ""),
            "play_count":    item.get("stat", {}).get("view", 0),
            "danmaku_count": item.get("stat", {}).get("danmaku", 0),
            "like_count":    item.get("stat", {}).get("like", 0),
            "coin_count":    item.get("stat", {}).get("coin", 0),
            "favorite_count": item.get("stat", {}).get("favorite", 0),
            "duration":      _format_duration(item.get("duration", 0)),
            "pubdate":       _ts_to_str(item.get("pubdate", 0)),
        })

    print(f"✓ 成功获取 {len(results)} 条视频信息")
    return results


def _format_duration(seconds: int) -> str:
    """将秒数格式化为 mm:ss 或 hh:mm:ss。"""
    if seconds <= 0:
        return "00:00"
    h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _ts_to_str(ts: int) -> str:
    """Unix 时间戳转可读字符串。"""
    if ts <= 0:
        return "未知"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _format_count(n: int) -> str:
    """大数字友好展示（万 / 亿）。"""
    if n >= 100_000_000:
        return f"{n / 100_000_000:.1f}亿"
    if n >= 10_000:
        return f"{n / 10_000:.1f}万"
    return str(n)


def save_csv(videos: list[dict], filename: str = "bilibili_videos.csv") -> None:
    """保存为 CSV 文件（UTF-8 BOM，Excel 可直接打开）。"""
    fieldnames = [
        "title", "author", "bvid", "url", "cover",
        "play_count", "danmaku_count", "like_count",
        "coin_count", "favorite_count", "duration", "pubdate",
    ]
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(videos)
    print(f"✓ 已保存到 {filename}")


def save_json(videos: list[dict], filename: str = "bilibili_videos.json") -> None:
    """保存为 JSON 文件。"""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(videos, f, ensure_ascii=False, indent=2)
    print(f"✓ 已保存到 {filename}")


def print_table(videos: list[dict]) -> None:
    """在终端打印视频信息表格。"""
    if not videos:
        print("没有数据可显示。")
        return

    # 计算列宽（中文字符占 2 个显示宽度）
    def _display_width(s: str) -> int:
        w = 0
        for ch in s:
            w += 2 if '一' <= ch <= '鿿' or '　' <= ch <= '〿' else 1
        return w

    # 缩短标题以适应终端
    MAX_TITLE = 30
    short_titles = []
    for v in videos:
        t = v["title"]
        if _display_width(t) > MAX_TITLE:
            # 按显示宽度截断
            w, i = 0, 0
            for i, ch in enumerate(t):
                w += 2 if '一' <= ch <= '鿿' else 1
                if w >= MAX_TITLE - 2:
                    break
            t = t[:i] + "…"
        short_titles.append(t)

    print(f"\n{'=' * 80}")
    print(f"  B 站首页热门视频  |  更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 80}")
    print(f"{'序号':<4} {'标题':<32} {'UP主':<16} {'播放量':>8} {'弹幕':>6} {'时长':>8}")
    print(f"{'-' * 80}")

    for i, (v, st) in enumerate(zip(videos, short_titles), 1):
        print(
            f"{i:<4} "
            f"{st:<32} "
            f"{v['author']:<16} "
            f"{_format_count(v['play_count']):>8} "
            f"{_format_count(v['danmaku_count']):>6} "
            f"{v['duration']:>8}"
        )

    print(f"{'-' * 80}")
    print(f"  共 {len(videos)} 条  |  数据来源: api.bilibili.com")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="B 站首页热门视频爬虫 —— 基于 B 站公开 API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python bilibili_scraper.py                     # 爬取 30 条综合热门
  python bilibili_scraper.py --count 50          # 爬取 50 条
  python bilibili_scraper.py --region 3          # 爬取音乐区热门
  python bilibili_scraper.py --json              # 保存 JSON 格式
  python bilibili_scraper.py --no-save           # 仅打印，不保存文件
  python bilibili_scraper.py -o my_videos.csv     # 指定输出文件名
        """,
    )
    parser.add_argument(
        "--count", "-c", type=int, default=30,
        help="抓取视频数量（默认 30，最大 50）",
    )
    parser.add_argument(
        "--region", "-r", type=int, default=0,
        help="频道/分区 ID（0=综合, 1=动画, 3=音乐, 4=游戏, 5=知识）",
    )
    parser.add_argument(
        "--output", "-o", type=str, default="",
        help="输出文件名（默认: bilibili_videos.csv）",
    )
    parser.add_argument(
        "--json", "-j", action="store_true",
        help="输出为 JSON 文件而非 CSV",
    )
    parser.add_argument(
        "--no-save", "-n", action="store_true",
        help="仅打印到终端，不保存文件",
    )

    args = parser.parse_args()

    print("正在获取 B 站首页热门视频...\n")

    videos = fetch_popular_videos(count=args.count, region=args.region)

    if not videos:
        print("未获取到任何视频，请检查网络连接后重试。", file=sys.stderr)
        sys.exit(1)

    # 打印表格
    print_table(videos)

    # 保存文件
    if not args.no_save:
        if args.json:
            filename = args.output or "bilibili_videos.json"
            save_json(videos, filename)
        else:
            filename = args.output or "bilibili_videos.csv"
            save_csv(videos, filename)

    # 打印几个示例链接
    print(f"\n热门视频链接（前 5 个）:")
    for v in videos[:5]:
        print(f"  • {v['title'][:40]}  →  {v['url']}")
    print()


if __name__ == "__main__":
    main()
