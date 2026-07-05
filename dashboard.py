"""
dashboard.py - 卡片式交互看板生成器
浅色主题、卡片展示、点击展开原文、分类筛选
"""
import json
from datetime import datetime
from config import DASHBOARD_PATH, DASHBOARD_TOP_N
from database import get_pain_points_with_posts, get_stats


def generate_dashboard(conn):
    """生成HTML看板"""
    pain_points = get_pain_points_with_posts(conn, limit=DASHBOARD_TOP_N * 3)
    stats = get_stats(conn)

    # 分类中文映射
    cat_names = {
        "work": "工作职场", "study": "学习考试", "life": "日常生活",
        "health": "医疗健康", "shopping": "购物消费", "office": "办公文档",
        "travel": "出行旅游", "finance": "理财记账", "internet": "网络工具",
        "phone": "手机应用", "computer": "电脑软件", "other": "其他",
    }

    # 构建分类分布
    cat_dist = {}
    for pp in pain_points:
        cat = pp.get("category", "other")
        name = cat_names.get(cat, cat)
        cat_dist[name] = cat_dist.get(name, 0) + 1

    # 按分类分组
    grouped = {}
    for pp in pain_points:
        cat = pp.get("category", "other")
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(pp)

    dashboard_data = {
        "pain_points": pain_points,
        "grouped": grouped,
        "stats": stats,
        "cat_dist": cat_dist,
        "cat_names": cat_names,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    html = _build_html(dashboard_data)
    with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    return DASHBOARD_PATH


def _build_html(data):
    data_json = json.dumps(data, ensure_ascii=False, default=str)
    return _HTML_TEMPLATE.replace("__DATA_PLACEHOLDER__", data_json)


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>大众痛点收集 · 日常需求看板</title>
<style>
:root {
    --bg: #f8f9fa;
    --card-bg: #fff;
    --text: #212529;
    --text-secondary: #6c757d;
    --text-muted: #adb5bd;
    --border: #e9ecef;
    --accent: #4361ee;
    --accent-light: #eef0ff;
    --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
    --shadow-hover: 0 4px 12px rgba(0,0,0,0.08);
    --radius: 10px;
    --radius-sm: 6px;
}

* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
        "Microsoft YaHei", "Helvetica Neue", sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
}

/* ===== Header ===== */
.header {
    background: #fff;
    border-bottom: 1px solid var(--border);
    padding: 16px 0;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.header-inner {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
}
.header-left { display: flex; align-items: center; gap: 12px; }
.logo {
    width: 40px; height: 40px;
    background: linear-gradient(135deg, #4361ee, #7209b7);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    color: #fff; font-weight: 800; font-size: 16px;
    flex-shrink: 0;
}
.header h1 { font-size: 20px; font-weight: 700; color: #212529; }
.header-sub { font-size: 13px; color: var(--text-secondary); }

/* ===== Banner Slogan ===== */
.banner-slogan {
    flex: 1;
    text-align: center;
    padding: 0 20px;
}
.banner-slogan .slogan-main {
    font-size: 22px;
    font-weight: 800;
    background: linear-gradient(135deg, #ff6b6b, #ee5a6f, #f06595);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1.3;
    letter-spacing: 1px;
}
.banner-slogan .slogan-sub {
    font-size: 13px;
    color: var(--text-secondary);
    margin-top: 2px;
}
.banner-slogan .slogan-sub strong {
    color: #e64980;
}

/* ===== Submit Button ===== */
.btn-submit {
    background: linear-gradient(135deg, #ff6b6b, #ee5a6f);
    color: #fff;
    border: none;
    border-radius: 25px;
    padding: 10px 24px;
    font-size: 15px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.3s;
    box-shadow: 0 4px 14px rgba(238,90,111,0.35);
    white-space: nowrap;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
}
.btn-submit:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(238,90,111,0.45);
}
.btn-submit:active { transform: translateY(0); }
.btn-submit .pulse-dot {
    width: 8px; height: 8px;
    background: #fff;
    border-radius: 50%;
    animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.5; transform: scale(1.3); }
}

.stats-inline {
    display: flex; gap: 16px; flex-wrap: wrap;
    align-items: center;
}
.stat-mini {
    font-size: 13px; color: var(--text-secondary);
}
.stat-mini strong { color: var(--accent); font-size: 16px; }

/* ===== Modal ===== */
.modal-overlay {
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.5);
    z-index: 1000;
    align-items: center;
    justify-content: center;
    padding: 20px;
    backdrop-filter: blur(4px);
}
.modal-overlay.show { display: flex; }
.modal-box {
    background: #fff;
    border-radius: 16px;
    max-width: 560px;
    width: 100%;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 20px 60px rgba(0,0,0,0.15);
    animation: modalIn 0.3s ease;
}
@keyframes modalIn {
    from { opacity: 0; transform: scale(0.95) translateY(10px); }
    to { opacity: 1; transform: scale(1) translateY(0); }
}
.modal-header {
    background: linear-gradient(135deg, #ff6b6b, #ee5a6f);
    color: #fff;
    padding: 24px 28px;
    border-radius: 16px 16px 0 0;
}
.modal-header h2 { font-size: 22px; font-weight: 700; margin-bottom: 6px; }
.modal-header p { font-size: 14px; opacity: 0.9; line-height: 1.5; }
.modal-body { padding: 28px; }
.modal-close {
    float: right;
    font-size: 24px;
    cursor: pointer;
    opacity: 0.8;
    line-height: 1;
    background: none;
    border: none;
    color: #fff;
}
.modal-close:hover { opacity: 1; }

.form-group { margin-bottom: 20px; }
.form-label {
    display: block;
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 8px;
}
.form-label .required { color: #e64980; }
.form-label .optional { color: var(--text-muted); font-weight: 400; font-size: 12px; }
.form-hint {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 6px;
    line-height: 1.5;
}
.form-textarea {
    width: 100%;
    min-height: 120px;
    padding: 12px 16px;
    border: 2px solid var(--border);
    border-radius: 10px;
    font-size: 14px;
    font-family: inherit;
    resize: vertical;
    outline: none;
    transition: border-color 0.2s;
    line-height: 1.6;
}
.form-textarea:focus { border-color: #ff6b6b; }
.form-input {
    width: 100%;
    padding: 12px 16px;
    border: 2px solid var(--border);
    border-radius: 10px;
    font-size: 14px;
    outline: none;
    transition: border-color 0.2s;
}
.form-input:focus { border-color: #ff6b6b; }
.form-tag-row {
    display: flex; gap: 8px; flex-wrap: wrap;
    margin-top: 8px;
}
.form-tag {
    font-size: 12px;
    padding: 4px 12px;
    border-radius: 14px;
    background: var(--bg);
    color: var(--text-secondary);
    cursor: pointer;
    border: 1px solid var(--border);
    transition: all 0.2s;
}
.form-tag:hover { border-color: #ff6b6b; color: #ff6b6b; }

.btn-submit-form {
    width: 100%;
    background: linear-gradient(135deg, #ff6b6b, #ee5a6f);
    color: #fff;
    border: none;
    border-radius: 10px;
    padding: 14px;
    font-size: 16px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.2s;
    margin-top: 8px;
}
.btn-submit-form:hover { opacity: 0.9; }
.btn-submit-form:disabled { opacity: 0.5; cursor: not-allowed; }

.modal-success {
    text-align: center;
    padding: 40px 28px;
}
.modal-success .success-icon {
    font-size: 56px;
    margin-bottom: 16px;
}
.modal-success h3 { font-size: 20px; margin-bottom: 8px; }
.modal-success p { font-size: 14px; color: var(--text-secondary); line-height: 1.6; }

/* ===== User Requests Section ===== */
.user-requests-section {
    background: linear-gradient(135deg, #fff5f5, #fff0f3);
    border: 1px solid #ffe0e6;
    border-radius: var(--radius);
    padding: 20px 24px;
    margin-bottom: 24px;
}
.ur-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;
}
.ur-header h2 { font-size: 16px; font-weight: 700; }
.ur-count {
    background: linear-gradient(135deg, #ff6b6b, #ee5a6f);
    color: #fff;
    font-size: 13px;
    font-weight: 700;
    padding: 3px 12px;
    border-radius: 14px;
}
.ur-list {
    display: flex;
    gap: 10px;
    overflow-x: auto;
    padding-bottom: 6px;
}
.ur-list::-webkit-scrollbar { height: 4px; }
.ur-list::-webkit-scrollbar-thumb { background: #ffc9cc; border-radius: 2px; }
.ur-item {
    background: #fff;
    border: 1px solid #ffe0e6;
    border-radius: 8px;
    padding: 10px 14px;
    min-width: 260px;
    max-width: 300px;
    flex-shrink: 0;
}
.ur-item-text {
    font-size: 13px;
    color: var(--text);
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
.ur-item-time {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 6px;
}

/* ===== Container ===== */
.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px 24px;
}

/* ===== Filters ===== */
.filter-bar {
    display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
    margin-bottom: 20px;
    padding: 0;
}
.cat-btn {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 6px 16px;
    font-size: 13px;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
}
.cat-btn:hover { border-color: var(--accent); color: var(--accent); }
.cat-btn.active {
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
    font-weight: 600;
}
.cat-btn .count {
    font-size: 11px;
    opacity: 0.7;
    margin-left: 4px;
}
.search-box {
    margin-left: auto;
    padding: 7px 14px;
    border: 1px solid var(--border);
    border-radius: 20px;
    font-size: 13px;
    width: 200px;
    outline: none;
    transition: border-color 0.2s;
}
.search-box:focus { border-color: var(--accent); }
.search-box::placeholder { color: var(--text-muted); }

/* ===== Category Sections ===== */
.cat-section { margin-bottom: 28px; }
.cat-header {
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--border);
}
.cat-header h2 {
    font-size: 17px; font-weight: 700;
    display: flex; align-items: center; gap: 6px;
}
.cat-count {
    font-size: 13px; color: var(--text-muted);
    font-weight: 400;
}

/* ===== Cards — Simplified ===== */
.cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
    gap: 10px;
}
.pain-card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 14px 16px;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: var(--shadow);
    position: relative;
}
.pain-card:hover {
    box-shadow: var(--shadow-hover);
    transform: translateY(-1px);
}
.pain-card.expanded {
    border-color: var(--accent);
    box-shadow: 0 4px 16px rgba(67,97,238,0.1);
}

/* Card collapsed view — minimal */
.card-collapsed {
    display: flex;
    align-items: flex-start;
    gap: 10px;
}
.card-num {
    width: 24px; height: 24px;
    background: var(--bg);
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 700;
    color: var(--text-muted);
    flex-shrink: 0;
    margin-top: 2px;
}
.card-main {
    flex: 1;
    min-width: 0;
}
.card-title {
    font-size: 14px; font-weight: 600;
    color: var(--text);
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    margin-bottom: 6px;
}
.card-tags {
    display: flex; align-items: center; gap: 8px;
    flex-wrap: wrap;
    font-size: 12px;
    color: var(--text-muted);
}
.cat-badge {
    display: inline-flex; align-items: center;
    padding: 2px 10px; border-radius: 12px;
    font-size: 11px; font-weight: 600;
    white-space: nowrap;
}
.cat-work { background: #e3f2fd; color: #1565c0; }
.cat-study { background: #fff3e0; color: #e65100; }
.cat-life { background: #fce4ec; color: #c62828; }
.cat-health { background: #e8f5e9; color: #2e7d32; }
.cat-shopping { background: #f3e5f5; color: #7b1fa2; }
.cat-office { background: #e0f2f1; color: #00695c; }
.cat-travel { background: #e8eaf6; color: #283593; }
.cat-finance { background: #fff8e1; color: #f57f17; }
.cat-internet { background: #e0f7fa; color: #00838f; }
.cat-phone { background: #fce4ec; color: #ad1457; }
.cat-computer { background: #eceff1; color: #455a64; }
.cat-other { background: #f5f5f5; color: #757575; }

.platform-badge {
    font-size: 11px; color: var(--text-muted);
}
.en-badge {
    font-size: 10px; background: #f0f5ff; color: #4361ee;
    padding: 1px 6px; border-radius: 8px;
    font-weight: 500;
}
.expand-arrow {
    font-size: 12px; color: var(--text-muted);
    margin-left: auto;
    transition: transform 0.2s;
}
.pain-card.expanded .expand-arrow {
    transform: rotate(180deg);
}

/* ===== Expanded Detail ===== */
.card-detail {
    display: none;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--border);
}
.pain-card.expanded .card-detail { display: block; }
.detail-section { margin-bottom: 12px; }
.detail-section:last-child { margin-bottom: 0; }
.detail-label {
    font-size: 11px; font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
}
.detail-text {
    font-size: 14px; color: var(--text);
    line-height: 1.7;
    white-space: pre-wrap;
    word-break: break-word;
}
.detail-text.original {
    font-size: 13px;
    color: var(--text-secondary);
    background: #f8f9fa;
    padding: 12px;
    border-radius: var(--radius-sm);
    border-left: 3px solid #dee2e6;
    font-style: italic;
    max-height: 200px;
    overflow-y: auto;
}
.detail-reason {
    font-size: 13px; color: var(--text-secondary);
    line-height: 1.6;
}
.detail-keywords {
    display: flex; gap: 4px; flex-wrap: wrap;
}
.detail-kw {
    font-size: 12px; color: var(--text-secondary);
    background: #f1f3f5;
    padding: 3px 10px;
    border-radius: 4px;
}
.detail-feas {
    display: flex; align-items: center; gap: 8px;
    font-size: 14px;
}
.feas-stars {
    color: #ffc107;
    letter-spacing: 2px;
}
.feas-stars .empty { color: #e9ecef; }
.source-link {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 13px; color: var(--accent);
    text-decoration: none;
    font-weight: 500;
    margin-top: 4px;
}
.source-link:hover { text-decoration: underline; }
.source-link::after { content: ' ↗'; font-size: 12px; }

/* ===== Empty ===== */
.empty {
    text-align: center; padding: 60px 20px;
    color: var(--text-muted); font-size: 15px;
}
.empty-icon { font-size: 40px; margin-bottom: 12px; }

/* ===== Reward / Donate Section ===== */
.reward-section {
    background: linear-gradient(135deg, #fff9f0, #fff3e6);
    border: 1px solid #ffe0c2;
    border-radius: 14px;
    padding: 28px 24px;
    margin-top: 36px;
    text-align: center;
}
.reward-title {
    font-size: 18px; font-weight: 700;
    color: #d4380d; margin-bottom: 16px;
    display: flex; align-items: center; justify-content: center; gap: 8px;
}
.reward-qrs {
    display: flex; gap: 32px; justify-content: center; flex-wrap: wrap;
}
.reward-item { text-align: center; }
.reward-label {
    font-size: 13px; font-weight: 600;
    margin-top: 10px; margin-bottom: 2px;
}
.reward-alipay { color: #1677ff; }
.reward-wechat { color: #07c160; }
.reward-img {
    width: 180px; height: 180px;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    object-fit: cover;
    transition: transform 0.2s;
}
.reward-img:hover {
    transform: scale(1.05);
    cursor: pointer;
}

/* ===== Footer ===== */
.footer {
    text-align: center; padding: 24px;
    font-size: 12px; color: var(--text-muted);
    border-top: 1px solid var(--border);
    margin-top: 40px;
}

/* ===== Responsive ===== */
@media (max-width: 768px) {
    .cards-grid { grid-template-columns: 1fr; }
    .header-inner { padding: 0 16px; }
    .search-box { width: 140px; }
    .cat-section { margin-bottom: 20px; }
    .banner-slogan { width: 100%; order: 3; padding: 0; }
    .banner-slogan .slogan-main { font-size: 16px; }
    .banner-slogan .slogan-sub { font-size: 12px; }
    .stats-inline { width: 100%; justify-content: space-between; }
    .btn-submit { padding: 8px 18px; font-size: 14px; }
    .modal-box { border-radius: 12px; }
    .modal-header { padding: 20px; }
    .modal-body { padding: 20px; }
    .ur-item { min-width: 220px; }
}
</style>
</head>
<body>

<div class="header">
    <div class="header-inner">
        <div class="header-left">
            <div class="logo">📋</div>
            <div>
                <h1>大众痛点收集</h1>
                <div class="header-sub" id="lastUpdated"></div>
            </div>
        </div>
        <div class="banner-slogan">
            <div class="slogan-main">你的诉求，我来实现！</div>
            <div class="slogan-sub">说出你生活工作中的困扰，用代码帮你解决 · <strong>参与即享首批内测资格</strong></div>
        </div>
        <div class="stats-inline">
            <div class="stat-mini">痛点 <strong id="statPP">0</strong></div>
            <div class="stat-mini">帖子 <strong id="statPosts">0</strong></div>
            <button class="btn-submit" onclick="openModal()">
                <span class="pulse-dot"></span> 我有诉求
            </button>
        </div>
    </div>
</div>

<!-- Submit Modal -->
<div class="modal-overlay" id="submitModal" onclick="closeModalOnOverlay(event)">
    <div class="modal-box">
        <div class="modal-header">
            <button class="modal-close" onclick="closeModal()">&times;</button>
            <h2>📝 提交你的诉求</h2>
            <p>遇到了什么困扰？希望有什么工具能帮你解决？每一条诉求我们都会认真对待，优秀的想法将直接变成开发项目！</p>
        </div>
        <div class="modal-body" id="modalBody">
            <div class="form-group">
                <label class="form-label">描述你的诉求 <span class="required">*</span></label>
                <textarea class="form-textarea" id="reqDesc" placeholder="比如：每次整理发票都要手动分类，太费时间了，希望有个工具能自动识别分类..." maxlength="1000"></textarea>
                <div class="form-hint">越具体越好！说说你遇到了什么问题，你期望什么样的解决方案。</div>
                <div class="form-tag-row">
                    <span class="form-tag" onclick="quickFill('工作办公')">💼 工作办公</span>
                    <span class="form-tag" onclick="quickFill('学习考试')">📚 学习考试</span>
                    <span class="form-tag" onclick="quickFill('日常生活')">🏠 日常生活</span>
                    <span class="form-tag" onclick="quickFill('购物消费')">🛒 购物消费</span>
                    <span class="form-tag" onclick="quickFill('其他')">📌 其他</span>
                </div>
            </div>
            <div class="form-group">
                <label class="form-label">邮箱 <span class="optional">（选填，用于内测通知）</span></label>
                <input type="email" class="form-input" id="reqEmail" placeholder="your@email.com">
                <div class="form-hint">留下邮箱，项目上线后你将作为<strong>首批内测用户</strong>第一时间收到通知。我们承诺不会用于其他用途。</div>
            </div>
            <button class="btn-submit-form" id="submitBtn" onclick="submitRequest()">提交诉求</button>
        </div>
    </div>
</div>

<div class="container">
    <!-- User Submitted Requests -->
    <div class="user-requests-section" id="userRequestsSection" style="display:none;">
        <div class="ur-header">
            <h2>🗣️ 大家都在说</h2>
            <span class="ur-count" id="urCount">0 人参与</span>
        </div>
        <div class="ur-list" id="urList"></div>
    </div>

    <!-- Filters -->
    <div class="filter-bar" id="catFilters"></div>

    <!-- Pain Point Cards by Category -->
    <div id="cardContainer"></div>
    <div class="empty" id="emptyMsg" style="display:none;">
        <div class="empty-icon">📭</div>
        暂无痛点数据，请先运行采集和注入流程
    </div>
</div>

<!-- Reward / Donate -->
<div class="reward-section">
    <div class="reward-title">☕ 觉得有用？请作者喝杯咖啡吧</div>
    <div class="reward-qrs">
        <div class="reward-item">
            <img src="/static/reward_wechat.jpg" alt="微信打赏" class="reward-img">
            <div class="reward-label reward-wechat">💚 微信支付</div>
        </div>
        <div class="reward-item">
            <img src="/static/reward_alipay.jpg" alt="支付宝打赏" class="reward-img">
            <div class="reward-label reward-alipay">💙 支付宝</div>
        </div>
    </div>
</div>

<div class="footer">
    大众痛点收集器 · 聚焦日常工作、学习、生活中的真实需求 · 你的每一个诉求都可能成为下一个项目 💡
</div>

<script>
const DATA = __DATA_PLACEHOLDER__;
const catNames = DATA.cat_names || {};
const groupedData = DATA.grouped || {};
const catDist = DATA.cat_dist || {};

let activeCat = 'all';
let searchQuery = '';

// ===== Init =====
document.getElementById('lastUpdated').textContent = '更新：' + (DATA.last_updated || '');
document.getElementById('statPP').textContent = DATA.stats.total_pain_points || 0;
document.getElementById('statPosts').textContent = DATA.stats.total_posts || 0;

// ===== Category definition & order =====
const catOrder = ['work','study','life','health','office','shopping','travel','finance','internet','phone','computer','other'];

// Build filter bar
function renderFilters() {
    const bar = document.getElementById('catFilters');
    let html = '<button class="cat-btn active" data-cat="all">全部<span class="count">' +
        (DATA.pain_points || []).length + '</span></button>';

    catOrder.forEach(cat => {
        const list = groupedData[cat] || [];
        if (list.length === 0) return;
        const name = catNames[cat] || cat;
        html += '<button class="cat-btn" data-cat="' + cat + '">' + name +
            '<span class="count">' + list.length + '</span></button>';
    });

    html += '<input type="text" class="search-box" id="searchBox" placeholder="🔍 搜索痛点...">';
    bar.innerHTML = html;

    bar.querySelectorAll('.cat-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            bar.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeCat = btn.dataset.cat;
            renderCards();
        });
    });

    document.getElementById('searchBox').addEventListener('input', e => {
        searchQuery = e.target.value.toLowerCase().trim();
        renderCards();
    });
}

// ===== Render Cards =====
function renderCards() {
    const container = document.getElementById('cardContainer');
    let html = '';
    let totalVisible = 0;
    let cardIndex = 0;

    if (activeCat === 'all') {
        catOrder.forEach(cat => {
            const list = groupedData[cat] || [];
            if (list.length === 0) return;

            const filtered = list.filter(matchesSearch);
            if (filtered.length === 0) return;

            const catName = catNames[cat] || cat;
            html += '<div class="cat-section">';
            html += '<div class="cat-header"><h2>' + getCatEmoji(cat) + ' ' + catName +
                '<span class="cat-count">' + filtered.length + ' 个痛点</span></h2></div>';
            html += '<div class="cards-grid">';
            filtered.forEach(pp => {
                html += renderCard(pp, ++cardIndex);
                totalVisible++;
            });
            html += '</div></div>';
        });
    } else {
        const list = groupedData[activeCat] || [];
        const filtered = list.filter(matchesSearch);
        if (filtered.length > 0) {
            const catName = catNames[activeCat] || activeCat;
            html += '<div class="cat-section">';
            html += '<div class="cat-header"><h2>' + getCatEmoji(activeCat) + ' ' + catName +
                '<span class="cat-count">' + filtered.length + ' 个痛点</span></h2></div>';
            html += '<div class="cards-grid">';
            filtered.forEach(pp => {
                html += renderCard(pp, ++cardIndex);
                totalVisible++;
            });
            html += '</div></div>';
        }
    }

    if (totalVisible === 0) {
        container.innerHTML = '';
        document.getElementById('emptyMsg').style.display = 'block';
    } else {
        container.innerHTML = html;
        document.getElementById('emptyMsg').style.display = 'none';
    }
}

function matchesSearch(pp) {
    if (!searchQuery) return true;
    const desc = (pp.description || '').toLowerCase();
    const kw = (pp.keywords || '').toLowerCase();
    const title = (pp.title || '').toLowerCase();
    const orig = (pp.original_text || '').toLowerCase();
    return desc.includes(searchQuery) || kw.includes(searchQuery) ||
        title.includes(searchQuery) || orig.includes(searchQuery);
}

function getCatEmoji(cat) {
    const m = { work: '💼', study: '📚', life: '🏠', health: '🏥',
        office: '📄', shopping: '🛒', travel: '✈️', finance: '💰',
        internet: '🌐', phone: '📱', computer: '💻', other: '📌' };
    return m[cat] || '📌';
}

function getCatBadgeClass(cat) {
    return 'cat-badge cat-' + (cat || 'other');
}

function getPlatformName(platform) {
    const m = { v2ex: 'V2EX', douyin: '抖音', weibo: '微博', baidu: '百度',
        hackernews: 'HN', reddit: 'Reddit', stackoverflow: 'SO', producthunt: 'PH',
        user_request: '用户诉求' };
    return m[platform] || platform || '未知';
}

function renderFeasStars(score) {
    const s = parseInt(score) || 3;
    let html = '<span class="feas-stars">';
    for (let i = 1; i <= 5; i++) {
        html += i <= s ? '★' : '<span class="empty">★</span>';
    }
    html += '</span>';
    return html;
}

function renderCard(pp, idx) {
    const cat = pp.category || 'other';
    const desc = pp.description || pp.title || '';
    const isEnglish = pp.is_english;
    const origText = pp.original_text || '';
    const keywords = (pp.keywords || '').split(',').filter(k => k.trim()).slice(0, 6);
    const platform = pp.platform || '';

    // Collapsed view — minimal
    let html = '<div class="pain-card" onclick="toggleCard(this)" data-index="' + idx + '">';
    html += '<div class="card-collapsed">';
    html += '<div class="card-num">' + idx + '</div>';
    html += '<div class="card-main">';
    html += '<div class="card-title">' + escapeHtml(desc) + '</div>';
    html += '<div class="card-tags">';
    html += '<span class="' + getCatBadgeClass(cat) + '">' + (catNames[cat] || cat) + '</span>';
    html += '<span class="platform-badge">' + getPlatformName(platform) + '</span>';
    if (isEnglish || origText) {
        html += '<span class="en-badge">EN</span>';
    }
    html += '<span class="expand-arrow">▼</span>';
    html += '</div>'; // card-tags
    html += '</div>'; // card-main
    html += '</div>'; // card-collapsed

    // Expanded detail
    html += '<div class="card-detail">';

    // Full description
    html += '<div class="detail-section">';
    html += '<div class="detail-label">📝 详细描述</div>';
    html += '<div class="detail-text">' + escapeHtml(desc) + '</div>';
    html += '</div>';

    // Original English text
    if (origText) {
        html += '<div class="detail-section">';
        html += '<div class="detail-label">🌍 英文原文</div>';
        html += '<div class="detail-text original">' + escapeHtml(origText) + '</div>';
        html += '</div>';
    }

    // Keywords
    if (keywords.length > 0) {
        html += '<div class="detail-section">';
        html += '<div class="detail-label">🏷️ 关键词</div>';
        html += '<div class="detail-keywords">';
        keywords.forEach(k => {
            html += '<span class="detail-kw">' + escapeHtml(k.trim()) + '</span>';
        });
        html += '</div>';
        html += '</div>';
    }

    // Feasibility
    html += '<div class="detail-section">';
    html += '<div class="detail-label">💡 可编程解决可行性</div>';
    html += '<div class="detail-feas">' + renderFeasStars(pp.feasibility) +
        ' <span style="font-size:12px;color:var(--text-muted)">' +
        escapeHtml(pp.feasibility_reason || '') + '</span></div>';
    html += '</div>';

    // Source link
    if (pp.url) {
        html += '<div class="detail-section">';
        html += '<a class="source-link" href="' + pp.url +
            '" target="_blank" rel="noopener">查看原始帖子 (' +
            getPlatformName(platform) + ')</a>';
        html += '</div>';
    }

    html += '</div>'; // card-detail
    html += '</div>'; // pain-card
    return html;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function toggleCard(card) {
    card.classList.toggle('expanded');
}

// ===== Init =====
renderFilters();
renderCards();

// ===== User Request Modal =====
function openModal() {
    document.getElementById('submitModal').classList.add('show');
    document.body.style.overflow = 'hidden';
}

function closeModal() {
    document.getElementById('submitModal').classList.remove('show');
    document.body.style.overflow = '';
}

function closeModalOnOverlay(event) {
    if (event.target === document.getElementById('submitModal')) {
        closeModal();
    }
}

function quickFill(category) {
    const ta = document.getElementById('reqDesc');
    const prefixes = {
        '工作办公': '【工作办公】',
        '学习考试': '【学习考试】',
        '日常生活': '【日常生活】',
        '购物消费': '【购物消费】',
        '其他': '【其他】'
    };
    const prefix = prefixes[category] || '';
    if (!ta.value.startsWith(prefix)) {
        ta.value = prefix + ta.value.replace(/^【.*?】/, '');
    }
    ta.focus();
}

function submitRequest() {
    const desc = document.getElementById('reqDesc').value.trim();
    const email = document.getElementById('reqEmail').value.trim();
    const btn = document.getElementById('submitBtn');

    if (!desc || desc.length < 5) {
        alert('请至少输入5个字描述你的诉求');
        return;
    }
    if (desc.length > 1000) {
        alert('描述不能超过1000字');
        return;
    }
    if (email && !/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email)) {
        alert('邮箱格式不正确');
        return;
    }

    btn.disabled = true;
    btn.textContent = '提交中...';

    fetch('/api/submit-request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: desc, email: email })
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) {
            alert(data.error);
            btn.disabled = false;
            btn.textContent = '提交诉求';
            return;
        }
        // Show success
        document.getElementById('modalBody').innerHTML = `
            <div class="modal-success">
                <div class="success-icon">🎉</div>
                <h3>诉求已提交！</h3>
                <p>感谢你的参与！你的想法对我们非常重要。<br>项目上线后，你将作为首批内测用户收到通知。</p>
                <button class="btn-submit-form" style="margin-top:20px;" onclick="closeModal();resetModal();">完成</button>
            </div>
        `;
        loadUserRequests();
    })
    .catch(err => {
        alert('网络错误，请稍后重试');
        btn.disabled = false;
        btn.textContent = '提交诉求';
    });
}

function resetModal() {
    document.getElementById('modalBody').innerHTML = `
        <div class="form-group">
            <label class="form-label">描述你的诉求 <span class="required">*</span></label>
            <textarea class="form-textarea" id="reqDesc" placeholder="比如：每次整理发票都要手动分类，太费时间了，希望有个工具能自动识别分类..." maxlength="1000"></textarea>
            <div class="form-hint">越具体越好！说说你遇到了什么问题，你期望什么样的解决方案。</div>
            <div class="form-tag-row">
                <span class="form-tag" onclick="quickFill('工作办公')">💼 工作办公</span>
                <span class="form-tag" onclick="quickFill('学习考试')">📚 学习考试</span>
                <span class="form-tag" onclick="quickFill('日常生活')">🏠 日常生活</span>
                <span class="form-tag" onclick="quickFill('购物消费')">🛒 购物消费</span>
                <span class="form-tag" onclick="quickFill('其他')">📌 其他</span>
            </div>
        </div>
        <div class="form-group">
            <label class="form-label">邮箱 <span class="optional">（选填，用于内测通知）</span></label>
            <input type="email" class="form-input" id="reqEmail" placeholder="your@email.com">
            <div class="form-hint">留下邮箱，项目上线后你将作为<strong>首批内测用户</strong>第一时间收到通知。我们承诺不会用于其他用途。</div>
        </div>
        <button class="btn-submit-form" id="submitBtn" onclick="submitRequest()">提交诉求</button>
    `;
}

// ===== Load User Requests =====
function loadUserRequests() {
    fetch('/api/user-requests')
    .then(r => r.json())
    .then(data => {
        if (!data.total || data.total === 0) return;
        document.getElementById('userRequestsSection').style.display = 'block';
        document.getElementById('urCount').textContent = data.total + ' 人参与';

        const list = document.getElementById('urList');
        list.innerHTML = data.requests.map(r => {
            const time = formatTime(r.created_at);
            return '<div class="ur-item">' +
                '<div class="ur-item-text">' + escapeHtml(r.description) + '</div>' +
                '<div class="ur-item-time">' + time + '</div>' +
                '</div>';
        }).join('');
    })
    .catch(() => {});
}

function formatTime(isoStr) {
    try {
        const d = new Date(isoStr);
        const now = new Date();
        const diff = (now - d) / 1000;
        if (diff < 60) return '刚刚';
        if (diff < 3600) return Math.floor(diff / 60) + '分钟前';
        if (diff < 86400) return Math.floor(diff / 3600) + '小时前';
        if (diff < 604800) return Math.floor(diff / 86400) + '天前';
        return d.toLocaleDateString('zh-CN');
    } catch(e) { return ''; }
}

// Load on page init
loadUserRequests();
</script>
</body>
</html>"""
