"""
database.py - SQLite 数据库层
建表、CRUD操作、数据保留策略清理
"""

import sqlite3
import os
from datetime import datetime, timedelta
from config import (
    DB_PATH, RETENTION_POSTS_DAYS, RETENTION_PAINPOINTS_DAYS,
    RETENTION_LOGS_DAYS, DISK_WARNING_MB
)


def get_db():
    """获取数据库连接（启用外键级联）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    """初始化所有表"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL,
        post_id TEXT NOT NULL,
        title TEXT,
        content TEXT,
        author TEXT,
        url TEXT,
        reply_count INTEGER DEFAULT 0,
        posted_at TEXT,
        collected_at TEXT NOT NULL,
        processed INTEGER DEFAULT 0,
        UNIQUE(platform, post_id)
    );

    CREATE TABLE IF NOT EXISTS pain_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER REFERENCES posts(id) ON DELETE CASCADE,
        description TEXT NOT NULL,
        original_text TEXT,
        inspiration TEXT,
        category TEXT,
        feasibility INTEGER,
        feasibility_reason TEXT,
        keywords TEXT,
        extracted_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS need_clusters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        representative_text TEXT NOT NULL,
        category TEXT,
        keywords TEXT,
        member_count INTEGER DEFAULT 1,
        first_seen TEXT NOT NULL,
        last_seen TEXT NOT NULL,
        trend TEXT DEFAULT 'new'
    );

    CREATE TABLE IF NOT EXISTS cluster_members (
        cluster_id INTEGER REFERENCES need_clusters(id) ON DELETE CASCADE,
        pain_point_id INTEGER REFERENCES pain_points(id) ON DELETE CASCADE,
        PRIMARY KEY (cluster_id, pain_point_id)
    );

    CREATE TABLE IF NOT EXISTS daily_rankings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ranking_date TEXT NOT NULL,
        cluster_id INTEGER REFERENCES need_clusters(id),
        rank INTEGER,
        score REAL,
        frequency_component REAL,
        recency_component REAL,
        feasibility_component REAL,
        UNIQUE(ranking_date, cluster_id)
    );

    CREATE TABLE IF NOT EXISTS collection_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_date TEXT NOT NULL,
        platform TEXT,
        posts_collected INTEGER DEFAULT 0,
        pain_points_extracted INTEGER DEFAULT 0,
        errors TEXT,
        duration_seconds REAL,
        status TEXT DEFAULT 'running'
    );

    CREATE INDEX IF NOT EXISTS idx_posts_collected ON posts(collected_at);
    CREATE INDEX IF NOT EXISTS idx_posts_processed ON posts(processed);
    CREATE INDEX IF NOT EXISTS idx_posts_platform ON posts(platform);
    CREATE INDEX IF NOT EXISTS idx_painpoints_category ON pain_points(category);
    CREATE INDEX IF NOT EXISTS idx_painpoints_post ON pain_points(post_id);
    CREATE INDEX IF NOT EXISTS idx_rankings_date ON daily_rankings(ranking_date);
    CREATE INDEX IF NOT EXISTS idx_clusters_category ON need_clusters(category);
    CREATE INDEX IF NOT EXISTS idx_clustermembers_cluster ON cluster_members(cluster_id);
    CREATE INDEX IF NOT EXISTS idx_clustermembers_pp ON cluster_members(pain_point_id);
    CREATE INDEX IF NOT EXISTS idx_logs_date ON collection_logs(run_date);

    CREATE TABLE IF NOT EXISTS user_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT NOT NULL,
        email TEXT,
        category TEXT,
        source TEXT DEFAULT 'web',
        ip TEXT,
        created_at TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_ur_created ON user_requests(created_at);
    """)

    # 迁移：给 pain_points 表添加 inspiration 列（如果不存在）
    try:
        conn.execute("ALTER TABLE pain_points ADD COLUMN inspiration TEXT")
    except sqlite3.OperationalError:
        pass  # 列已存在

    conn.commit()
    conn.close()


# ============================================================
# Posts CRUD
# ============================================================

def insert_post(conn, platform, post_id, title, content, author, url,
                reply_count, posted_at):
    """插入帖子（重复则忽略）"""
    try:
        conn.execute(
            """INSERT OR IGNORE INTO posts
               (platform, post_id, title, content, author, url,
                reply_count, posted_at, collected_at, processed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (platform, str(post_id), title, content, author, url,
             reply_count, posted_at, datetime.now().isoformat())
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def get_unprocessed_posts(conn, limit=100):
    """获取未处理的帖子"""
    rows = conn.execute(
        """SELECT * FROM posts WHERE processed = 0
           ORDER BY collected_at ASC LIMIT ?""",
        (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def mark_post_processed(conn, post_id):
    """标记帖子已处理"""
    conn.execute("UPDATE posts SET processed = 1 WHERE id = ?", (post_id,))
    conn.commit()


def count_posts_today(conn):
    """统计今日采集帖子数"""
    today = datetime.now().strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM posts WHERE collected_at LIKE ?",
        (f"{today}%",)
    ).fetchone()
    return row["cnt"]


# ============================================================
# Pain Points CRUD
# ============================================================

def insert_pain_point(conn, post_id, description, category, feasibility,
                      feasibility_reason, keywords, original_text=None, inspiration=None):
    """插入痛点，返回痛点ID"""
    cursor = conn.execute(
        """INSERT INTO pain_points
           (post_id, description, original_text, inspiration, category, feasibility,
            feasibility_reason, keywords, extracted_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (post_id, description, original_text, inspiration, category, feasibility,
         feasibility_reason, keywords, datetime.now().isoformat())
    )
    conn.commit()
    return cursor.lastrowid


# ============================================================
# Clusters CRUD
# ============================================================

def get_all_clusters(conn):
    """获取所有簇"""
    rows = conn.execute("SELECT * FROM need_clusters").fetchall()
    return [dict(r) for r in rows]


def create_cluster(conn, text, category, keywords):
    """创建新簇，返回簇ID"""
    now = datetime.now().isoformat()
    cursor = conn.execute(
        """INSERT INTO need_clusters
           (representative_text, category, keywords, member_count,
            first_seen, last_seen, trend)
           VALUES (?, ?, ?, 1, ?, ?, 'new')""",
        (text, category, keywords, now, now)
    )
    conn.commit()
    return cursor.lastrowid


def add_to_cluster(conn, cluster_id, pain_point_id, new_keywords):
    """将痛点加入簇，更新簇关键词和计数"""
    # 获取当前簇信息
    row = conn.execute(
        "SELECT keywords, member_count FROM need_clusters WHERE id = ?",
        (cluster_id,)
    ).fetchone()

    if row:
        # 合并关键词
        existing_kw = set(k.strip() for k in (row["keywords"] or "").split(",") if k.strip())
        new_kw = set(k.strip() for k in new_keywords.split(",") if k.strip())
        merged = ",".join(sorted(existing_kw | new_kw))

        conn.execute(
            """UPDATE need_clusters
               SET member_count = ?, keywords = ?, last_seen = ?
               WHERE id = ?""",
            (row["member_count"] + 1, merged, datetime.now().isoformat(), cluster_id)
        )

    # 插入关联
    conn.execute(
        "INSERT OR IGNORE INTO cluster_members (cluster_id, pain_point_id) VALUES (?, ?)",
        (cluster_id, pain_point_id)
    )
    conn.commit()


def update_cluster_trend(conn, cluster_id, trend):
    """更新簇趋势"""
    conn.execute("UPDATE need_clusters SET trend = ? WHERE id = ?", (trend, cluster_id))
    conn.commit()


def get_cluster_member_count_since(conn, cluster_id, days_ago):
    """获取簇在最近N天内新增的成员数"""
    cutoff = (datetime.now() - timedelta(days=days_ago)).isoformat()
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM cluster_members cm
           JOIN pain_points pp ON cm.pain_point_id = pp.id
           WHERE cm.cluster_id = ? AND pp.extracted_at >= ?""",
        (cluster_id, cutoff)
    ).fetchone()
    return row["cnt"]


def get_cluster_feasibility_avg(conn, cluster_id):
    """获取簇内痛点的平均可行性"""
    row = conn.execute(
        """SELECT AVG(feasibility) as avg_feas FROM cluster_members cm
           JOIN pain_points pp ON cm.pain_point_id = pp.id
           WHERE cm.cluster_id = ?""",
        (cluster_id,)
    ).fetchone()
    return row["avg_feas"] if row["avg_feas"] else 3.0


def get_cluster_post_urls(conn, cluster_id, limit=5):
    """获取簇相关的帖子URL"""
    rows = conn.execute(
        """SELECT DISTINCT p.url, p.title, p.platform
           FROM cluster_members cm
           JOIN pain_points pp ON cm.pain_point_id = pp.id
           JOIN posts p ON pp.post_id = p.id
           WHERE cm.cluster_id = ?
           LIMIT ?""",
        (cluster_id, limit)
    ).fetchall()
    return [dict(r) for r in rows]


# ============================================================
# Rankings CRUD
# ============================================================

def save_rankings(conn, date_str, rankings):
    """保存当日排名"""
    # 先删除当天已有排名（支持重跑）
    conn.execute("DELETE FROM daily_rankings WHERE ranking_date = ?", (date_str,))
    for r in rankings:
        conn.execute(
            """INSERT OR REPLACE INTO daily_rankings
               (ranking_date, cluster_id, rank, score,
                frequency_component, recency_component, feasibility_component)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (date_str, r["cluster_id"], r["rank"], r["score"],
             r["freq_comp"], r["recency_comp"], r["feas_comp"])
        )
    conn.commit()


def get_latest_rankings(conn, limit=50):
    """获取最新排名"""
    row = conn.execute(
        "SELECT MAX(ranking_date) as latest FROM daily_rankings"
    ).fetchone()
    if not row or not row["latest"]:
        return [], None

    latest_date = row["latest"]
    rows = conn.execute(
        """SELECT dr.*, nc.representative_text, nc.category, nc.member_count,
                  nc.trend, nc.keywords
           FROM daily_rankings dr
           JOIN need_clusters nc ON dr.cluster_id = nc.id
           WHERE dr.ranking_date = ?
           ORDER BY dr.rank ASC
           LIMIT ?""",
        (latest_date, limit)
    ).fetchall()
    return [dict(r) for r in rows], latest_date


# ============================================================
# Collection Logs
# ============================================================

def start_log(conn):
    """开始记录日志，返回日志ID"""
    cursor = conn.execute(
        """INSERT INTO collection_logs
           (run_date, status) VALUES (?, 'running')""",
        (datetime.now().isoformat(),)
    )
    conn.commit()
    return cursor.lastrowid


def finish_log(conn, log_id, posts_collected, pain_points_extracted,
               errors, duration, status="completed"):
    """完成日志记录"""
    conn.execute(
        """UPDATE collection_logs
           SET posts_collected = ?, pain_points_extracted = ?,
               errors = ?, duration_seconds = ?, status = ?
           WHERE id = ?""",
        (posts_collected, pain_points_extracted,
         errors, duration, status, log_id)
    )
    conn.commit()


# ============================================================
# 数据保留 / 清理
# ============================================================

def cleanup_old_data(conn):
    """清理过期数据"""
    now = datetime.now()
    cutoff_posts = (now - timedelta(days=RETENTION_POSTS_DAYS)).isoformat()
    cutoff_pp = (now - timedelta(days=RETENTION_PAINPOINTS_DAYS)).isoformat()
    cutoff_logs = (now - timedelta(days=RETENTION_LOGS_DAYS)).isoformat()

    # 删除过期帖子（级联删除关联痛点）
    conn.execute("DELETE FROM posts WHERE collected_at < ?", (cutoff_posts,))

    # 删除过期痛点（保留簇成员）
    conn.execute(
        """DELETE FROM pain_points
           WHERE extracted_at < ?
           AND id NOT IN (SELECT pain_point_id FROM cluster_members)""",
        (cutoff_pp,)
    )

    # 删除过期日志
    conn.execute("DELETE FROM collection_logs WHERE run_date < ?", (cutoff_logs,))

    conn.commit()

    # VACUUM 回收空间
    try:
        conn.execute("VACUUM")
    except Exception:
        pass  # WAL模式下VACUUM可能需要独占锁，失败则跳过


def check_disk_space():
    """检查可用磁盘空间（MB），返回可用空间"""
    try:
        stat = os.statvfs("/")
        return (stat.f_bavail * stat.f_frsize) / (1024 * 1024)
    except Exception:
        return 9999  # 无法检测时不阻止


# ============================================================
# 用户诉求提交
# ============================================================

def insert_user_request(conn, description, email=None, source="web", ip=None):
    """插入用户提交的诉求"""
    cursor = conn.execute(
        """INSERT INTO user_requests
           (description, email, category, source, ip, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (description, email, "user_submitted", source, ip, datetime.now().isoformat())
    )
    conn.commit()
    return cursor.lastrowid


def get_stats(conn):
    """获取全局统计"""
    stats = {}
    row = conn.execute("SELECT COUNT(*) as cnt FROM posts").fetchone()
    stats["total_posts"] = row["cnt"]

    row = conn.execute("SELECT COUNT(*) as cnt FROM pain_points").fetchone()
    stats["total_pain_points"] = row["cnt"]

    row = conn.execute("SELECT COUNT(*) as cnt FROM need_clusters").fetchone()
    stats["total_clusters"] = row["cnt"]

    stats["posts_today"] = count_posts_today(conn)

    # 平台分布
    rows = conn.execute(
        "SELECT platform, COUNT(*) as cnt FROM posts GROUP BY platform"
    ).fetchall()
    stats["platform_dist"] = {r["platform"]: r["cnt"] for r in rows}

    # 分类分布
    rows = conn.execute(
        """SELECT category, COUNT(*) as cnt FROM need_clusters
           GROUP BY category ORDER BY cnt DESC"""
    ).fetchall()
    stats["category_dist"] = {r["category"]: r["cnt"] for r in rows}

    # 趋势分布
    rows = conn.execute(
        "SELECT trend, COUNT(*) as cnt FROM need_clusters GROUP BY trend"
    ).fetchall()
    stats["trend_dist"] = {r["trend"]: r["cnt"] for r in rows}

    return stats


def get_pain_points_with_posts(conn, limit=200, category=None, exclude_dev=True):
    """
    获取痛点列表（含帖子信息），用于卡片式看板。
    只返回大众化日常痛点，排除专业开发需求。
    """
    DEV_TERMS = [
        "kubernetes", "docker", "container", "microservice", "微服务",
        "机器学习", "深度学习", "neural network", "compiler", "编译器",
        "blockchain", "区块链", "distributed", "分布式", "embedded",
        "嵌入式", "kernel", "内核", "firmware",
        "K8s", "CI/CD", "devops", "container",
        "cursor", "claude code", "codex", "antigravity", "chatgpt plus",
        "IDE", "编程框架", "RAG", "vector database", "向量库",
        "Codex", "Cursor",
        # 新增 — 更多专业开发术语排除
        "react", "vue", "angular", "svelte", "nextjs", "nuxt",
        "typescript", "rust", "golang", "kotlin", "swift",
        "webpack", "vite", "rollup", "esbuild",
        "postgresql", "mongodb", "redis", "elasticsearch",
        "graphql", "grpc", "protobuf", "thrift",
        "terraform", "ansible", "puppet", "helm",
        "linux kernel", "system call", "syscall",
        "reverse engineering", "逆向",
        "fpga", "verilog", "vhdl",
        "cryptography", "密码学",
        "concurrency", "并发", "multithreading", "多线程",
        "garbage collection", "GC", "内存管理",
        "compiler optimization", "JIT",
        "webassembly", "WASM",
        "kafka", "rabbitmq", "celery",
        "nginx", "apache", "load balancer",
    ]

    query = """
        SELECT pp.id, pp.description, pp.inspiration, pp.original_text, pp.category,
               pp.feasibility, pp.feasibility_reason, pp.keywords,
               pp.extracted_at,
               p.platform, p.title, p.url, p.post_id
        FROM pain_points pp
        JOIN posts p ON pp.post_id = p.id
        WHERE pp.description IS NOT NULL AND trim(pp.description) != ''
    """
    params = []

    if category:
        query += " AND pp.category = ?"
        params.append(category)

    if exclude_dev:
        for i, term in enumerate(DEV_TERMS):
            query += f" AND (lower(pp.description) NOT LIKE ? AND lower(coalesce(pp.keywords, '')) NOT LIKE ?)"
            params.append(f"%{term.lower()}%")
            params.append(f"%{term.lower()}%")

    query += " ORDER BY pp.extracted_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        english_platforms = ("hackernews", "reddit", "stackoverflow", "producthunt")
        d["is_english"] = d.get("platform", "").lower() in english_platforms
        results.append(d)

    return results


def get_pain_point_post_detail(conn, pain_point_id):
    """获取单个痛点的帖子详情"""
    row = conn.execute(
        """SELECT p.title, p.content, p.url, p.platform, p.posted_at
           FROM pain_points pp
           JOIN posts p ON pp.post_id = p.id
           WHERE pp.id = ?""",
        (pain_point_id,)
    ).fetchone()
    return dict(row) if row else None
