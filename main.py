"""
main.py - 痛点收集器主编排器

三种运行模式:
    python main.py                      # 传统全流程（关键词提取，无AI）
    python main.py --collect-only       # 仅采集+预筛，导出 pending_posts.json 供AI提取
    python main.py --inject <file.json> # 注入AI提取的痛点 + 聚类 + 排序 + 看板
    python main.py --skip-collect       # 跳过采集，用关键词模式重新处理
    python main.py --verbose            # 详细输出
"""

import sys
import os
import time
import json
from datetime import datetime

from config import DISK_WARNING_MB, DASHBOARD_TOP_N, DASHBOARD_PATH, BASE_DIR
from database import (
    init_db, get_db, insert_post, get_unprocessed_posts,
    mark_post_processed, cleanup_old_data, check_disk_space,
    get_stats, start_log, finish_log, save_rankings,
    get_latest_rankings,
)
from collectors import collect_all
from processor import (
    should_process, export_pending_posts, inject_pain_points,
    cluster_pain_points, update_all_trends, compute_rankings,
)
from dashboard import generate_dashboard

PENDING_POSTS_PATH = os.path.join(BASE_DIR, "pending_posts.json")


def run_collect_only(verbose=False):
    """模式1: 仅采集 + 预筛 + 导出JSON"""
    print("=" * 60)
    print("  痛点收集器 - 采集模式 (--collect-only)")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    start_time = time.time()
    init_db()
    conn = get_db()

    # 磁盘检查
    disk_mb = check_disk_space()
    print(f"\n  可用磁盘: {disk_mb:.0f} MB")
    if disk_mb < DISK_WARNING_MB:
        print(f"  ⚠️ 磁盘空间不足，触发清理")
        cleanup_old_data(conn)

    # 1. 采集
    print("\n[1/3] 开始采集...")
    total_posts = 0
    try:
        posts, collect_results = collect_all()
        total_posts = len(posts)
        inserted = 0
        for post in posts:
            try:
                success = insert_post(
                    conn,
                    platform=post["platform"],
                    post_id=post["post_id"],
                    title=post.get("title", ""),
                    content=post.get("content", ""),
                    author=post.get("author", ""),
                    url=post.get("url", ""),
                    reply_count=post.get("reply_count", 0),
                    posted_at=post.get("posted_at"),
                )
                if success:
                    inserted += 1
            except Exception:
                pass
        print(f"  新增帖子: {inserted} / {total_posts}")
    except Exception as e:
        print(f"  ❌ 采集失败: {e}")

    # 2. 预筛 + 导出
    print("\n[2/3] 预筛帖子并导出...")
    pending = export_pending_posts(conn, limit=100)
    print(f"  预筛通过: {len(pending)} 帖")

    # 3. 写JSON
    print("\n[3/3] 导出待处理帖子...")
    with open(PENDING_POSTS_PATH, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)
    print(f"  已导出: {PENDING_POSTS_PATH}")
    print(f"  文件大小: {os.path.getsize(PENDING_POSTS_PATH) / 1024:.1f} KB")

    duration = time.time() - start_time
    print(f"\n  耗时: {duration:.1f}s")
    print(f"  下一步: 由 WorkBuddy AI 读取 pending_posts.json 提取痛点")
    print("=" * 60)

    conn.close()
    return 0


def run_inject(json_file, verbose=False):
    """模式2: 注入AI提取的痛点 + 聚类 + 排序 + 看板"""
    print("=" * 60)
    print("  痛点收集器 - 注入模式 (--inject)")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    start_time = time.time()
    init_db()
    conn = get_db()

    log_id = start_log(conn)

    # 1. 读取AI提取结果
    print(f"\n[1/5] 读取AI提取结果: {json_file}")
    if not os.path.exists(json_file):
        print(f"  ❌ 文件不存在: {json_file}")
        conn.close()
        return 1

    with open(json_file, "r", encoding="utf-8") as f:
        extracted_data = json.load(f)

    print(f"  读取 {len(extracted_data)} 条帖子提取结果")

    # 2. 注入痛点
    print("\n[2/5] 注入痛点到数据库...")
    total_pp = inject_pain_points(conn, extracted_data)
    print(f"  注入痛点: {total_pp}")

    # 3. 更新趋势
    print("\n[3/5] 更新聚类趋势...")
    try:
        update_all_trends(conn)
        print("  完成")
    except Exception as e:
        print(f"  ⚠️ 趋势更新失败: {e}")

    # 4. 排序
    print("\n[4/5] 计算排名...")
    rankings = []
    try:
        rankings = compute_rankings(conn)
        today = datetime.now().strftime("%Y-%m-%d")
        save_rankings(conn, today, rankings)
        print(f"  生成排名: {len(rankings)} 条")
    except Exception as e:
        print(f"  ⚠️ 排名失败: {e}")

    # 5. 生成看板
    print("\n[5/5] 生成HTML看板...")
    try:
        dashboard_path = generate_dashboard(conn)
        print(f"  看板已生成: {dashboard_path}")
    except Exception as e:
        print(f"  ⚠️ 看板生成失败: {e}")

    # 清理
    try:
        cleanup_old_data(conn)
    except Exception:
        pass

    # 日志
    duration = time.time() - start_time
    finish_log(conn, log_id, 0, total_pp, None, duration, "completed")

    # 摘要
    print("\n" + "=" * 60)
    print("  运行摘要")
    print("=" * 60)
    print(f"  注入痛点: {total_pp}")
    print(f"  运行耗时: {duration:.1f} 秒")

    if rankings:
        print(f"\n  Top 5 需求:")
        for r in rankings[:5]:
            trend_icon = {"increasing": "↑", "new": "✦", "decreasing": "↓", "stable": "→"}.get(r["trend"], "")
            print(f"    {r['rank']}. [{r['category']}] {r['representative_text'][:50]}  "
                  f"(频次:{r['member_count']} 可行:{r['feas_comp']*5:.1f} {trend_icon} 评分:{r['score']:.2f})")

    print(f"\n  看板文件: {DASHBOARD_PATH}")
    print("=" * 60)

    conn.close()
    return 0


def run_full(verbose=False, skip_collect=False):
    """模式3: 传统全流程（关键词模式，无AI）"""
    print("=" * 60)
    print("  痛点收集器 PainPoint Collector")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    start_time = time.time()
    init_db()
    conn = get_db()

    # 磁盘检查
    disk_mb = check_disk_space()
    print(f"\n  可用磁盘: {disk_mb:.0f} MB")
    if disk_mb < DISK_WARNING_MB:
        print(f"  ⚠️ 磁盘空间不足 {DISK_WARNING_MB}MB，触发清理")
        cleanup_old_data(conn)

    log_id = start_log(conn)
    all_errors = []
    total_posts = 0
    total_pain_points = 0

    # 1. 采集
    if skip_collect:
        print("\n[1/7] 跳过采集（--skip-collect）")
    else:
        print("\n[1/7] 开始采集...")
        try:
            posts, collect_results = collect_all()
            total_posts = len(posts)
            for platform, result in collect_results.items():
                if result["status"] == "error":
                    all_errors.append(f"{platform}: {result['error']}")
            inserted = 0
            for post in posts:
                try:
                    success = insert_post(
                        conn,
                        platform=post["platform"],
                        post_id=post["post_id"],
                        title=post.get("title", ""),
                        content=post.get("content", ""),
                        author=post.get("author", ""),
                        url=post.get("url", ""),
                        reply_count=post.get("reply_count", 0),
                        posted_at=post.get("posted_at"),
                    )
                    if success:
                        inserted += 1
                except Exception:
                    pass
            print(f"  新增帖子: {inserted} / {total_posts}")
        except Exception as e:
            all_errors.append(f"采集失败: {e}")
            print(f"  ❌ {e}")

    # 2. 预筛 + 导出（标记未通过的为已处理）
    print("\n[2/7] 预筛帖子...")
    pending = export_pending_posts(conn, limit=100)
    print(f"  预筛通过: {len(pending)} 帖")

    # 3. 导出JSON（供后续AI处理）
    print("[3/7] 导出 pending_posts.json...")
    with open(PENDING_POSTS_PATH, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)
    print(f"  已导出: {len(pending)} 帖 → {PENDING_POSTS_PATH}")

    # 4-7: 聚类/排序/看板（如果有已注入的痛点）
    print("\n[4/7] 更新聚类趋势...")
    try:
        update_all_trends(conn)
        print("  完成")
    except Exception as e:
        print(f"  ⚠️ {e}")

    print("\n[5/7] 计算排名...")
    rankings = []
    try:
        rankings = compute_rankings(conn)
        today = datetime.now().strftime("%Y-%m-%d")
        save_rankings(conn, today, rankings)
        print(f"  生成排名: {len(rankings)} 条")
    except Exception as e:
        print(f"  ⚠️ {e}")

    print("\n[6/7] 生成HTML看板...")
    try:
        dashboard_path = generate_dashboard(conn)
        print(f"  看板已生成: {dashboard_path}")
    except Exception as e:
        print(f"  ⚠️ {e}")

    print("\n[7/7] 清理旧数据...")
    try:
        cleanup_old_data(conn)
    except Exception:
        pass

    duration = time.time() - start_time
    status = "completed" if not all_errors else "completed_with_errors"
    finish_log(conn, log_id, total_posts, total_pain_points,
               json.dumps(all_errors, ensure_ascii=False) if all_errors else None,
               duration, status)

    print("\n" + "=" * 60)
    print("  运行摘要")
    print("=" * 60)
    print(f"  采集帖子: {total_posts}")
    print(f"  预筛通过: {len(pending)} (已导出 pending_posts.json)")
    print(f"  运行耗时: {duration:.1f} 秒")
    print(f"\n  ⚠️ 当前为全流程模式，未做AI痛点提取")
    print(f"  要使用AI提取，请运行:")
    print(f"    1. python main.py --collect-only")
    print(f"    2. (WorkBuddy AI 处理 pending_posts.json)")
    print(f"    3. python main.py --inject extracted_painpoints.json")
    print(f"\n  看板文件: {DASHBOARD_PATH}")
    print("=" * 60)

    conn.close()
    return 0 if not all_errors else 1


def main():
    verbose = "--verbose" in sys.argv
    collect_only = "--collect-only" in sys.argv

    # 检查 --inject 模式
    inject_file = None
    for i, arg in enumerate(sys.argv):
        if arg == "--inject" and i + 1 < len(sys.argv):
            inject_file = sys.argv[i + 1]
            break

    if collect_only:
        return run_collect_only(verbose=verbose)
    elif inject_file:
        return run_inject(inject_file, verbose=verbose)
    else:
        skip_collect = "--skip-collect" in sys.argv
        return run_full(verbose=verbose, skip_collect=skip_collect)


if __name__ == "__main__":
    sys.exit(main())
