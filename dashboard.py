"""
dashboard.py - 交互式 HTML 看板生成器
单文件输出，内联CSS/JS，暗色主题，零外部依赖
"""

import json
from datetime import datetime
from config import DASHBOARD_PATH, DASHBOARD_TOP_N
from database import (
    get_latest_rankings, get_stats, get_cluster_post_urls,
    get_all_clusters,
)


def generate_dashboard(conn):
    """生成HTML看板并写入文件"""
    rankings, latest_date = get_latest_rankings(conn, DASHBOARD_TOP_N)
    stats = get_stats(conn)

    # 为每个排名项添加相关帖子URL
    for r in rankings:
        r["related_posts"] = get_cluster_post_urls(conn, r["cluster_id"], 5)

    # 趋势概览
    trends = _build_trend_overview(rankings)

    # 构建嵌入数据
    dashboard_data = {
        "rankings": rankings,
        "stats": stats,
        "trends": trends,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ranking_date": latest_date,
    }

    html = _build_html(dashboard_data)

    with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    return DASHBOARD_PATH


def _build_trend_overview(rankings):
    """构建趋势概览数据"""
    increasing = [r for r in rankings if r["trend"] == "increasing"]
    new_needs = [r for r in rankings if r["trend"] == "new"]
    decreasing = [r for r in rankings if r["trend"] == "decreasing"]

    return {
        "increasing": [{"text": r["representative_text"], "count": r["member_count"]}
                       for r in increasing[:10]],
        "new": [{"text": r["representative_text"]}
                for r in new_needs[:10]],
        "decreasing": [{"text": r["representative_text"], "count": r["member_count"]}
                       for r in decreasing[:10]],
    }


def _build_html(data):
    """构建完整HTML"""
    data_json = json.dumps(data, ensure_ascii=False, default=str)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>大众需求排行榜 | LEO</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Helvetica Neue", sans-serif;
    background: #1a1a2e;
    color: #e0e0e0;
    line-height: 1.6;
    padding: 20px;
    max-width: 1200px;
    margin: 0 auto;
}}

/* ===== 头部 ===== */
.header {{
    background: linear-gradient(135deg, #FF6B6B 0%, #4ECDC4 100%);
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(255, 107, 107, 0.15);
    position: relative;
}}
.header h1 {{
    font-size: 26px;
    color: #fff;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 12px;
}}
.logo {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 48px;
    height: 48px;
    background: rgba(255,255,255,0.25);
    backdrop-filter: blur(12px);
    border: 2px solid rgba(255,255,255,0.5);
    border-radius: 12px;
    font-size: 18px;
    font-weight: 900;
    letter-spacing: 3px;
    color: #fff;
    text-shadow: 0 2px 4px rgba(0,0,0,0.2);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}}
.header .subtitle {{
    color: rgba(255,255,255,0.85);
    font-size: 14px;
    margin-top: 6px;
}}

/* ===== 醒目标语 ===== */
.cta-banner {{
    background: linear-gradient(135deg, rgba(255,107,107,0.25) 0%, rgba(78,205,196,0.25) 100%);
    border: 2px solid rgba(255,107,107,0.4);
    border-radius: 14px;
    padding: 20px 28px;
    margin-top: 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
}}
.cta-text {{
    flex: 1;
    min-width: 260px;
}}
.cta-text .cta-main {{
    font-size: 20px;
    font-weight: 800;
    background: linear-gradient(90deg, #FFD93D, #FF6B6B, #4ECDC4);
    background-clip: text;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: ctaShimmer 3s ease infinite;
}}
@keyframes ctaShimmer {{
    0%, 100% {{ filter: hue-rotate(0deg); }}
    50% {{ filter: hue-rotate(15deg); }}
}}
.cta-text .cta-sub {{
    color: rgba(255,255,255,0.75);
    font-size: 13px;
    margin-top: 4px;
}}
.cta-btn {{
    background: linear-gradient(135deg, #FF6B6B, #FFD93D);
    color: #1a1a2e;
    border: none;
    border-radius: 30px;
    padding: 14px 32px;
    font-size: 18px;
    font-weight: 800;
    cursor: pointer;
    white-space: nowrap;
    box-shadow: 0 4px 20px rgba(255,107,107,0.4);
    transition: all 0.3s;
    letter-spacing: 1px;
}}
.cta-btn:hover {{
    transform: scale(1.06);
    box-shadow: 0 6px 28px rgba(255,107,107,0.55);
}}
.cta-btn:active {{ transform: scale(0.98); }}

/* ===== 模态框 ===== */
.modal-overlay {{
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.8);
    z-index: 10000;
    justify-content: center;
    align-items: center;
    backdrop-filter: blur(4px);
}}
.modal-overlay.show {{ display: flex; }}
.modal-box {{
    background: #16213e;
    border: 1px solid rgba(78,205,196,0.3);
    border-radius: 18px;
    padding: 0;
    width: 500px;
    max-width: 92vw;
    box-shadow: 0 16px 60px rgba(0,0,0,0.5);
    animation: modalIn 0.3s ease;
}}
@keyframes modalIn {{
    from {{ transform: translateY(20px); opacity: 0; }}
    to {{ transform: translateY(0); opacity: 1; }}
}}
.modal-header {{
    background: linear-gradient(135deg, #FF6B6B, #4ECDC4);
    border-radius: 18px 18px 0 0;
    padding: 20px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}}
.modal-header h2 {{
    color: #fff;
    font-size: 18px;
    font-weight: 700;
    margin: 0;
}}
.modal-close {{
    background: rgba(255,255,255,0.2);
    border: none;
    color: #fff;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    font-size: 18px;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
}}
.modal-close:hover {{ background: rgba(255,255,255,0.35); }}
.modal-body {{
    padding: 24px;
}}
.modal-body label {{
    display: block;
    color: #aaa;
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 6px;
    margin-top: 14px;
}}
.modal-body label:first-child {{ margin-top: 0; }}
.modal-body textarea {{
    width: 100%;
    min-height: 120px;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
    color: #e0e0e0;
    padding: 12px;
    font-size: 14px;
    font-family: inherit;
    resize: vertical;
    outline: none;
    transition: border-color 0.2s;
}}
.modal-body textarea:focus {{
    border-color: #4ECDC4;
}}
.modal-body textarea::placeholder {{
    color: #555;
}}
.modal-body input[type="email"] {{
    width: 100%;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
    color: #e0e0e0;
    padding: 10px 12px;
    font-size: 14px;
    outline: none;
    transition: border-color 0.2s;
}}
.modal-body input[type="email"]:focus {{
    border-color: #4ECDC4;
}}
.modal-body input[type="email"]::placeholder {{
    color: #555;
}}
.modal-body .email-hint {{
    color: #4ECDC4;
    font-size: 12px;
    margin-top: 4px;
}}
.modal-footer {{
    padding: 0 24px 24px;
}}
.modal-submit {{
    width: 100%;
    background: linear-gradient(135deg, #FF6B6B, #4ECDC4);
    color: #fff;
    border: none;
    border-radius: 12px;
    padding: 14px;
    font-size: 16px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.3s;
    letter-spacing: 1px;
}}
.modal-submit:hover {{
    transform: translateY(-1px);
    box-shadow: 0 6px 24px rgba(255,107,107,0.3);
}}
.modal-submit:disabled {{
    opacity: 0.5;
    cursor: wait;
    transform: none;
}}
.modal-msg {{
    text-align: center;
    font-size: 14px;
    margin-top: 8px;
    min-height: 22px;
}}
.modal-msg.success {{ color: #4ECDC4; }}
.modal-msg.error {{ color: #FF6B6B; }}
.refresh-btn {{
    position: absolute;
    top: 24px;
    right: 28px;
    background: rgba(255,255,255,0.2);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.3);
    color: #fff;
    border-radius: 10px;
    padding: 8px 18px;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
}}
.refresh-btn:hover {{
    background: rgba(255,255,255,0.35);
    transform: scale(1.03);
}}
.refresh-btn:disabled {{
    opacity: 0.6;
    cursor: wait;
    transform: none;
}}
.refresh-btn .spin {{
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
}}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}

/* Loading overlay */
.load-overlay {{
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.75);
    z-index: 9999;
    justify-content: center;
    align-items: center;
}}
.load-overlay.show {{ display: flex; }}
.load-box {{
    background: #16213e;
    border-radius: 16px;
    padding: 32px 44px;
    text-align: center;
    max-width: 420px;
    border: 1px solid rgba(78,205,196,0.2);
    box-shadow: 0 8px 40px rgba(0,0,0,0.4);
}}
.load-box .load-icon {{
    font-size: 36px;
    margin-bottom: 12px;
    animation: bounce 1s ease infinite;
}}
@keyframes bounce {{
    0%, 100% {{ transform: translateY(0); }}
    50% {{ transform: translateY(-6px); }}
}}
.load-box .load-title {{
    color: #4ECDC4;
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 8px;
}}
.load-box .load-detail {{
    color: #aaa;
    font-size: 13px;
    margin-bottom: 16px;
    min-height: 20px;
}}
.load-box .load-bar {{
    width: 100%;
    height: 4px;
    background: rgba(255,255,255,0.08);
    border-radius: 2px;
    overflow: hidden;
}}
.load-box .load-bar-fill {{
    height: 100%;
    background: linear-gradient(90deg, #FF6B6B, #4ECDC4);
    border-radius: 2px;
    transition: width 0.5s ease;
    width: 0%;
}}
.stats-row {{
    display: flex;
    gap: 24px;
    margin-top: 16px;
    flex-wrap: wrap;
}}
.stat-item {{
    background: rgba(255,255,255,0.15);
    backdrop-filter: blur(10px);
    border-radius: 10px;
    padding: 10px 18px;
    color: #fff;
}}
.stat-item .num {{
    font-size: 22px;
    font-weight: 700;
}}
.stat-item .label {{
    font-size: 12px;
    opacity: 0.8;
}}

/* ===== 卡片通用 ===== */
.card {{
    background: #16213e;
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 20px;
    border: 1px solid rgba(255,255,255,0.05);
}}
.card-title {{
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
    color: #4ECDC4;
}}

/* ===== 筛选器 ===== */
.filters {{
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    align-items: center;
    margin-bottom: 16px;
}}
.filter-group {{
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
}}
.filter-btn {{
    background: rgba(255,255,255,0.06);
    color: #aaa;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
}}
.filter-btn:hover {{
    background: rgba(78,205,196,0.15);
    color: #4ECDC4;
}}
.filter-btn.active {{
    background: linear-gradient(135deg, #FF6B6B, #4ECDC4);
    color: #fff;
    border-color: transparent;
    font-weight: 600;
}}
select, input[type="text"] {{
    background: rgba(255,255,255,0.06);
    color: #e0e0e0;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 13px;
    outline: none;
}}
select:focus, input:focus {{
    border-color: #4ECDC4;
}}
input[type="text"] {{
    width: 200px;
}}

/* ===== 排行表格 ===== */
.table-wrap {{
    overflow-x: auto;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
}}
thead th {{
    text-align: left;
    padding: 10px 12px;
    color: #888;
    font-weight: 500;
    font-size: 12px;
    text-transform: uppercase;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
}}
thead th:hover {{ color: #4ECDC4; }}
thead th.sorted {{ color: #FF6B6B; }}
tbody tr {{
    border-bottom: 1px solid rgba(255,255,255,0.04);
    transition: background 0.15s;
}}
tbody tr:hover {{ background: rgba(78,205,196,0.05); }}
tbody td {{
    padding: 10px 12px;
    vertical-align: top;
}}
.rank-cell {{
    font-weight: 700;
    font-size: 16px;
    width: 40px;
}}
.rank-1 {{ color: #FFD93D; }}
.rank-2 {{ color: #C0C0C0; }}
.rank-3 {{ color: #CD7F32; }}
.desc-cell {{ max-width: 350px; }}
.cat-badge {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
}}
.cat-work, .cat-工作 {{ background: rgba(78,205,196,0.15); color: #4ECDC4; }}
.cat-study, .cat-学习 {{ background: rgba(255,217,61,0.15); color: #FFD93D; }}
.cat-life, .cat-生活 {{ background: rgba(255,107,107,0.15); color: #FF6B6B; }}
.cat-computer, .cat-电脑 {{ background: rgba(100,149,237,0.15); color: #6495ED; }}
.cat-phone, .cat-手机 {{ background: rgba(186,85,211,0.15); color: #BA55D3; }}
.cat-internet, .cat-网络 {{ background: rgba(50,205,50,0.15); color: #32CD32; }}
.cat-other, .cat-其他 {{ background: rgba(255,255,255,0.08); color: #888; }}

.freq-cell {{ text-align: center; font-weight: 600; color: #4ECDC4; }}
.feas-cell {{ text-align: center; }}
.feas-bar {{
    display: inline-block;
    width: 50px;
    height: 6px;
    background: rgba(255,255,255,0.08);
    border-radius: 3px;
    overflow: hidden;
    vertical-align: middle;
}}
.feas-fill {{
    height: 100%;
    border-radius: 3px;
    background: linear-gradient(90deg, #FF6B6B, #4ECDC4);
}}
.trend-cell {{ text-align: center; font-weight: 600; }}
.trend-increasing {{ color: #4ECDC4; }}
.trend-new {{ color: #FFD93D; }}
.trend-decreasing {{ color: #888; }}
.trend-stable {{ color: #666; }}
.score-cell {{
    text-align: center;
    font-weight: 700;
    font-size: 15px;
    color: #FF6B6B;
}}

/* 展开行 */
.detail-row {{
    display: none;
    background: rgba(0,0,0,0.2);
}}
.detail-row.show {{ display: table-row; }}
.detail-content {{
    padding: 12px 16px;
    font-size: 13px;
    color: #aaa;
}}
.detail-content .related-post {{
    margin: 4px 0;
}}
.detail-content a {{
    color: #4ECDC4;
    text-decoration: none;
}}
.detail-content a:hover {{ text-decoration: underline; }}
.detail-kw {{
    display: inline-block;
    background: rgba(255,255,255,0.06);
    padding: 2px 8px;
    border-radius: 4px;
    margin: 2px;
    font-size: 12px;
    color: #888;
}}

/* ===== 分类分布 ===== */
.dist-row {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 6px 0;
}}
.dist-label {{
    width: 60px;
    text-align: right;
    font-size: 13px;
    color: #aaa;
}}
.dist-bar {{
    flex: 1;
    height: 22px;
    background: rgba(255,255,255,0.04);
    border-radius: 6px;
    overflow: hidden;
    position: relative;
}}
.dist-fill {{
    height: 100%;
    border-radius: 6px;
    background: linear-gradient(90deg, #FF6B6B, #4ECDC4);
    transition: width 0.5s ease;
    display: flex;
    align-items: center;
    padding-left: 8px;
    color: #fff;
    font-size: 12px;
    font-weight: 600;
    min-width: 30px;
}}

/* ===== 趋势概览 ===== */
.trend-section {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 16px;
}}
.trend-col {{
    background: rgba(255,255,255,0.03);
    border-radius: 10px;
    padding: 14px;
}}
.trend-col h4 {{
    font-size: 13px;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 6px;
}}
.trend-item {{
    font-size: 13px;
    padding: 4px 0;
    color: #bbb;
    border-bottom: 1px solid rgba(255,255,255,0.03);
}}
.trend-item:last-child {{ border-bottom: none; }}

/* ===== 空状态 ===== */
.empty {{
    text-align: center;
    padding: 40px;
    color: #666;
    font-size: 15px;
}}

/* ===== 响应式 ===== */
@media (max-width: 768px) {{
    .trend-section {{ grid-template-columns: 1fr; }}
    .stats-row {{ gap: 12px; }}
    .desc-cell {{ max-width: 200px; }}
    input[type="text"] {{ width: 140px; }}
    .cta-banner {{ flex-direction: column; text-align: center; }}
    .cta-text .cta-main {{ font-size: 17px; }}
    .cta-btn {{ width: 100%; }}
    .modal-box {{ width: 95vw; }}
}}
</style>
</head>
<body>

<div class="header">
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">
        <h1 style="margin:0;"><span class="logo">LEO</span> 大众需求排行榜</h1>
        <button class="refresh-btn" id="refreshBtn" onclick="triggerRefresh()">
            <span id="refreshIcon">🔄</span> <span id="refreshText">刷新数据</span>
        </button>
    </div>
    <div class="subtitle" id="lastUpdated">加载中...</div>
    <div class="stats-row" id="statsRow"></div>

    <!-- 醒目标语 + 我要诉求 -->
    <div class="cta-banner">
        <div class="cta-text">
            <div class="cta-main">💡 你的痛点，就是下一个产品！</div>
            <div class="cta-sub">📢 征集大众痛点 — 说出你的需求，我们一起解决</div>
        </div>
        <button class="cta-btn" onclick="openRequestModal()">✍️ 我要诉求</button>
    </div>
</div>

<!-- Loading overlay -->
<div class="load-overlay" id="loadOverlay">
    <div class="load-box">
        <div class="load-icon" id="loadIcon">🔄</div>
        <div class="load-title" id="loadTitle">正在刷新数据</div>
        <div class="load-detail" id="loadDetail">正在启动采集...</div>
        <div class="load-bar"><div class="load-bar-fill" id="loadBarFill"></div></div>
    </div>
</div>

<!-- 排行表 -->
<div class="card">
    <div class="card-title">📊 需求排行榜</div>

    <div class="filters">
        <div class="filter-group" id="catFilters">
            <button class="filter-btn active" data-cat="all">全部</button>
            <button class="filter-btn" data-cat="work">工作</button>
            <button class="filter-btn" data-cat="study">学习</button>
            <button class="filter-btn" data-cat="life">生活</button>
            <button class="filter-btn" data-cat="computer">电脑</button>
            <button class="filter-btn" data-cat="phone">手机</button>
            <button class="filter-btn" data-cat="internet">网络</button>
            <button class="filter-btn" data-cat="other">其他</button>
        </div>
    </div>

    <div class="filters">
        <select id="feasFilter">
            <option value="all">可行性: 全部</option>
            <option value="high">高可行 (≥4)</option>
            <option value="mid">中等 (3)</option>
            <option value="low">低可行 (≤2)</option>
        </select>
        <select id="trendFilter">
            <option value="all">趋势: 全部</option>
            <option value="increasing">上升</option>
            <option value="new">新增</option>
            <option value="decreasing">下降</option>
            <option value="stable">稳定</option>
        </select>
        <input type="text" id="searchBox" placeholder="搜索需求...">
    </div>

    <div class="table-wrap">
        <table id="rankTable">
            <thead>
                <tr>
                    <th>#</th>
                    <th class="desc-cell" data-sort="text">需求描述</th>
                    <th data-sort="category">分类</th>
                    <th data-sort="freq" style="text-align:center;">频次</th>
                    <th data-sort="feas" style="text-align:center;">可行性</th>
                    <th data-sort="trend" style="text-align:center;">趋势</th>
                    <th data-sort="score" style="text-align:center;" class="sorted">评分 ↓</th>
                </tr>
            </thead>
            <tbody id="rankBody"></tbody>
        </table>
    </div>
    <div id="emptyMsg" class="empty" style="display:none;">暂无数据，请先运行采集</div>
</div>

<!-- 分类分布 -->
<div class="card">
    <div class="card-title">📈 分类分布</div>
    <div id="distChart"></div>
</div>

<!-- 趋势概览 -->
<div class="card">
    <div class="card-title">📉 趋势概览</div>
    <div class="trend-section">
        <div class="trend-col">
            <h4>🔴 上升中</h4>
            <div id="trendIncreasing"></div>
        </div>
        <div class="trend-col">
            <h4>🟡 新增需求</h4>
            <div id="trendNew"></div>
        </div>
        <div class="trend-col">
            <h4>⚪ 下降中</h4>
            <div id="trendDecreasing"></div>
        </div>
    </div>
</div>

<div style="text-align:center;padding:20px;color:#555;font-size:12px;margin-top:20px;">
    LEO · 大众需求排行榜 | 每日 08:00 自动刷新 | 数据来源：V2EX + Reddit
</div>

<!-- 我要诉求 模态框 -->
<div class="modal-overlay" id="requestModal">
    <div class="modal-box">
        <div class="modal-header">
            <h2>✍️ 提交你的诉求</h2>
            <button class="modal-close" onclick="closeRequestModal()">✕</button>
        </div>
        <div class="modal-body">
            <label>你的痛点 / 需求 <span style="color:#FF6B6B;">*</span></label>
            <textarea id="reqDescription" placeholder="请详细描述：你遇到了什么问题？希望有什么工具/产品来解决？&#10;&#10;例如：&#10;- 找不到一个汇总全网降价信息的APP&#10;- 孩子写作业总是拖延，有没有好的监督工具&#10;- 租房找室友太难了，想要一个靠谱的平台"></textarea>

            <label>你的邮箱（选填）</label>
            <input type="email" id="reqEmail" placeholder="your@email.com">
            <div class="email-hint">📬 留下邮箱，项目上线后第一时间获得内测资格</div>
        </div>
        <div class="modal-footer">
            <button class="modal-submit" id="submitBtn" onclick="submitRequest()">🚀 提交诉求</button>
            <div class="modal-msg" id="submitMsg"></div>
        </div>
    </div>
</div>

<script>
const DATA = {data_json};

// ===== 状态 =====
let state = {{
    cat: 'all',
    feas: 'all',
    trend: 'all',
    search: '',
    sortBy: 'score',
    sortDir: 'desc',
}};

// ===== 渲染头部 =====
function renderHeader() {{
    document.getElementById('lastUpdated').textContent =
        '最后更新: ' + DATA.last_updated + ' | 排名日期: ' + (DATA.ranking_date || 'N/A');

    const s = DATA.stats;
    const platformText = Object.entries(s.platform_dist || {{}})
        .map(([k, v]) => k + ': ' + v).join(' | ');

    document.getElementById('statsRow').innerHTML = `
        <div class="stat-item"><div class="num">${{s.total_clusters || 0}}</div><div class="label">需求簇总数</div></div>
        <div class="stat-item"><div class="num">${{s.total_pain_points || 0}}</div><div class="label">痛点总数</div></div>
        <div class="stat-item"><div class="num">${{s.posts_today || 0}}</div><div class="label">今日采集</div></div>
        <div class="stat-item"><div class="num">${{s.total_posts || 0}}</div><div class="label">帖子总量</div></div>
    `;
}}

// ===== 渲染排行表 =====
function renderTable() {{
    const tbody = document.getElementById('rankBody');
    let items = (DATA.rankings || []).slice();

    // 筛选
    if (state.cat !== 'all') {{
        items = items.filter(r => (r.category || '').toLowerCase() === state.cat);
    }}
    if (state.feas !== 'all') {{
        const feasMap = {{ r: r => r.cluster_id }};
        items = items.filter(r => {{
            const f = r.feas_comp * 5;
            if (state.feas === 'high') return f >= 3.5;
            if (state.feas === 'mid') return f >= 2.5 && f < 3.5;
            if (state.feas === 'low') return f < 2.5;
            return true;
        }});
    }}
    if (state.trend !== 'all') {{
        items = items.filter(r => r.trend === state.trend);
    }}
    if (state.search) {{
        const q = state.search.toLowerCase();
        items = items.filter(r =>
            (r.representative_text || '').toLowerCase().includes(q) ||
            (r.keywords || '').toLowerCase().includes(q)
        );
    }}

    // 排序
    const sortKey = state.sortBy;
    items.sort((a, b) => {{
        let va, vb;
        switch(sortKey) {{
            case 'text': va = a.representative_text || ''; vb = b.representative_text || ''; break;
            case 'category': va = a.category || ''; vb = b.category || ''; break;
            case 'freq': va = a.member_count; vb = b.member_count; break;
            case 'feas': va = a.feas_comp; vb = b.feas_comp; break;
            case 'trend': va = a.trend || ''; vb = b.trend || ''; break;
            default: va = a.score; vb = b.score;
        }}
        if (typeof va === 'string') {{
            return state.sortDir === 'desc' ? vb.localeCompare(va) : va.localeCompare(vb);
        }}
        return state.sortDir === 'desc' ? vb - va : va - vb;
    }});

    if (items.length === 0) {{
        tbody.innerHTML = '';
        document.getElementById('emptyMsg').style.display = 'block';
        return;
    }}
    document.getElementById('emptyMsg').style.display = 'none';

    tbody.innerHTML = items.map((r, i) => {{
        const rank = i + 1;
        const rankClass = rank <= 3 ? 'rank-' + rank : '';
        const cat = (r.category || 'other').toLowerCase();
        const feasPct = Math.round((r.feas_comp || 0) * 100);
        const feasVal = (r.feas_comp * 5).toFixed(1);
        const trendIcon = {{
            increasing: '↑ 上升', new: '✦ 新增', decreasing: '↓ 下降', stable: '→ 稳定'
        }}[r.trend] || r.trend;
        const trendClass = 'trend-' + (r.trend || 'stable');

        const kwHtml = (r.keywords || '').split(',')
            .filter(k => k.trim()).slice(0, 6)
            .map(k => '<span class="detail-kw">' + k.trim() + '</span>').join('');

        const postsHtml = (r.related_posts || []).map(p =>
            '<div class="related-post">🔗 <a href="' + (p.url || '#') + '" target="_blank">' +
            '[' + (p.platform || '') + '] ' + (p.title || '无标题').substring(0, 60) + '</a></div>'
        ).join('');

        return `
        <tr class="data-row" onclick="toggleDetail('detail-${{r.cluster_id}}')">
            <td class="rank-cell ${{rankClass}}">${{rank}}</td>
            <td class="desc-cell">${{r.representative_text || ''}}</td>
            <td><span class="cat-badge cat-${{cat}}">${{r.category || '其他'}}</span></td>
            <td class="freq-cell">${{r.member_count}}</td>
            <td class="feas-cell">
                <div class="feas-bar"><div class="feas-fill" style="width:${{feasPct}}%"></div></div>
                ${{feasVal}}
            </td>
            <td class="trend-cell ${{trendClass}}">${{trendIcon}}</td>
            <td class="score-cell">${{(r.score || 0).toFixed(2)}}</td>
        </tr>
        <tr class="detail-row" id="detail-${{r.cluster_id}}">
            <td colspan="7">
                <div class="detail-content">
                    <div style="margin-bottom:6px;"><strong>关键词:</strong> ${{kwHtml || '无'}}</div>
                    <div style="margin-bottom:6px;"><strong>评分构成:</strong> 频率${{(r.freq_comp||0).toFixed(2)}} × 时效${{(r.recency_comp||0).toFixed(2)}} × 可行性${{(r.feas_comp||0).toFixed(2)}}</div>
                    ${{postsHtml ? '<div style="margin-top:6px;"><strong>相关帖子:</strong></div>' + postsHtml : ''}}
                </div>
            </td>
        </tr>`;
    }}).join('');
}}

// ===== 渲染分类分布 =====
function renderDist() {{
    const dist = DATA.stats.category_dist || {{}};
    const entries = Object.entries(dist).sort((a, b) => b[1] - a[1]);
    const maxVal = Math.max(...entries.map(e => e[1]), 1);

    const catNames = {{
        work: '工作', study: '学习', life: '生活',
        computer: '电脑', phone: '手机', internet: '网络', other: '其他'
    }};

    document.getElementById('distChart').innerHTML = entries.map(([cat, count]) => {{
        const pct = Math.round(count / maxVal * 100);
        const name = catNames[cat] || cat;
        const total = entries.reduce((s, e) => s + e[1], 0);
        const sharePct = total > 0 ? Math.round(count / total * 100) : 0;
        return `<div class="dist-row">
            <div class="dist-label">${{name}}</div>
            <div class="dist-bar"><div class="dist-fill" style="width:${{pct}}%">${{count}} (${{sharePct}}%)</div></div>
        </div>`;
    }}).join('') || '<div class="empty">暂无数据</div>';
}}

// ===== 渲染趋势 =====
function renderTrends() {{
    const t = DATA.trends || {{}};

    document.getElementById('trendIncreasing').innerHTML =
        (t.increasing || []).map(item =>
            `<div class="trend-item">${{item.text}} <span style="color:#4ECDC4;">(${{item.count}})</span></div>`
        ).join('') || '<div class="trend-item" style="color:#666;">暂无</div>';

    document.getElementById('trendNew').innerHTML =
        (t.new || []).map(item =>
            `<div class="trend-item">${{item.text}}</div>`
        ).join('') || '<div class="trend-item" style="color:#666;">暂无</div>';

    document.getElementById('trendDecreasing').innerHTML =
        (t.decreasing || []).map(item =>
            `<div class="trend-item">${{item.text}} <span style="color:#888;">(${{item.count}})</span></div>`
        ).join('') || '<div class="trend-item" style="color:#666;">暂无</div>';
}}

// ===== 交互 =====
function toggleDetail(id) {{
    const row = document.getElementById(id);
    if (row) row.classList.toggle('show');
}}

// 分类筛选
document.getElementById('catFilters').addEventListener('click', e => {{
    if (e.target.classList.contains('filter-btn')) {{
        document.querySelectorAll('#catFilters .filter-btn').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        state.cat = e.target.dataset.cat;
        renderTable();
    }}
}});

// 可行性筛选
document.getElementById('feasFilter').addEventListener('change', e => {{
    state.feas = e.target.value;
    renderTable();
}});

// 趋势筛选
document.getElementById('trendFilter').addEventListener('change', e => {{
    state.trend = e.target.value;
    renderTable();
}});

// 搜索
document.getElementById('searchBox').addEventListener('input', e => {{
    state.search = e.target.value;
    renderTable();
}});

// 排序
document.querySelectorAll('#rankTable thead th').forEach(th => {{
    th.addEventListener('click', () => {{
        const sort = th.dataset.sort;
        if (!sort) return;
        if (state.sortBy === sort) {{
            state.sortDir = state.sortDir === 'desc' ? 'asc' : 'desc';
        }} else {{
            state.sortBy = sort;
            state.sortDir = 'desc';
        }}
        document.querySelectorAll('#rankTable thead th').forEach(t => t.classList.remove('sorted'));
        th.classList.add('sorted');
        th.textContent = th.textContent.replace(/[↑↓]/g, '') + (state.sortDir === 'desc' ? ' ↓' : ' ↑');
        renderTable();
    }});
}});

// ===== 刷新功能 =====
async function triggerRefresh() {{
    const btn = document.getElementById('refreshBtn');
    const icon = document.getElementById('refreshIcon');
    const text = document.getElementById('refreshText');
    const overlay = document.getElementById('loadOverlay');
    const detail = document.getElementById('loadDetail');
    const barFill = document.getElementById('loadBarFill');

    btn.disabled = true;
    icon.innerHTML = '<span class="spin"></span>';
    text.textContent = '采集中...';
    overlay.classList.add('show');

    try {{
        const resp = await fetch('/api/refresh', {{ method: 'POST' }});
        if (resp.status === 409) {{
            detail.textContent = '已有采集任务在运行，等待完成...';
        }} else if (!resp.ok) {{
            throw new Error('Server error');
        }}

        // Poll status
        const poll = setInterval(async () => {{
            try {{
                const sr = await fetch('/api/status');
                const st = await sr.json();

                const stageMap = {{
                    'starting': ['正在启动采集...', 5],
                    'collecting': ['正在从各平台采集帖子...', 30],
                    'filtering': ['正在预筛帖子...', 50],
                    'ranking': ['正在计算排名...', 70],
                    'generating_dashboard': ['正在生成看板...', 90],
                    'done': ['刷新完成！', 100],
                }};
                const [msg, pct] = stageMap[st.stage] || [st.stage, 50];
                detail.textContent = msg;
                barFill.style.width = pct + '%';

                // Show latest output line
                if (st.output && st.output.length > 0) {{
                    const lastLine = st.output[st.output.length - 1];
                    if (lastLine && lastLine.trim()) {{
                        detail.textContent = msg + ' | ' + lastLine.substring(0, 60);
                    }}
                }}

                if (st.stage === 'done') {{
                    clearInterval(poll);
                    barFill.style.width = '100%';
                    detail.textContent = st.error ? '出错: ' + st.error : '刷新完成！';
                    setTimeout(() => {{
                        overlay.classList.remove('show');
                        location.reload();
                    }}, 1000);
                }}
            }} catch (e) {{
                /* ignore poll errors */
            }}
        }}, 1500);

    }} catch (e) {{
        // Server not running — fallback to page reload
        detail.textContent = '本地服务器未运行，正在刷新页面...';
        setTimeout(() => {{
            overlay.classList.remove('show');
            location.reload();
        }}, 1500);
    }}
}}

// ===== 诉求提交 =====
function openRequestModal() {{
    document.getElementById('requestModal').classList.add('show');
    document.getElementById('reqDescription').focus();
    document.getElementById('submitMsg').textContent = '';
    document.getElementById('submitMsg').className = 'modal-msg';
}}

function closeRequestModal() {{
    document.getElementById('requestModal').classList.remove('show');
}}

document.getElementById('requestModal').addEventListener('click', function(e) {{
    if (e.target === this) closeRequestModal();
}});

document.addEventListener('keydown', function(e) {{
    if (e.key === 'Escape') closeRequestModal();
}});

async function submitRequest() {{
    const desc = document.getElementById('reqDescription').value.trim();
    const email = document.getElementById('reqEmail').value.trim();
    const btn = document.getElementById('submitBtn');
    const msg = document.getElementById('submitMsg');

    if (desc.length < 5) {{
        msg.textContent = '请至少输入5个字描述你的需求';
        msg.className = 'modal-msg error';
        return;
    }}
    if (desc.length > 1000) {{
        msg.textContent = '描述不能超过1000字';
        msg.className = 'modal-msg error';
        return;
    }}
    if (email && !email.includes('@')) {{
        msg.textContent = '邮箱格式不正确';
        msg.className = 'modal-msg error';
        return;
    }}

    btn.disabled = true;
    btn.textContent = '提交中...';
    msg.textContent = '';
    msg.className = 'modal-msg';

    try {{
        const resp = await fetch('/api/submit-request', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ description: desc, email: email || null }})
        }});
        const data = await resp.json();
        if (resp.ok) {{
            msg.textContent = '✅ ' + (data.message || '诉求已提交，感谢你的参与！');
            msg.className = 'modal-msg success';
            document.getElementById('reqDescription').value = '';
            document.getElementById('reqEmail').value = '';
            setTimeout(closeRequestModal, 2000);
        }} else {{
            msg.textContent = '❌ ' + (data.error || '提交失败，请重试');
            msg.className = 'modal-msg error';
        }}
    }} catch (e) {{
        msg.textContent = '❌ 网络错误，请稍后重试';
        msg.className = 'modal-msg error';
    }} finally {{
        btn.disabled = false;
        btn.textContent = '🚀 提交诉求';
    }}
}}

// ===== 初始化 =====
renderHeader();
renderTable();
renderDist();
renderTrends();
</script>

</body>
</html>"""
