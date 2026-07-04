"""
collectors.py - 多平台采集器
数据源：抖音热榜 + Hacker News + Reddit + V2EX + 微博热搜 + 百度热搜 + Stack Overflow + Product Hunt
覆盖国内外主流社交平台和技术社区，全面收集用户痛点与需求
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


# 英文痛点短语 → 中文翻译映射
EN_TO_CN = {
    "frustrating": "令人沮丧", "annoying": "烦人", "slow": "太慢",
    "crash": "崩溃", "broken": "坏了", "hate": "讨厌",
    "difficult": "困难", "struggle": "挣扎", "tedious": "繁琐",
    "cumbersome": "笨重", "useless": "没用", "confusing": "混乱",
    "missing": "缺失", "lack": "缺乏", "unable to": "无法",
    "how to": "如何", "how do": "怎么做", "anyone know": "有人知道吗",
    "recommend": "推荐", "looking for": "寻找", "alternative": "替代方案",
    "wish": "希望", "need": "需要", "want": "想要", "should": "应该",
    "request": "请求", "suggest": "建议", "why is": "为什么",
    "why does": "为什么", "why can't": "为什么不能",
    "is there": "有没有", "is there a way": "有没有办法",
    "help with": "求助", "stuck on": "卡在", "can't figure out": "搞不懂",
    "waste of time": "浪费时间", "time consuming": "耗时",
    "workaround": "临时方案", "hack": "折腾",
}

# 英文 → 中文分类关键词映射
EN_CATEGORY_MAP = {
    "code": "computer", "programming": "computer", "developer": "computer",
    "software": "computer", "debug": "computer", "api": "computer",
    "app": "phone", "mobile": "phone", "android": "phone", "ios": "phone",
    "iphone": "phone",
    "website": "internet", "browser": "internet", "online": "internet",
    "internet": "internet", "web": "internet",
    "work": "work", "office": "work", "business": "work", "meeting": "work",
    "study": "study", "learn": "study", "course": "study", "school": "study",
    "life": "life", "daily": "life", "home": "life", "family": "life",
    "health": "life", "food": "life", "travel": "life",
}


def translate_en(text):
    """简单英译中：替换已知痛点短语"""
    if not text:
        return text
    result = text
    for en, cn in sorted(EN_TO_CN.items(), key=lambda x: -len(x[0])):
        result = result.replace(en, cn)
    return result


def categorize_en(text):
    """根据英文关键词推断分类"""
    text_lower = text.lower()
    for en_kw, cat in EN_CATEGORY_MAP.items():
        if en_kw in text_lower:
            return cat
    return "other"


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

        hot_posts = self._fetch_hotlist()
        all_posts.extend(hot_posts)

        for kw in self.SEARCH_KEYWORDS:
            try:
                search_posts = self._fetch_search(kw)
                all_posts.extend(search_posts)
                time.sleep(1)
            except Exception:
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
# Hacker News 采集器（Algolia API — 免费、可靠、全球可用）
# ============================================================

class HackerNewsCollector:
    """Hacker News — 技术社区热门帖子，Algolia 搜索 API"""

    SEARCH_API = "https://hn.algolia.com/api/v1/search"

    # 搜索痛点/需求相关的故事
    SEARCH_QUERIES = [
        "ask hn",      # Ask HN 帖子天然包含需求/求助
        "tell hn",     # Tell HN 帖子天然包含吐槽/痛点
    ]

    # 按热度获取
    FRONT_PAGE_API = "https://hn.algolia.com/api/v1/search?tags=front_page"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; PainPointBot/1.0)",
            "Accept": "application/json",
        }

    def fetch(self):
        all_posts = []

        # 1. 前页热帖
        try:
            resp = requests.get(self.FRONT_PAGE_API, headers=self.headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for hit in data.get("hits", []):
                    post = self._parse_hit(hit)
                    if post:
                        all_posts.append(post)
        except Exception:
            pass

        # 2. Ask HN / Tell HN 搜索
        for q in self.SEARCH_QUERIES:
            try:
                resp = requests.get(
                    self.SEARCH_API,
                    params={"query": q, "tags": "story", "hitsPerPage": 30},
                    headers=self.headers,
                    timeout=15
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for hit in data.get("hits", []):
                        post = self._parse_hit(hit)
                        if post:
                            all_posts.append(post)
                time.sleep(0.5)
            except Exception:
                continue

        seen = set()
        unique = []
        for p in all_posts:
            if p["post_id"] not in seen:
                seen.add(p["post_id"])
                unique.append(p)

        print(f"  [HackerNews] 采集 {len(unique)} 帖（英文，自动翻译）")
        return unique

    def _parse_hit(self, hit):
        title = hit.get("title", "") or hit.get("story_title", "")
        if not title:
            return None

        object_id = hit.get("objectID", str(hash(title)))
        points = hit.get("points", 0) or 0
        num_comments = hit.get("num_comments", 0) or 0
        url = hit.get("url", "") or f"https://news.ycombinator.com/item?id={object_id}"
        author = hit.get("author", "")
        created = hit.get("created_at", datetime.now().isoformat())

        # 翻译标题
        cn_title = translate_en(title)

        return {
            "platform": "hackernews",
            "post_id": f"hn_{object_id}",
            "title": truncate(cn_title if cn_title != title else title, MAX_TITLE_LENGTH),
            "content": truncate(f"{title}\n{translate_en(hit.get('story_text', '') or hit.get('comment_text', '') or '')}", MAX_CONTENT_LENGTH),
            "author": author,
            "url": url,
            "reply_count": num_comments,
            "posted_at": created,
        }


# ============================================================
# Reddit 采集器（JSON API — 免费、可靠）
# ============================================================

class RedditCollector:
    """Reddit — 多个子版块热门帖子，JSON API"""

    SUBREDDITS = [
        "AskReddit",       # 问答社区，大量需求/痛点
        "lifehacks",       # 生活技巧，天然痛点
        "YouShouldKnow",   # 你应该知道，需求类
        "productivity",    # 生产力工具
        "apps",            # APP推荐
        "software",        # 软件推荐
        "techsupport",     # 技术支持，天然痛点
        "mildlyinfuriating", # 轻微恼火，天然痛点
        "firstworldproblems", # 第一世界问题，天然痛点
    ]

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; PainPointBot/1.0; Research Project)",
            "Accept": "application/json",
        }

    def fetch(self):
        all_posts = []

        for sub in self.SUBREDDITS:
            try:
                url = f"https://www.reddit.com/r/{sub}/hot.json?limit=10"
                resp = requests.get(url, headers=self.headers, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    children = data.get("data", {}).get("children", [])
                    for child in children:
                        post = self._parse_post(child.get("data", {}), sub)
                        if post:
                            all_posts.append(post)
                time.sleep(1)
            except Exception:
                continue

        seen = set()
        unique = []
        for p in all_posts:
            if p["post_id"] not in seen:
                seen.add(p["post_id"])
                unique.append(p)

        print(f"  [Reddit] 采集 {len(unique)} 帖（{len(self.SUBREDDITS)}个子版块，英文，自动翻译）")
        return unique

    def _parse_post(self, data, subreddit):
        title = data.get("title", "")
        if not title or len(title) < 5:
            return None

        post_id = data.get("id", str(hash(title)))
        selftext = data.get("selftext", "")
        score = data.get("score", 0) or 0
        num_comments = data.get("num_comments", 0) or 0
        author = data.get("author", "")
        permalink = data.get("permalink", "")
        created_utc = data.get("created_utc", 0)

        # 翻译标题
        cn_title = translate_en(title)
        cn_text = translate_en(selftext[:500]) if selftext else ""

        # 构建内容
        content = f"[r/{subreddit}] {title}"
        if selftext:
            content += f"\n{cn_text}"

        return {
            "platform": "reddit",
            "post_id": f"rd_{post_id}",
            "title": truncate(cn_title if cn_title != title else title, MAX_TITLE_LENGTH),
            "content": truncate(content, MAX_CONTENT_LENGTH),
            "author": author,
            "url": f"https://www.reddit.com{permalink}" if permalink else f"https://www.reddit.com/r/{subreddit}",
            "reply_count": num_comments,
            "posted_at": datetime.utcfromtimestamp(created_utc).isoformat() if created_utc else datetime.now().isoformat(),
        }


# ============================================================
# V2EX 采集器（热门话题 API — 免费、可靠）
# ============================================================

class V2EXCollector:
    """V2EX — 中文技术社区热门话题"""

    HOT_API = "https://www.v2ex.com/api/topics/hot.json"
    LATEST_API = "https://www.v2ex.com/api/topics/latest.json"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        }

    def fetch(self):
        all_posts = []

        # 1. 热门话题
        try:
            resp = requests.get(self.HOT_API, headers=self.headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for topic in data:
                    post = self._parse_topic(topic)
                    if post:
                        all_posts.append(post)
        except Exception:
            pass

        time.sleep(1)

        # 2. 最新话题
        try:
            resp = requests.get(self.LATEST_API, headers=self.headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for topic in data:
                    post = self._parse_topic(topic)
                    if post:
                        all_posts.append(post)
        except Exception:
            pass

        seen = set()
        unique = []
        for p in all_posts:
            if p["post_id"] not in seen:
                seen.add(p["post_id"])
                unique.append(p)

        print(f"  [V2EX] 采集 {len(unique)} 帖")
        return unique

    def _parse_topic(self, topic):
        title = topic.get("title", "")
        if not title or len(title) < 3:
            return None

        topic_id = topic.get("id", str(hash(title)))
        content = topic.get("content", "")
        content_text = clean_html(content) if content else title
        member = topic.get("member", {})
        node = topic.get("node", {})

        return {
            "platform": "v2ex",
            "post_id": f"v2ex_{topic_id}",
            "title": truncate(title, MAX_TITLE_LENGTH),
            "content": truncate(content_text, MAX_CONTENT_LENGTH),
            "author": member.get("username", ""),
            "url": f"https://www.v2ex.com/t/{topic_id}",
            "reply_count": topic.get("replies", 0),
            "posted_at": datetime.now().isoformat(),
        }


# ============================================================
# 微博热搜采集器
# ============================================================

class WeiboCollector:
    """微博热搜 — 移动端 API"""

    HOT_API = "https://m.weibo.cn/api/container/getIndex"
    HOT_PARAMS = {
        "containerid": "106003type=25&t=3&disable_hot=1&filter_type=realtimehot",
    }

    def __init__(self):
        self.headers = {
            "User-Agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                           "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                           "Version/17.0 Mobile/15E148 Safari/604.1"),
            "Accept": "application/json",
            "Referer": "https://m.weibo.cn/",
        }

    def fetch(self):
        posts = []
        try:
            resp = requests.get(
                self.HOT_API,
                params=self.HOT_PARAMS,
                headers=self.headers,
                timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                cards = (data.get("data", {}).get("cards", []) or [])
                for card in cards:
                    card_group = card.get("card_group", [])
                    for item in card_group:
                        desc = item.get("desc", "") or item.get("desc_extr", "")
                        if not desc or len(desc) < 2:
                            continue
                        post_id = item.get("itemid", "") or item.get("id", str(hash(desc)))
                        posts.append({
                            "platform": "weibo",
                            "post_id": f"wb_{post_id}",
                            "title": truncate(desc, MAX_TITLE_LENGTH),
                            "content": desc,
                            "author": item.get("user", {}).get("screen_name", "微博热搜"),
                            "url": item.get("scheme", f"https://m.weibo.cn/search?containerid={quote(desc)}"),
                            "reply_count": item.get("comments_count", 0) or 0,
                            "posted_at": datetime.now().isoformat(),
                        })
        except Exception:
            pass

        print(f"  [微博] 采集 {len(posts)} 帖")
        return posts


# ============================================================
# 百度热搜采集器
# ============================================================

class BaiduHotCollector:
    """百度热搜 — 热搜榜 API"""

    HOT_API = "https://top.baidu.com/api/board"
    HOT_PARAMS = {"platform": "wise", "tab": "realtime"}

    def __init__(self):
        self.headers = {
            "User-Agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                           "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                           "Version/17.0 Mobile/15E148 Safari/604.1"),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://top.baidu.com/",
        }

    def fetch(self):
        posts = []
        try:
            resp = requests.get(
                self.HOT_API,
                params=self.HOT_PARAMS,
                headers=self.headers,
                timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                cards = (data.get("data", {}).get("cards", []) or [])
                for card in cards:
                    for item in card.get("content", []):
                        title = item.get("word", "") or item.get("query", "")
                        if not title or len(title) < 2:
                            continue
                        desc = item.get("desc", "") or title
                        hot_score = item.get("hotScore", 0) or 0
                        posts.append({
                            "platform": "baidu",
                            "post_id": f"bd_{hash(title) % 10000000}",
                            "title": truncate(title, MAX_TITLE_LENGTH),
                            "content": truncate(desc, MAX_CONTENT_LENGTH),
                            "author": "百度热搜",
                            "url": item.get("url", f"https://www.baidu.com/s?wd={quote(title)}"),
                            "reply_count": int(hot_score) if hot_score else 0,
                            "posted_at": datetime.now().isoformat(),
                        })
        except Exception:
            pass

        print(f"  [百度] 采集 {len(posts)} 帖")
        return posts


# ============================================================
# Stack Overflow 采集器（API — 免费、可靠）
# ============================================================

class StackOverflowCollector:
    """Stack Overflow — 热门问题，天然痛点"""

    API = "https://api.stackexchange.com/2.3/questions"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; PainPointBot/1.0)",
            "Accept": "application/json",
        }

    def fetch(self):
        posts = []
        try:
            resp = requests.get(
                self.API,
                params={
                    "order": "desc",
                    "sort": "hot",
                    "site": "stackoverflow",
                    "pagesize": 30,
                    "filter": "withbody",
                },
                headers=self.headers,
                timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("items", []):
                    title = item.get("title", "")
                    if not title:
                        continue
                    q_id = item.get("question_id", str(hash(title)))
                    body = clean_html(item.get("body", ""))
                    tags = item.get("tags", [])

                    # 翻译标题
                    cn_title = translate_en(title)

                    content = f"[SO] {title}"
                    if tags:
                        content += f"\nTags: {', '.join(tags)}"
                    if body:
                        content += f"\n{translate_en(body[:300])}"

                    posts.append({
                        "platform": "stackoverflow",
                        "post_id": f"so_{q_id}",
                        "title": truncate(cn_title if cn_title != title else title, MAX_TITLE_LENGTH),
                        "content": truncate(content, MAX_CONTENT_LENGTH),
                        "author": item.get("owner", {}).get("display_name", ""),
                        "url": item.get("link", f"https://stackoverflow.com/questions/{q_id}"),
                        "reply_count": item.get("answer_count", 0),
                        "posted_at": datetime.now().isoformat(),
                    })
        except Exception:
            pass

        print(f"  [StackOverflow] 采集 {len(posts)} 帖（英文，自动翻译）")
        return posts


# ============================================================
# Product Hunt 采集器（RSS — 免费）
# ============================================================

class ProductHuntCollector:
    """Product Hunt — 产品发布，天然需求信号"""

    RSS_URL = "https://www.producthunt.com/feed"
    ALTERNATIVE_API = "https://www.producthunt.com/frontend/graphql"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; PainPointBot/1.0)",
            "Accept": "application/xml, application/rss+xml, text/xml",
        }

    def fetch(self):
        posts = []
        try:
            resp = requests.get(self.RSS_URL, headers=self.headers, timeout=15)
            if resp.status_code == 200:
                text = resp.text
                # 解析 RSS XML
                items = re.findall(r'<item>(.*?)</item>', text, re.DOTALL)
                for item_text in items:
                    title_m = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>', item_text)
                    link_m = re.search(r'<link>(.*?)</link>', item_text)
                    desc_m = re.search(r'<description><!\[CDATA\[(.*?)\]\]></description>|<description>(.*?)</description>', item_text)

                    title = (title_m.group(1) or title_m.group(2)) if title_m else ""
                    if not title or len(title) < 3:
                        continue

                    link = link_m.group(1) if link_m else ""
                    desc = ""
                    if desc_m:
                        desc = desc_m.group(1) or desc_m.group(2) or ""
                        desc = clean_html(desc)

                    cn_title = translate_en(title)

                    posts.append({
                        "platform": "producthunt",
                        "post_id": f"ph_{hash(title) % 10000000}",
                        "title": truncate(cn_title if cn_title != title else title, MAX_TITLE_LENGTH),
                        "content": truncate(desc or title, MAX_CONTENT_LENGTH),
                        "author": "Product Hunt",
                        "url": link,
                        "reply_count": 0,
                        "posted_at": datetime.now().isoformat(),
                    })
        except Exception:
            pass

        print(f"  [ProductHunt] 采集 {len(posts)} 帖（英文，自动翻译）")
        return posts


# ============================================================
# WorkBuddy 补充数据注入器（读取AI搜索补充结果）
# ============================================================

class WorkBuddySupplementCollector:
    """读取 WorkBuddy 自动化任务产生的补充搜索结果 JSON"""

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
        ("hackernews", HackerNewsCollector),
        ("reddit", RedditCollector),
        ("v2ex", V2EXCollector),
        ("weibo", WeiboCollector),
        ("baidu", BaiduHotCollector),
        ("stackoverflow", StackOverflowCollector),
        ("producthunt", ProductHuntCollector),
        ("workbuddy", WorkBuddySupplementCollector),
    ]

    for name, collector_cls in collectors:
        try:
            print(f"\n>>> 开始采集 {name}...", flush=True)
            collector = collector_cls()
            posts = collector.fetch()
            results[name] = {"status": "ok", "count": len(posts), "error": None}
            all_posts.extend(posts)
        except Exception as e:
            print(f"  [{name}] 采集失败: {e}", flush=True)
            results[name] = {"status": "error", "count": 0, "error": str(e)}
            continue

    print(f"\n=== 总计采集 {len(all_posts)} 条帖子（来自 {len(results)} 个平台）===", flush=True)
    return all_posts, results
