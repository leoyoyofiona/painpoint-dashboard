"""
collectors.py - 多平台采集器
数据源：抖音热榜（实时）+ WorkBuddy AI 补充搜索（自动化）
"""
import time
import re
import json
import os
import requests
import html
from datetime import datetime
from urllib.parse import quote

from config import (
    MAX_CONTENT_LENGTH, MAX_TITLE_LENGTH,
    DOUYIN_TIMEOUT,
)


def truncate(text, max_len):
    if not text:
        return ""
    text = str(text).strip()
    return text[:max_len] + "..." if len(text) > max_len else text


def clean_html(raw_html):
    if not raw_html:
        return ""
    clean = re.compile(r"<[^>]+>")
    text = clean.sub("", raw_html)
    text = html.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


# ============================================================
# 抖音采集器（热榜 + 搜索双路径）
# ============================================================

class DouyinCollector:
    """抖音采集器 — 热榜 + 搜索「求推荐」等关键词"""

    HOT_API = "https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/"
    SEARCH_API = "https://www.iesdouyin.com/web/api/v2/search/item/"

    SEARCH_KEYWORDS = [
        "求推荐 好用 工具",
        "怎么办 日常 生活",
        "有没有 方便 方法",
        "吐槽 难用",
        "想要 但是 没有",
    ]

    def __init__(self):
        self.headers = {
            "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/125.0.0.0 Safari/537.36"),
            "Accept": "application/json",
            "Referer": "https://www.douyin.com/",
        }

    def fetch(self):
        all_posts = []

        # 1. 热榜
        hot_posts = self._fetch_hotlist()
        all_posts.extend(hot_posts)

        # 2. 搜索（获取更多日常需求类内容）
        for kw in self.SEARCH_KEYWORDS:
            try:
                search_posts = self._fetch_search(kw)
                all_posts.extend(search_posts)
                time.sleep(2)
            except Exception as e:
                continue

        seen = set()
        unique = []
        for p in all_posts:
            if p["post_id"] not in seen:
                seen.add(p["post_id"])
                unique.append(p)

        print(f"  [抖音] 热榜{len(hot_posts)} + 搜索{len(all_posts)-len(hot_posts)} = {len(unique)} 帖")
        return unique

    def _fetch_hotlist(self):
        posts = []
        try:
            resp = requests.get(self.HOT_API, headers=self.headers, timeout=DOUYIN_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                word_list = (data.get("word_list", []) or
                             data.get("data", {}).get("word_list", []))
                for item in word_list:
                    title = item.get("word", "") or item.get("title", "")
                    if not title:
                        continue
                    hot = item.get("hot_value", 0) or item.get("hotValue", 0)
                    posts.append({
                        "platform": "douyin",
                        "post_id": f"dy_hot_{hash(title) % 10000000}",
                        "title": truncate(title, MAX_TITLE_LENGTH),
                        "content": title,
                        "author": "抖音热榜",
                        "url": f"https://www.douyin.com/search/{quote(title)}",
                        "reply_count": int(hot) if hot else 0,
                        "posted_at": datetime.now().isoformat(),
                    })
        except Exception:
            pass
        return posts

    def _fetch_search(self, keyword):
        posts = []
        try:
            resp = requests.get(
                self.SEARCH_API,
                params={"keyword": keyword, "count": 15},
                headers=self.headers,
                timeout=DOUYIN_TIMEOUT
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", []) if isinstance(data, dict) else []
                if isinstance(items, list):
                    for item in items:
                        aweme = item.get("aweme_info", {}) or item
                        desc = aweme.get("desc", "") or aweme.get("title", "")
                        if not desc or len(desc) < 3:
                            continue
                        aid = aweme.get("aweme_id", "") or aweme.get("id", "") or hash(desc)
                        posts.append({
                            "platform": "douyin",
                            "post_id": f"dy_srch_{aid}",
                            "title": truncate(desc, MAX_TITLE_LENGTH),
                            "content": desc,
                            "author": aweme.get("author", {}).get("nickname", ""),
                            "url": f"https://www.douyin.com/video/{aid}",
                            "reply_count": aweme.get("statistics", {}).get("comment_count", 0),
                            "posted_at": datetime.now().isoformat(),
                        })
        except Exception:
            pass
        return posts


# ============================================================
# WorkBuddy 补充数据注入器（读取AI搜索补充结果）
# ============================================================

class WorkBuddySupplementCollector:
    """
    读取 WorkBuddy 自动化任务产生的补充搜索结果 JSON
    文件: wb_supplement.json（由自动化生成）
    """

    def __init__(self):
        self.supplement_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "wb_supplement.json"
        )

    def fetch(self):
        posts = []
        if os.path.exists(self.supplement_path):
            try:
                with open(self.supplement_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    if isinstance(item, dict) and item.get("title"):
                        platform = item.get("platform", "supplement")
                        posts.append({
                            "platform": platform,
                            "post_id": f"wb_{platform}_{hash(item['title']) % 10000000}",
                            "title": truncate(item["title"], MAX_TITLE_LENGTH),
                            "content": truncate(item.get("content", item["title"]), MAX_CONTENT_LENGTH),
                            "author": item.get("author", "WorkBuddy"),
                            "url": item.get("url", ""),
                            "reply_count": item.get("reply_count", 0),
                            "posted_at": item.get("posted_at", datetime.now().isoformat()),
                        })
                print(f"  [WorkBuddy] 读取 {len(posts)} 条补充数据")
            except Exception as e:
                print(f"  [WorkBuddy] 读取失败: {e}")
        else:
            print(f"  [WorkBuddy] 无补充数据（可运行自动化生成）")
        return posts


# ============================================================
# 统一采集入口
# ============================================================

def collect_all():
    import sys
    all_posts = []
    results = {}

    collectors = [
        ("douyin", DouyinCollector),
        ("workbuddy", WorkBuddySupplementCollector),
    ]

    for name, collector_cls in collectors:
        try:
            print(f"\n>>> 开始采集 {name}...")
            sys.stdout.flush()
            collector = collector_cls()
            posts = collector.fetch()
            results[name] = {"status": "ok", "count": len(posts), "error": None}
            all_posts.extend(posts)
        except Exception as e:
            print(f"  [{name}] 采集失败: {e}", flush=True)
            results[name] = {"status": "error", "count": 0, "error": str(e)}
            continue

    print(f"\n=== 总计采集 {len(all_posts)} 条帖子 ===", flush=True)
    return all_posts, results
