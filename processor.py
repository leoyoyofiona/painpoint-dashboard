"""
processor.py - NLP 处理管道
jieba预筛 -> 自动痛点提取 -> Jaccard聚类 -> 排序
痛点提取为内置关键词引擎，无需外部 AI 步骤
"""

import re
import json
import math
from datetime import datetime, timedelta

import jieba
import jieba.analyse

from config import (
    PAIN_KEYWORDS, NEED_KEYWORDS, TOOL_KEYWORDS,
    EN_PAIN, EN_NEED, EN_TOOL,
    EXCLUDE_KEYWORDS, EN_EXCLUDE,
    CLUSTER_THRESHOLD,
    WEIGHT_FREQUENCY, WEIGHT_RECENCY, WEIGHT_FEASIBILITY,
    RECENCY_HALFLIFE_DAYS,
    TREND_NEW_DAYS, TREND_INCREASE_RATIO, TREND_DECREASE_RATIO,
)
from database import (
    insert_pain_point, get_all_clusters, create_cluster, add_to_cluster,
    update_cluster_trend, get_cluster_member_count_since,
    get_cluster_feasibility_avg,
)

_jieba_initialized = False


def _ensure_jieba():
    global _jieba_initialized
    if not _jieba_initialized:
        jieba.initialize()
        _jieba_initialized = True


# ============================================================
# 分类映射 — 关键词到分类
# ============================================================

CATEGORY_KEYWORDS = {
    "work": ["工作", "办公", "职场", "会议", "汇报", "效率", "管理", "流程",
             "work", "office", "business", "meeting", "manage"],
    "study": ["学习", "考试", "背单词", "做题", "题库", "刷题", "错题",
              "考研", "考公", "课程", "笔记", "复习",
              "study", "learn", "course", "school", "exam"],
    "life": ["生活", "日常", "家务", "做饭", "菜谱", "记账", "预算",
             "购物", "快递", "旅游", "出行", "租房", "买房", "装修",
             "搬家", "相亲", "情感", "健身", "减肥", "睡眠", "饮食",
             "体检", "看病", "养生", "护肤", "育儿", "孩子",
              "life", "daily", "home", "family", "health", "food", "travel"],
    "computer": ["电脑", "文档", "表格", "PPT", "PDF", "Word", "Excel",
                 "格式转换", "批量处理", "文件", "文件夹", "重命名",
                 "压缩", "解压", "备份", "截图", "录屏",
                 "code", "programming", "software", "debug", "开发",
                 "programming", "compiler"],
    "phone": ["手机", "APP", "小程序", "安卓", "iOS", "iPhone",
              "app", "mobile", "android", "iphone"],
    "internet": ["网页", "浏览器", "下载", "搜索", "网盘", "云盘",
                 "插件", "扩展", "脚本", "翻译", "OCR",
                 "website", "browser", "online", "internet", "web"],
    "other": [],
}


def _categorize(text):
    """根据文本关键词自动分类"""
    text_lower = text.lower()
    best_cat = "other"
    best_score = 0

    for cat, keywords in CATEGORY_KEYWORDS.items():
        if cat == "other":
            continue
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > best_score:
            best_score = score
            best_cat = cat

    return best_cat


def _extract_keywords(text, topk=8):
    """使用 jieba 提取关键词"""
    _ensure_jieba()
    tags = jieba.analyse.extract_tags(text, topK=topk, withWeight=False)
    return tags


def _detect_pain_signal(text):
    """
    检测文本中的痛点/需求信号
    返回: (has_signal, signal_type, signal_words)
    signal_type: 'pain', 'need', 'both', None
    """
    _ensure_jieba()
    text_lower = text.lower()

    # 英文信号检测
    en_pain_hits = [kw for kw in EN_PAIN if kw in text_lower]
    en_need_hits = [kw for kw in EN_NEED if kw in text_lower]

    # 中文信号检测（jieba分词后匹配）
    words = set(jieba.cut(text))
    cn_pain_hits = list(PAIN_KEYWORDS & words)
    cn_need_hits = list(NEED_KEYWORDS & words)

    all_pain = cn_pain_hits + en_pain_hits
    all_need = cn_need_hits + en_need_hits

    has_pain = len(all_pain) > 0
    has_need = len(all_need) > 0

    if has_pain and has_need:
        return True, "both", all_pain + all_need
    elif has_pain:
        return True, "pain", all_pain
    elif has_need:
        return True, "need", all_need
    else:
        return False, None, []


# ============================================================
# Step 1: jieba 预筛（放宽条件 — 只要含痛点或需求信号即可）
# ============================================================

def should_process(title, content):
    """
    判断帖子是否值得处理
    放宽条件：只要包含 痛点词 OR 需求词 即可通过（不再强制要求工具词）
    """
    _ensure_jieba()
    text = f"{title} {content}".lower()

    # 排除专业领域
    cn_exclude = bool(EXCLUDE_KEYWORDS & set(jieba.cut(text)))
    en_exclude = any(kw in text for kw in EN_EXCLUDE)
    if cn_exclude or en_exclude:
        return False

    # 检测痛点/需求信号
    has_signal, _, _ = _detect_pain_signal(text)
    return has_signal


# ============================================================
# Step 2: 自动痛点提取引擎（核心！）
# ============================================================

def extract_pain_points_auto(conn, verbose=False):
    """
    自动痛点提取引擎 — 从所有未处理帖子中提取痛点
    不依赖外部 AI，使用 jieba 关键词分析 + 规则引擎

    流程:
    1. 获取所有未处理帖子
    2. 对每条帖子进行痛点信号检测
    3. 提取痛点描述、关键词、分类、可行性评分
    4. 聚类入库
    5. 标记帖子已处理

    返回: 提取的痛点总数
    """
    from database import get_unprocessed_posts, mark_post_processed

    _ensure_jieba()

    unprocessed = get_unprocessed_posts(conn, limit=500)
    if verbose:
        print(f"  待处理帖子: {len(unprocessed)} 帖")

    if not unprocessed:
        return 0

    all_extracted = []
    processed_count = 0
    skipped_count = 0

    for post in unprocessed:
        post_id = post["id"]
        title = post.get("title", "") or ""
        content = post.get("content", "") or ""
        platform = post.get("platform", "")
        full_text = f"{title} {content}"

        if len(full_text.strip()) < 5:
            mark_post_processed(conn, post_id)
            skipped_count += 1
            continue

        # 检测痛点信号
        has_signal, signal_type, signal_words = _detect_pain_signal(full_text)

        if not has_signal:
            # 无信号 — 尝试更宽松的匹配：标题本身就是问题/需求
            # 热搜榜类内容（抖音/微博/百度）的标题通常是用户关注的热点
            if platform in ("douyin", "weibo", "baidu", "v2ex", "reddit", "hackernews"):
                # 对热搜类内容，提取关键词作为潜在需求
                keywords = _extract_keywords(full_text, topk=5)
                if keywords:
                    pain_desc = _generate_description(title, content, platform, signal_type=None)
                    category = _categorize(full_text)
                    feas = _estimate_feasibility(full_text, signal_words=[], platform=platform)
                    all_extracted.append({
                        "post_id": post_id,
                        "description": pain_desc,
                        "category": category,
                        "feasibility": feas,
                        "feasibility_reason": "热搜话题提取",
                        "keywords": ",".join(keywords),
                    })
                    processed_count += 1
                    mark_post_processed(conn, post_id)
                    continue
            mark_post_processed(conn, post_id)
            skipped_count += 1
            continue

        # 有信号 — 提取痛点
        keywords = _extract_keywords(full_text, topk=8)
        # 合并信号词到关键词中
        all_kw = list(set(keywords + signal_words[:4]))

        pain_desc = _generate_description(title, content, platform, signal_type)
        category = _categorize(full_text)
        feas = _estimate_feasibility(full_text, signal_words, platform)

        all_extracted.append({
            "post_id": post_id,
            "description": pain_desc,
            "category": category,
            "feasibility": feas,
            "feasibility_reason": f"信号类型: {signal_type}, 信号词: {','.join(signal_words[:3])}",
            "keywords": ",".join(all_kw),
        })
        processed_count += 1
        mark_post_processed(conn, post_id)

    if verbose:
        print(f"  信号检测: {processed_count} 帖有痛点/需求信号")
        print(f"  跳过: {skipped_count} 帖无信号")

    # 批量聚类入库
    if all_extracted:
        clustered = cluster_pain_points(conn, all_extracted)
        if verbose:
            print(f"  聚类入库: {clustered} 条痛点")
        return clustered

    return 0


def _generate_description(title, content, platform, signal_type):
    """
    根据帖子内容生成痛点描述
    """
    title = (title or "").strip()
    content = (content or "").strip()

    # 平台标签
    platform_labels = {
        "douyin": "[抖音]",
        "weibo": "[微博]",
        "baidu": "[百度]",
        "v2ex": "[V2EX]",
        "hackernews": "[HN]",
        "reddit": "[Reddit]",
        "stackoverflow": "[StackOverflow]",
        "producthunt": "[ProductHunt]",
    }
    prefix = platform_labels.get(platform, "")

    # 如果有信号类型，添加标注
    signal_label = ""
    if signal_type == "pain":
        signal_label = "【痛点】"
    elif signal_type == "need":
        signal_label = "【需求】"
    elif signal_type == "both":
        signal_label = "【痛点+需求】"

    # 生成描述
    if title and content and title != content:
        desc = f"{prefix}{signal_label}{title}"
        # 如果内容中有更多上下文，截取关键部分
        if len(content) > 20 and content != title:
            # 提取内容前100字作为补充
            content_brief = content[:100].replace("\n", " ").strip()
            if content_brief and content_brief != title:
                desc = f"{prefix}{signal_label}{title} — {content_brief}"
    else:
        desc = f"{prefix}{signal_label}{title}"

    return desc[:200] if len(desc) > 200 else desc


def _estimate_feasibility(text, signal_words, platform):
    """
    估算痛点可行性评分 (1-5)
    基于信号强度、内容长度、平台特性
    """
    score = 3  # 基础分

    # 信号词越多，可行性越高（说明痛点越明确）
    if len(signal_words) >= 3:
        score += 1
    elif len(signal_words) >= 1:
        score += 0.5

    # 包含明确的需求词（求推荐、怎么办等），可行性更高
    need_indicators = ["求推荐", "怎么办", "有没有", "如何", "怎么", "need", "want",
                       "wish", "looking for", "recommend", "how to"]
    text_lower = text.lower()
    for indicator in need_indicators:
        if indicator in text_lower:
            score += 0.5
            break

    # 技术社区帖子可行性通常更高（问题更具体）
    if platform in ("stackoverflow", "v2ex", "hackernews"):
        score += 0.5

    # 限制范围
    score = max(1, min(5, int(round(score))))
    return score


# ============================================================
# Step 3: 导出待处理帖子为JSON（保留兼容）
# ============================================================

def export_pending_posts(conn, limit=100):
    """将预筛通过的未处理帖子导出为JSON列表（不标记已处理，留给 extract_pain_points_auto 处理）"""
    from database import get_unprocessed_posts

    unprocessed = get_unprocessed_posts(conn, limit=limit)
    pending = []

    for post in unprocessed:
        title = post.get("title", "")
        content = post.get("content", "")

        if not should_process(title, content):
            continue  # 不标记已处理，留给 extract_pain_points_auto 的兜底逻辑

        pending.append({
            "id": post["id"],
            "title": title,
            "content": content[:1500],
            "platform": post.get("platform", ""),
            "url": post.get("url", ""),
        })

    return pending


# ============================================================
# Step 4: 注入AI提取的痛点到数据库（保留兼容）
# ============================================================

def inject_pain_points(conn, extracted_data):
    """将外部AI提取的痛点注入数据库（保留兼容）"""
    from database import mark_post_processed

    total_injected = 0

    for item in extracted_data:
        post_id = item.get("post_id")
        points = item.get("pain_points", [])

        if not post_id:
            continue

        if points:
            for point in points:
                desc = str(point.get("description", "")).strip()
                if not desc or len(desc) < 5:
                    continue

                category = str(point.get("category", "other")).strip().lower()
                valid_cats = {
                    "work", "study", "life", "computer", "phone",
                    "internet", "other",
                }
                if category not in valid_cats:
                    category = "other"

                try:
                    feasibility = int(point.get("feasibility", 3))
                    feasibility = max(1, min(5, feasibility))
                except (ValueError, TypeError):
                    feasibility = 3

                keywords = str(point.get("keywords", "")).strip()
                feas_reason = str(point.get("feasibility_reason", "AI提取"))

                point_data = {
                    "post_id": post_id,
                    "description": desc,
                    "category": category,
                    "feasibility": feasibility,
                    "feasibility_reason": feas_reason,
                    "keywords": keywords,
                }

                cluster_pain_points(conn, [point_data])
                total_injected += 1

        mark_post_processed(conn, post_id)

    return total_injected


# ============================================================
# Step 5: Jaccard 聚类
# ============================================================

def cluster_pain_points(conn, new_points):
    """将新提取的痛点聚类到已有簇或创建新簇"""
    existing_clusters = get_all_clusters(conn)
    clustered_count = 0

    for point in new_points:
        pp_id = insert_pain_point(
            conn,
            post_id=point["post_id"],
            description=point["description"],
            category=point["category"],
            feasibility=point["feasibility"],
            feasibility_reason=point["feasibility_reason"],
            keywords=point["keywords"],
        )

        point_kw = set(k.strip().lower() for k in point["keywords"].split(",") if k.strip())

        if not point_kw:
            cluster_id = create_cluster(
                conn, point["description"], point["category"], point["keywords"]
            )
            add_to_cluster(conn, cluster_id, pp_id, point["keywords"])
            clustered_count += 1
            continue

        best_match_id = None
        best_score = 0.0

        for cluster in existing_clusters:
            cluster_kw = set(
                k.strip().lower() for k in (cluster["keywords"] or "").split(",") if k.strip()
            )
            if not cluster_kw:
                continue

            intersection = point_kw & cluster_kw
            union = point_kw | cluster_kw
            score = len(intersection) / len(union) if union else 0

            if score > best_score:
                best_score = score
                best_match_id = cluster["id"]

        if best_match_id and best_score >= CLUSTER_THRESHOLD:
            add_to_cluster(conn, best_match_id, pp_id, point["keywords"])
            for c in existing_clusters:
                if c["id"] == best_match_id:
                    c["keywords"] = ",".join(
                        set(k.strip() for k in (c["keywords"] or "").split(",")) |
                        set(k.strip() for k in point["keywords"].split(","))
                    )
                    c["member_count"] += 1
                    break
        else:
            new_cluster_id = create_cluster(
                conn, point["description"], point["category"], point["keywords"]
            )
            add_to_cluster(conn, new_cluster_id, pp_id, point["keywords"])
            existing_clusters.append({
                "id": new_cluster_id,
                "keywords": point["keywords"],
                "member_count": 1,
            })

        clustered_count += 1

    return clustered_count


# ============================================================
# Step 6: 趋势检测 + 排序
# ============================================================

def update_all_trends(conn):
    """更新所有簇的趋势"""
    clusters = get_all_clusters(conn)
    now = datetime.now()

    for cluster in clusters:
        trend = _detect_trend(conn, cluster, now)
        update_cluster_trend(conn, cluster["id"], trend)


def _detect_trend(conn, cluster, now):
    """检测单个簇的趋势"""
    first_seen = cluster["first_seen"]
    try:
        first_dt = datetime.fromisoformat(first_seen)
        if (now - first_dt).days <= TREND_NEW_DAYS:
            return "new"
    except (ValueError, TypeError):
        pass

    recent = get_cluster_member_count_since(conn, cluster["id"], 7)
    previous_period_count = get_cluster_member_count_since(conn, cluster["id"], 14) - recent

    if previous_period_count == 0:
        return "stable" if recent == 0 else "increasing"

    growth = (recent - previous_period_count) / previous_period_count

    if growth > TREND_INCREASE_RATIO:
        return "increasing"
    elif growth < TREND_DECREASE_RATIO:
        return "decreasing"
    else:
        return "stable"


def compute_rankings(conn):
    """计算所有簇的综合评分并排名"""
    clusters = get_all_clusters(conn)
    now = datetime.now()

    if not clusters:
        return []

    max_count = max(c["member_count"] for c in clusters)
    if max_count == 0:
        max_count = 1

    rankings = []
    for cluster in clusters:
        freq_comp = cluster["member_count"] / max_count

        try:
            last_seen = datetime.fromisoformat(cluster["last_seen"])
            days_since = max((now - last_seen).days, 0)
        except (ValueError, TypeError):
            days_since = 30
        recency_comp = math.exp(-days_since / RECENCY_HALFLIFE_DAYS)

        avg_feas = get_cluster_feasibility_avg(conn, cluster["id"])
        feas_comp = avg_feas / 5.0

        score = (
            freq_comp * WEIGHT_FREQUENCY +
            recency_comp * WEIGHT_RECENCY +
            feas_comp * WEIGHT_FEASIBILITY
        )

        rankings.append({
            "cluster_id": cluster["id"],
            "score": round(score, 4),
            "freq_comp": round(freq_comp, 4),
            "recency_comp": round(recency_comp, 4),
            "feas_comp": round(feas_comp, 4),
            "representative_text": cluster["representative_text"],
            "category": cluster["category"],
            "member_count": cluster["member_count"],
            "trend": cluster["trend"],
            "keywords": cluster["keywords"],
        })

    rankings.sort(key=lambda x: x["score"], reverse=True)

    for i, r in enumerate(rankings):
        r["rank"] = i + 1

    return rankings
