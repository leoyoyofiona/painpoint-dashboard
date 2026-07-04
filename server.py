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
from datetime import datetime, timedelta
from urllib.parse import urlparse

# Render 环境变量 PORT，本地默认 7531
PORT = int(os.environ.get("PORT", 7531))
BIND = "0.0.0.0"  # Render 要求绑定 0.0.0.0
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable  # 自动获取当前 Python 路径
DASHBOARD = os.path.join(BASE_DIR, "dashboard.html")

# Pipeline state
pipeline = {
    "running": False,
    "stage": "idle",
    "output": [],
    "error": None,
    "started_at": None,
    "finished_at": None,
}

STAGE_MAP = {
    "采集": "collecting",
    "预筛": "filtering",
    "排名": "ranking",
    "看板": "generating_dashboard",
    "注入": "injecting",
}


def run_pipeline():
    """在后台线程中运行采集流水线 (collect-only → export JSON)"""
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
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                pipeline["output"].append(line)
                for keyword, stage in STAGE_MAP.items():
                    if keyword in line:
                        pipeline["stage"] = stage
                        break

        proc.wait()
        if proc.returncode != 0:
            pipeline["error"] = f"Exit code {proc.returncode}"

    except Exception as e:
        pipeline["error"] = str(e)
    finally:
        pipeline["running"] = False
        pipeline["stage"] = "done"
        pipeline["finished_at"] = datetime.now().isoformat()
        # 重新生成看板（用已有数据）
        _regenerate_dashboard()


def _regenerate_dashboard():
    """用数据库中已有数据重新生成看板（不重新采集）"""
    try:
        proc = subprocess.run(
            [PYTHON, "main.py", "--skip-collect"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode == 0:
            pipeline["output"].append("看板已自动更新")
    except Exception as e:
        pipeline["output"].append(f"看板更新失败: {e}")


def scheduler_loop():
    """后台调度线程：每天北京时间8:00 (UTC 00:00) 自动采集"""
    while True:
        now = datetime.now(datetime.timezone.utc)
        # 计算下一个 00:00 UTC
        next_run = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        wait_seconds = (next_run - now).total_seconds()

        # 最多等一小时，避免休眠过久
        sleep_chunk = min(wait_seconds, 3600)
        time.sleep(sleep_chunk)

        # 检查是否到了执行时间
        now = datetime.now(datetime.timezone.utc)
        if now.hour == 0 and now.minute < 5 and not pipeline["running"]:
            print(f"[Scheduler] 开始每日自动采集: {now.isoformat()}")
            thread = threading.Thread(target=run_pipeline, daemon=True)
            thread.start()
            # 跑了之后等 10 分钟再检查，避免重复触发
            time.sleep(600)


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _path(self):
        return urlparse(self.path).path

    def do_GET(self):
        p = self._path()
        if p == "/" or p == "/dashboard.html":
            self._serve_dashboard()
        elif p == "/api/status":
            self._serve_json(pipeline)
        elif p == "/api/health":
            self._serve_json({"status": "ok"})
        else:
            self.send_error(404)

    def do_POST(self):
        p = self._path()
        if p == "/api/refresh":
            self._handle_refresh()
        else:
            self.send_error(404)

    def _serve_dashboard(self):
        if not os.path.exists(DASHBOARD):
            # 首次启动，尝试生成看板
            try:
                subprocess.run(
                    [PYTHON, "main.py", "--skip-collect"],
                    cwd=BASE_DIR,
                    capture_output=True,
                    timeout=60,
                )
            except Exception:
                pass

        if not os.path.exists(DASHBOARD):
            self.send_error(503, "Dashboard not ready. Please wait for first collection.")
            return

        with open(DASHBOARD, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def _serve_json(self, data):
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_refresh(self):
        if pipeline["running"]:
            body = json.dumps({"error": "Pipeline already running"}).encode()
            self.send_response(409)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        thread = threading.Thread(target=run_pipeline, daemon=True)
        thread.start()

        body = json.dumps({"message": "Pipeline started"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # 静默请求日志


if __name__ == "__main__":
    print(f"  LEO · 大众需求排行榜 服务器启动")
    print(f"  端口: {PORT} | 绑定: {BIND}")
    print(f"  自动采集: 每日 08:00 (北京时间)")

    # 启动后台调度线程
    scheduler = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler.start()

    # 启动 HTTP 服务器
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((BIND, PORT), Handler) as httpd:
        print(f"  看板地址: http://localhost:{PORT}")
        print(f"  按 Ctrl+C 停止")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  服务器已停止")
