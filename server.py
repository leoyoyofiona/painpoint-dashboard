"""
server.py - 大众需求排行榜 HTTP 服务器
支持本地运行和 Render 部署 | 内置每日8点（北京时间）自动刷新
"""
import http.server
import socketserver
import subprocess
import threading
import json
import os
import sys
import time
import sqlite3
import signal
import traceback
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

# Render 环境变量 PORT，本地默认 7531
PORT = int(os.environ.get("PORT", 7531))
BIND = "0.0.0.0"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable
DASHBOARD = os.path.join(BASE_DIR, "dashboard.html")

# ——— 子进程环境（清除代理，避免网络问题）———
def _clean_env():
    """构建干净的子进程环境变量，移除代理设置"""
    env = os.environ.copy()
    for key in list(env.keys()):
        if key.lower().endswith('_proxy'):
            del env[key]
    # 显式禁用代理
    env['http_proxy'] = ''
    env['https_proxy'] = ''
    env['HTTP_PROXY'] = ''
    env['HTTPS_PROXY'] = ''
    env['no_proxy'] = '*'
    env['NO_PROXY'] = '*'
    return env

CLEAN_ENV = _clean_env()

# Pipeline state（线程安全通过 GIL 保护简单读写）
pipeline = {
    "running": False,
    "stage": "idle",
    "output": [],
    "error": None,
    "started_at": None,
    "finished_at": None,
}
pipeline_lock = threading.Lock()

STAGE_MAP = {
    "采集": "collecting",
    "预筛": "filtering",
    "排名": "ranking",
    "看板": "generating_dashboard",
    "注入": "injecting",
}


def run_pipeline():
    """在后台线程中运行采集流水线 (collect-only → export JSON)"""
    with pipeline_lock:
        pipeline["running"] = True
        pipeline["stage"] = "starting"
        pipeline["output"] = []
        pipeline["error"] = None
        pipeline["started_at"] = datetime.now().isoformat()
        pipeline["finished_at"] = None

    try:
        proc = subprocess.Popen(
            [PYTHON, "main.py", "--collect-only"],
            cwd=BASE_DIR,
            env=CLEAN_ENV,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            preexec_fn=os.setsid,  # 独立进程组，避免信号传播
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                pipeline["output"].append(line)
                for keyword, stage in STAGE_MAP.items():
                    if keyword in line:
                        pipeline["stage"] = stage
                        break

        proc.wait(timeout=300)  # 最多等 5 分钟
        if proc.returncode != 0:
            pipeline["error"] = f"Exit code {proc.returncode}"

    except subprocess.TimeoutExpired:
        proc.kill()
        pipeline["error"] = "采集超时（5分钟）"
    except Exception as e:
        pipeline["error"] = f"{type(e).__name__}: {e}"
        traceback.print_exc()
    finally:
        with pipeline_lock:
            pipeline["running"] = False
            pipeline["stage"] = "done"
            pipeline["finished_at"] = datetime.now().isoformat()
        # 重新生成看板（用已有数据）
        _regenerate_dashboard()


def _regenerate_dashboard():
    """用数据库中已有数据重新生成看板（不重新采集）"""
    try:
        subprocess.run(
            [PYTHON, "main.py", "--skip-collect"],
            cwd=BASE_DIR,
            env=CLEAN_ENV,
            capture_output=True,
            text=True,
            timeout=120,
        )
        pipeline["output"].append("看板已自动更新")
    except Exception as e:
        pipeline["output"].append(f"看板更新失败: {e}")


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
                self._serve_json(pipeline.copy())
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
                subprocess.run(
                    [PYTHON, "main.py", "--skip-collect"],
                    cwd=BASE_DIR,
                    env=CLEAN_ENV,
                    capture_output=True,
                    timeout=60,
                )
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
            running = pipeline["running"]
        if running:
            self._serve_json({"error": "Pipeline already running"}, 409)
            return

        # 先返回响应，再后台启动
        self._serve_json({"message": "Pipeline started"})

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
        pass  # 静默请求日志


# ——— 多线程服务器 ———
class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True  # 主进程退出时自动清理线程


if __name__ == "__main__":
    # 忽略子进程信号，避免子进程终止导致父进程退出
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)

    print(f"  LEO · 大众需求排行榜 服务器启动", flush=True)
    print(f"  端口: {PORT} | 绑定: {BIND}", flush=True)
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
