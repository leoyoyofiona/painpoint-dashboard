"""
processor.py - NLP 处理管道
jieba预筛 -> Jaccard聚类 -> 排序
（痛点提取由 WorkBuddy AI 在自动化流程中完成）
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

# 初始化jieba（延迟加载，首次调用时自动完成）
_jieba_initialized = False


def _ensure_jieba():
    global _jieba_initialized
    if not _jieba_initialized:
        jieba.initialize()
        _jieba_initialized = True


# ============================================================
# Step 1: jieba 预筛
# ============================================================

def should_process(title, content):
    """
    判断帖子是否值得送AI处理
    规则:
    1. 必须同时包含 (痛点词 OR 需求词) AND 工具词
    2. 包含专业排除词的直接跳过
    3. 空标题或过短内容跳过
    """
    _ensure_jieba()

    text = f"{title} {content}".lower()

    # 0. 排除专业领域
    cn_exclude = bool(EXCLUDE_KEYWORDS & set(jieba.cut(text)))
    en_exclude = any(kw in text for kw in EN_EXCLUDE)
    if cn_exclude or en_exclude:
        return False

    # 1. 英文关键词直接子串匹配
    en_pain_hit = any(kw in text for kw in EN_PAIN)
    en_need_hit = any(kw in text for kw in EN_NEED)
    en_tool_hit = any(kw in text for kw in EN_TOOL)

    # 2. 中文用jieba分词后匹配
    words = set(jieba.cut(text))
    cn_pain_hit = bool(PAIN_KEYWORDS & words)
    cn_need_hit = bool(NEED_KEYWORDS & words)
    cn_tool_hit = bool(TOOL_KEYWORDS & words)

    has_signal = cn_pain_hit or cn_need_hit or en_pain_hit or en_need_hit
    has_tool = cn_tool_hit or en_tool_hit

    return has_signal and has_tool


# ============================================================
# Step 2: 导出待处理帖子为JSON（供 WorkBuddy AI 提取）
# ============================================================

def export_pending_posts(conn, limit=100):
    """
    将预筛通过的未处理帖子导出为JSON列表
    返回待处理帖子列表，每条含 id/title/content/platform
    """
    from database import get_unprocessed_posts

    unprocessed = get_unprocessed_posts(conn, limit=limit)
    pending = []

    for post in unprocessed:
        title = post.get("title", "")
        content = post.get("content", "")

        if not should_process(title, content):
            # 预筛未通过，直接标记已处理
            from database import mark_post_processed
            mark_post_processed(conn, post["id"])
            continue

        pending.append({
            "id": post["id"],
            "title": title,
            "content": content[:1500],  # 截断，避免JSON过大
            "platform": post.get("platform", ""),
            "url": post.get("url", ""),
        })

    return pending


# ============================================================
# Step 3: 注入AI提取的痛点到数据库
# ============================================================

def inject_pain_points(conn, extracted_data):
    """
    将 WorkBuddy AI 提取的痛点注入数据库
    extracted_data: list of {
        "post_id": int,
        "pain_points": [
            {
                "description": str,
                "category": str,
                "feasibility": int (1-5),
                "feasibility_reason": str,
                "keywords": str
            }
        ]
    }
    返回注入的痛点总数
    """
    from database import mark_post_processed

    total_injected = 0

    for item in extracted_data:
        post_id = item.get("post_id")
        points = item.get("pain_points", [])

        if not post_id:
            continue

        # 即使没有提取到痛点，也标记帖子已处理
        if points:
            for point in points:
                # 规范化数据
                desc = str(point.get("description", "")).strip()
                if not desc or len(desc) < 5:
                    continue

                category = str(point.get("category", "other")).strip().lower()
                valid_cats = {
                    "work", "study", "life", "computer", "phone",
                    "internet", "other",
                    "工作", "学习", "生活", "电脑", "手机", "网络", "其他",
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

        # 标记帖子已处理
        mark_post_processed(conn, post_id)

    return total_injected


# ============================================================
# Step 4: Jaccard 聚类
# ============================================================

def cluster_pain_points(conn, new_points):
    """
    将新提取的痛点聚类到已有簇或创建新簇
    使用Jaccard关键词相似度
    """
    existing_clusters = get_all_clusters(conn)
    clustered_count = 0

    for point in new_points:
        # 插入痛点记录
        pp_id = insert_pain_point(
            conn,
            post_id=point["post_id"],
            description=point["description"],
            category=point["category"],
            feasibility=point["feasibility"],
            feasibility_reason=point["feasibility_reason"],
            keywords=point["keywords"],
        )

        # 提取痛点关键词集合
        point_kw = set(k.strip().lower() for k in point["keywords"].split(",") if k.strip())

        if not point_kw:
            # 无关键词，直接创建新簇
            cluster_id = create_cluster(
                conn, point["description"], point["category"], point["keywords"]
            )
            add_to_cluster(conn, cluster_id, pp_id, point["keywords"])
            clustered_count += 1
            continue

        # 寻找最佳匹配簇
        best_match_id = None
        best_score = 0.0

        for cluster in existing_clusters:
            cluster_kw = set(
                k.strip().lower() for k in (cluster["keywords"] or "").split(",") if k.strip()
            )
            if not cluster_kw:
                continue

            # Jaccard相似度
            intersection = point_kw & cluster_kw
            union = point_kw | cluster_kw
            score = len(intersection) / len(union) if union else 0

            if score > best_score:
                best_score = score
                best_match_id = cluster["id"]

        if best_match_id and best_score >= CLUSTER_THRESHOLD:
            # 加入已有簇
            add_to_cluster(conn, best_match_id, pp_id, point["keywords"])
            # 更新内存中的簇列表
            for c in existing_clusters:
                if c["id"] == best_match_id:
                    c["keywords"] = ",".join(
                        set(k.strip() for k in (c["keywords"] or "").split(",")) |
                        set(k.strip() for k in point["keywords"].split(","))
                    )
                    c["member_count"] += 1
                    break
        else:
            # 创建新簇
            new_cluster_id = create_cluster(
                conn, point["description"], point["category"], point["keywords"]
            )
            add_to_cluster(conn, new_cluster_id, pp_id, point["keywords"])
            # 加入内存列表供后续匹配
            existing_clusters.append({
                "id": new_cluster_id,
                "keywords": point["keywords"],
                "member_count": 1,
            })

        clustered_count += 1

    return clustered_count


# ============================================================
# Step 5: 趋势检测 + 排序
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
    # 3天内首次出现 → new
    first_seen = cluster["first_seen"]
    try:
        first_dt = datetime.fromisoformat(first_seen)
        if (now - first_dt).days <= TREND_NEW_DAYS:
            return "new"
    except (ValueError, TypeError):
        pass

    # 最近7天 vs 前7天成员增长
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
    """
    计算所有簇的综合评分并排名
    score = frequency(40%) + recency(30%) + feasibility(30%)
    """
    clusters = get_all_clusters(conn)
    now = datetime.now()

    if not clusters:
        return []

    # 找最大成员数用于归一化
    max_count = max(c["member_count"] for c in clusters)
    if max_count == 0:
        max_count = 1

    rankings = []
    for cluster in clusters:
        # 频率分量
        freq_comp = cluster["member_count"] / max_count

        # 时效分量（指数衰减）
        try:
            last_seen = datetime.fromisoformat(cluster["last_seen"])
            days_since = max((now - last_seen).days, 0)
        except (ValueError, TypeError):
            days_since = 30
        recency_comp = math.exp(-days_since / RECENCY_HALFLIFE_DAYS)

        # 可行性分量
        avg_feas = get_cluster_feasibility_avg(conn, cluster["id"])
        feas_comp = avg_feas / 5.0

        # 综合评分
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

    # 按评分降序排列
    rankings.sort(key=lambda x: x["score"], reverse=True)

    # 分配排名
    for i, r in enumerate(rankings):
        r["rank"] = i + 1

    return rankings
