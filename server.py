"""
server.py - 大众需求排行榜 HTTP 服务器
支持本地运行和 Render 部署 | 内置每日8点（北京时间）自动刷新
"""
import http.server
import socketserver
import threading
import json
import os
import sys
import time
import sqlite3
import signal
import traceback
import io
import contextlib
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

PORT = int(os.environ.get("PORT", 7531))
BIND = "0.0.0.0"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD = os.path.join(BASE_DIR, "dashboard.html")

# 确保项目目录在 sys.path 中（进程内导入需要）
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

pipeline = {
    "running": False,
    "stage": "idle",
    "output": [],
    "error": None,
    "started_at": None,
    "finished_at": None,
    "progress_pct": 0,
    "progress_msg": "",
}
pipeline_lock = threading.Lock()

# 阶段映射 — 匹配 main.py run_full() 的输出行关键词
STAGE_MAP = [
    ("开始采集 douyin", "collect_douyin"),
    ("开始采集 hackernews", "collect_hackernews"),
    ("开始采集 reddit", "collect_reddit"),
    ("开始采集 v2ex", "collect_v2ex"),
    ("开始采集 weibo", "collect_weibo"),
    ("开始采集 baidu", "collect_baidu"),
    ("开始采集 stackoverflow", "collect_stackoverflow"),
    ("开始采集 producthunt", "collect_producthunt"),
    ("开始采集 workbuddy", "collect_workbuddy"),
    ("跳过采集", "skip_collect"),
    ("预筛帖子", "filtering"),
    ("自动提取痛点", "extracting"),
    ("更新聚类趋势", "trending"),
    ("计算排名", "ranking"),
    ("生成HTML看板", "dashboard"),
    ("看板已生成", "done"),
]


class PipelineWriter(io.StringIO):
    """自定义 stdout 写入器 — 实时推送进度到 pipeline 状态"""

    def write(self, s):
        result = super().write(s)
        stripped = s.rstrip()
        if stripped:
            with pipeline_lock:
                pipeline["output"].append(stripped)
            _update_stage(stripped)
        return result


def run_pipeline():
    """在后台线程中运行完整采集+看板流水线（进程内执行）"""
    with pipeline_lock:
        pipeline["running"] = True
        pipeline["stage"] = "starting"
        pipeline["output"] = []
        pipeline["error"] = None
        pipeline["started_at"] = datetime.now().isoformat()
        pipeline["finished_at"] = None
        pipeline["progress_pct"] = 0
        pipeline["progress_msg"] = "正在启动..."

    try:
        from main import run_full

        writer = PipelineWriter()
        with contextlib.redirect_stdout(writer):
            run_full(verbose=False, skip_collect=False)

        # 检查是否产生了实际输出（有采集数据的标志）
        full_output = writer.getvalue()
        if not full_output.strip():
            pipeline["error"] = "流水线未产生任何输出"

    except Exception as e:
        pipeline["error"] = f"{type(e).__name__}: {e}"
        traceback.print_exc()
    finally:
        with pipeline_lock:
            pipeline["running"] = False
            pipeline["stage"] = "done"
            pipeline["finished_at"] = datetime.now().isoformat()
            pipeline["progress_pct"] = 100
            pipeline["progress_msg"] = "刷新完成！"


def _update_stage(line):
    """根据输出行更新进度阶段"""
    with pipeline_lock:
        for keyword, stage in STAGE_MAP:
            if keyword in line:
                pipeline["stage"] = stage
                break

        # 预估进度百分比
        stage_pct = {
            "collect_douyin": 15,
            "collect_hackernews": 25,
            "collect_reddit": 35,
            "collect_v2ex": 45,
            "collect_weibo": 50,
            "collect_baidu": 55,
            "collect_stackoverflow": 60,
            "collect_producthunt": 63,
            "collect_workbuddy": 65,
            "filtering": 70,
            "extracting": 75,
            "ranking": 85,
            "trending": 90,
            "dashboard": 95,
            "done": 100,
        }
        pct = stage_pct.get(pipeline["stage"], pipeline["progress_pct"])
        pipeline["progress_pct"] = pct
        pipeline["progress_msg"] = line[:80]


def scheduler_loop():
    """后台调度线程：每天北京时间8:00 (UTC 00:00) 自动采集"""
    while True:
        now = datetime.now(timezone.utc)
        next_run = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        wait_seconds = (next_run - now).total_seconds()
        sleep_chunk = min(wait_seconds, 3600)
        time.sleep(sleep_chunk)

        now = datetime.now(timezone.utc)
        if now.hour == 0 and now.minute < 5:
            with pipeline_lock:
                if pipeline["running"]:
                    continue
            print(f"[Scheduler] 开始每日自动采集: {now.isoformat()}", flush=True)
            thread = threading.Thread(target=run_pipeline, daemon=False)
            thread.start()
            time.sleep(600)


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _path(self):
        return urlparse(self.path).path

    def do_GET(self):
        try:
            p = self._path()
            if p == "/" or p == "/dashboard.html":
                self._serve_dashboard()
            elif p == "/api/status":
                s = {}
                with pipeline_lock:
                    s = {
                        "running": pipeline["running"],
                        "stage": pipeline["stage"],
                        "output": pipeline["output"][-20:],  # 只返回最近20行
                        "error": pipeline["error"],
                        "started_at": pipeline["started_at"],
                        "finished_at": pipeline["finished_at"],
                        "progress_pct": pipeline["progress_pct"],
                        "progress_msg": pipeline["progress_msg"],
                    }
                self._serve_json(s)
            elif p == "/api/health":
                self._serve_json({"status": "ok"})
            else:
                self.send_error(404)
        except Exception as e:
            traceback.print_exc()
            try:
                self.send_error(500, str(e))
            except Exception:
                pass

    def do_POST(self):
        try:
            p = self._path()
            if p == "/api/refresh":
                self._handle_refresh()
            elif p == "/api/submit-request":
                self._handle_submit_request()
            else:
                self.send_error(404)
        except Exception as e:
            traceback.print_exc()
            try:
                self.send_error(500, str(e))
            except Exception:
                pass

    def _serve_dashboard(self):
        if not os.path.exists(DASHBOARD):
            try:
                from main import run_full
                with contextlib.redirect_stdout(io.StringIO()):
                    run_full(verbose=False, skip_collect=False)
            except Exception:
                pass

        if not os.path.exists(DASHBOARD):
            self.send_error(503, "Dashboard not ready.")
            return

        with open(DASHBOARD, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def _serve_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_refresh(self):
        with pipeline_lock:
            if pipeline["running"]:
                self._serve_json({"error": "正在刷新中，请稍候..."}, 409)
                return

        # 先返回响应
        self._serve_json({"message": "刷新已启动"})

        thread = threading.Thread(target=run_pipeline, daemon=False)
        thread.start()

    def _handle_submit_request(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(raw_body)

            description = (data.get("description") or "").strip()
            if not description or len(description) < 5:
                self._serve_json({"error": "请至少输入5个字描述你的需求"}, 400)
                return
            if len(description) > 1000:
                self._serve_json({"error": "描述不能超过1000字"}, 400)
                return

            email = (data.get("email") or "").strip()
            if email and "@" not in email:
                self._serve_json({"error": "邮箱格式不正确"}, 400)
                return
            if not email:
                email = None

            ip = self.headers.get("X-Forwarded-For", self.client_address[0])
            if "," in ip:
                ip = ip.split(",")[0].strip()

            db_path = os.path.join(BASE_DIR, "painpoints.db")
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    description TEXT NOT NULL,
                    email TEXT,
                    category TEXT,
                    source TEXT DEFAULT 'web',
                    ip TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute(
                """INSERT INTO user_requests
                   (description, email, category, source, ip, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (description, email, "user_submitted", "web", ip, datetime.now().isoformat())
            )
            conn.commit()
            conn.close()

            self._serve_json({"message": "诉求已提交，感谢你的参与！"})

        except json.JSONDecodeError:
            self._serve_json({"error": "请求格式错误"}, 400)
        except Exception as e:
            traceback.print_exc()
            self._serve_json({"error": f"服务器错误: {e}"}, 500)

    def log_message(self, *args):
        pass


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)

    print(f"  LEO · 大众需求排行榜 服务器启动", flush=True)
    print(f"  端口: {PORT} | 绑定: {BIND}", flush=True)
    print(f"  数据源: 抖音 · 微博 · 百度 · V2EX · Hacker News · Reddit · Stack Overflow · Product Hunt", flush=True)
    print(f"  自动采集: 每日 08:00 (北京时间)", flush=True)

    scheduler = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler.start()

    with ThreadingTCPServer((BIND, PORT), Handler) as httpd:
        print(f"  看板地址: http://localhost:{PORT}", flush=True)
        print(f"  按 Ctrl+C 停止", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  服务器已停止", flush=True)
