"""
collectors.py - 多平台采集器
主力：V2EX深度挖掘50+生活节点 + Reddit生活效率类子版块
"""
import time
import re
import requests
import xml.etree.ElementTree as ET

from config import (
    V2EX_ENDPOINTS, V2EX_INTERVAL, V2EX_TIMEOUT, V2EX_RELEVANT_NODES,
    REDDIT_SUBREDDITS, REDDIT_INTERVAL, REDDIT_TIMEOUT,
    MAX_CONTENT_LENGTH, MAX_TITLE_LENGTH,
)


# ============================================================
# 通用工具
# ============================================================

def truncate(text, max_len):
    if not text:
        return ""
    text = str(text).strip()
    return text[:max_len] + "..." if len(text) > max_len else text


def clean_html(raw_html):
    if not raw_html:
        return ""
    clean = re.compile(r"<[^>]+>")
    return clean.sub("", raw_html).strip()


def request_with_retry(url, method="GET", params=None, headers=None,
                       timeout=15, retries=3, interval=2):
    for attempt in range(retries):
        try:
            if method == "GET":
                resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            else:
                resp = requests.post(url, json=params, headers=headers, timeout=timeout)

            if resp.status_code == 429:
                wait = interval * (2 ** attempt)
                time.sleep(wait)
                continue

            resp.raise_for_status()
            return resp

        except (requests.RequestException, requests.Timeout) as e:
            if attempt < retries - 1:
                time.sleep(interval * (2 ** attempt))
            else:
                raise

    return None


# ============================================================
# V2EX 采集器（深度挖掘50+生活节点）
# ============================================================

class V2EXCollector:
    """V2EX API 采集器 — 只取生活/问答/创意/分享节点"""

    def __init__(self):
        self.headers = {"User-Agent": "PainPointCollector/1.0"}

    def fetch(self):
        posts = []
        for endpoint in V2EX_ENDPOINTS:
            try:
                resp = request_with_retry(
                    endpoint, headers=self.headers,
                    timeout=V2EX_TIMEOUT, interval=V2EX_INTERVAL
                )
                if resp:
                    data = resp.json()
                    for item in data:
                        post = self._parse_item(item)
                        if post:
                            posts.append(post)
                time.sleep(V2EX_INTERVAL)
            except Exception as e:
                print(f"  [V2EX] 采集 {endpoint} 失败: {e}")
                continue

        seen = set()
        unique = []
        for p in posts:
            key = p["post_id"]
            if key not in seen:
                seen.add(key)
                unique.append(p)

        print(f"  [V2EX] 采集到 {len(unique)} 条帖子")
        return unique

    def _parse_item(self, item):
        node_name = item.get("node", {}).get("name", "")
        if V2EX_RELEVANT_NODES and node_name.lower() not in V2EX_RELEVANT_NODES:
            return None

        title = truncate(item.get("title", ""), MAX_TITLE_LENGTH)
        content = truncate(
            clean_html(item.get("content_rendered", "") or
                       item.get("content", "")),
            MAX_CONTENT_LENGTH
        )

        return {
            "platform": "v2ex",
            "post_id": item.get("id"),
            "title": title,
            "content": content,
            "author": item.get("member", {}).get("username", ""),
            "url": f"https://www.v2ex.com/t/{item.get('id')}",
            "reply_count": item.get("replies", 0),
            "posted_at": self._parse_time(item.get("created")),
        }

    def _parse_time(self, timestamp):
        if not timestamp:
            return None
        try:
            from datetime import datetime
            return datetime.fromtimestamp(timestamp).isoformat()
        except Exception:
            return None


# ============================================================
# Reddit RSS 采集器（仅 lifehacks/productivity）
# ============================================================

class RedditCollector:
    """Reddit RSS 采集器"""

    def __init__(self):
        self.headers = {"User-Agent": "PainPointCollector/1.0"}

    def fetch(self):
        posts = []
        for subreddit in REDDIT_SUBREDDITS:
            try:
                url = f"https://www.reddit.com/r/{subreddit}/hot.rss"
                resp = request_with_retry(
                    url, headers=self.headers,
                    timeout=REDDIT_TIMEOUT, interval=REDDIT_INTERVAL
                )
                if resp:
                    items = self._parse_rss(resp.text, subreddit)
                    posts.extend(items)
                time.sleep(REDDIT_INTERVAL)
            except Exception as e:
                print(f"  [Reddit] r/{subreddit} 采集失败: {e}")
                continue

        seen = set()
        unique = []
        for p in posts:
            key = p["post_id"]
            if key not in seen:
                seen.add(key)
                unique.append(p)

        print(f"  [Reddit] 采集到 {len(unique)} 条帖子")
        return unique

    def _parse_rss(self, xml_text, subreddit):
        posts = []
        try:
            root = ET.fromstring(xml_text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", ns)
            if not entries:
                entries = root.findall("{http://www.w3.org/2005/Atom}entry")

            for entry in entries:
                post = self._parse_entry(entry, ns, subreddit)
                if post:
                    posts.append(post)
        except ET.ParseError as e:
            print(f"  [Reddit] RSS解析失败: {e}")
        return posts

    def _parse_entry(self, entry, ns, subreddit):
        try:
            title_elem = entry.find("atom:title", ns)
            if title_elem is None:
                title_elem = entry.find("{http://www.w3.org/2005/Atom}title")
            title = truncate(title_elem.text if title_elem is not None else "", MAX_TITLE_LENGTH)

            link_elem = entry.find("atom:link", ns)
            if link_elem is None:
                link_elem = entry.find("{http://www.w3.org/2005/Atom}link")
            url = link_elem.get("href") if link_elem is not None else ""

            content_elem = entry.find("atom:content", ns)
            if content_elem is None:
                content_elem = entry.find("{http://www.w3.org/2005/Atom}content")
            content_raw = content_elem.text if content_elem is not None else ""
            content = truncate(clean_html(content_raw), MAX_CONTENT_LENGTH)

            updated_elem = entry.find("atom:updated", ns)
            if updated_elem is None:
                updated_elem = entry.find("{http://www.w3.org/2005/Atom}updated")
            posted_at = updated_elem.text if updated_elem is not None else None

            post_id = url.rstrip("/").split("/")[-1] if url else ""

            return {
                "platform": "reddit",
                "post_id": f"{subreddit}_{post_id}",
                "title": title,
                "content": content,
                "author": f"r/{subreddit}",
                "url": url,
                "reply_count": 0,
                "posted_at": posted_at,
            }
        except Exception as e:
            return None


# ============================================================
# 统一采集入口
# ============================================================

def collect_all():
    """采集所有平台"""
    all_posts = []
    results = {}

    collectors = [
        ("v2ex", V2EXCollector),
        ("reddit", RedditCollector),
    ]

    for name, collector_cls in collectors:
        try:
            print(f"\n>>> 开始采集 {name}...")
            collector = collector_cls()
            posts = collector.fetch()
            results[name] = {"status": "ok", "count": len(posts), "error": None}
            all_posts.extend(posts)
        except Exception as e:
            print(f"  [{name}] 采集失败: {e}")
            results[name] = {"status": "error", "count": 0, "error": str(e)}
            continue

    print(f"\n=== 总计采集 {len(all_posts)} 条帖子 ===")
    return all_posts, results
