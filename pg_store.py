"""
pg_store.py - PostgreSQL 持久化层（user_requests 专用）

Render 免费版文件系统是临时的，每次重启/重新部署 SQLite 数据库都会被清空。
本模块用 PostgreSQL 持久化存储用户提交的诉求，确保跨重启不丢失。

当环境变量 DATABASE_URL 存在时启用 PostgreSQL；否则所有函数静默跳过。
"""

import os
import traceback
from datetime import datetime

# 检测是否启用 PostgreSQL
DATABASE_URL = os.environ.get("DATABASE_URL", "")

_pg_available = False
if DATABASE_URL:
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        _pg_available = True
    except ImportError:
        pass


def is_pg_enabled():
    """是否启用了 PostgreSQL 持久化"""
    return _pg_available


def _get_conn():
    """获取 PostgreSQL 连接"""
    return psycopg2.connect(DATABASE_URL)


def ensure_table():
    """确保 user_requests 表存在"""
    if not _pg_available:
        return
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_requests (
                        id SERIAL PRIMARY KEY,
                        description TEXT NOT NULL,
                        email TEXT,
                        category TEXT,
                        source TEXT DEFAULT 'web',
                        ip TEXT,
                        created_at TEXT NOT NULL
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ur_created_pg
                    ON user_requests(created_at)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ur_email_pg
                    ON user_requests(email)
                """)
    except Exception:
        traceback.print_exc()


def insert_request(description, email, category, source="web", ip=None, created_at=None):
    """插入一条用户诉求到 PostgreSQL"""
    if not _pg_available:
        return
    if created_at is None:
        created_at = datetime.now().isoformat()
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO user_requests
                       (description, email, category, source, ip, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (description, email, category, source, ip, created_at)
                )
    except Exception:
        traceback.print_exc()


def get_recent_requests(limit=50):
    """获取最近的用户诉求"""
    if not _pg_available:
        return []
    try:
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """SELECT id, description, email, category, created_at
                       FROM user_requests
                       ORDER BY id DESC LIMIT %s""",
                    (limit,)
                )
                rows = cur.fetchall()
                return [dict(r) for r in rows]
    except Exception:
        traceback.print_exc()
        return []


def get_total_count():
    """获取用户诉求总数"""
    if not _pg_available:
        return 0
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM user_requests")
                row = cur.fetchone()
                return row[0] if row else 0
    except Exception:
        return 0


def search_requests(query, limit=30):
    """按邮箱或描述模糊搜索"""
    if not _pg_available:
        return []
    try:
        like_q = f"%{query}%"
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """SELECT id, description, email, category, created_at
                       FROM user_requests
                       WHERE email ILIKE %s OR description ILIKE %s
                       ORDER BY id DESC LIMIT %s""",
                    (like_q, like_q, limit)
                )
                rows = cur.fetchall()
                return [dict(r) for r in rows]
    except Exception:
        traceback.print_exc()
        return []


def sync_from_sqlite(sqlite_conn):
    """将 SQLite 中的 user_requests 同步到 PostgreSQL（启动时调用）"""
    if not _pg_available:
        return 0
    try:
        # 获取 PG 中已有的所有记录（用 description+email+created_at 去重）
        with _get_conn() as pg_conn:
            with pg_conn.cursor() as cur:
                cur.execute("SELECT description, email, created_at FROM user_requests")
                existing = set()
                for row in cur.fetchall():
                    existing.add((row[0], row[1] or "", row[2]))

        # 从 SQLite 读取所有 user_requests
        sqlite_conn.row_factory = None
        rows = sqlite_conn.execute(
            "SELECT description, email, category, source, ip, created_at FROM user_requests"
        ).fetchall()

        inserted = 0
        for r in rows:
            key = (r[0], r[1] or "", r[5])
            if key not in existing:
                try:
                    with _get_conn() as pg_conn:
                        with pg_conn.cursor() as cur:
                            cur.execute(
                                """INSERT INTO user_requests
                                   (description, email, category, source, ip, created_at)
                                   VALUES (%s, %s, %s, %s, %s, %s)""",
                                (r[0], r[1], r[2], r[3], r[4], r[5])
                            )
                    inserted += 1
                except Exception:
                    pass

        if inserted > 0:
            print(f"  [pg_store] 从 SQLite 同步 {inserted} 条用户诉求到 PostgreSQL")

        return inserted
    except Exception:
        traceback.print_exc()
        return 0
