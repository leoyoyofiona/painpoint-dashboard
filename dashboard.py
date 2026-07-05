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
    padding: 20px 0;
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
}
.header h1 { font-size: 20px; font-weight: 700; color: #212529; }
.header-sub { font-size: 13px; color: var(--text-secondary); }
.stats-inline {
    display: flex; gap: 16px; flex-wrap: wrap;
}
.stat-mini {
    font-size: 13px; color: var(--text-secondary);
}
.stat-mini strong { color: var(--accent); font-size: 16px; }

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
        <div class="stats-inline">
            <div class="stat-mini">痛点 <strong id="statPP">0</strong></div>
            <div class="stat-mini">帖子 <strong id="statPosts">0</strong></div>
            <div class="stat-mini">今日采集 <strong id="statToday">0</strong></div>
        </div>
    </div>
</div>

<div class="container">
    <!-- Filters -->
    <div class="filter-bar" id="catFilters"></div>

    <!-- Pain Point Cards by Category -->
    <div id="cardContainer"></div>
    <div class="empty" id="emptyMsg" style="display:none;">
        <div class="empty-icon">📭</div>
        暂无痛点数据，请先运行采集和注入流程
    </div>
</div>

<div class="footer">
    大众痛点收集器 · 聚焦日常工作、学习、生活中的真实需求 · 数据来源：抖音/V2EX/微博/百度/HN/Reddit/SO/PH
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
document.getElementById('statToday').textContent = DATA.stats.posts_today || 0;

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
        hackernews: 'HN', reddit: 'Reddit', stackoverflow: 'SO', producthunt: 'PH' };
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
</script>
</body>
</html>"""
