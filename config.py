"""
config.py - 痛点收集器全局配置
所有配置常量集中管理，修改阈值/关键词/API端点只需改这一个文件
"""

import os

# ============================================================
# 路径配置
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "painpoints.db")
DASHBOARD_PATH = os.path.join(BASE_DIR, "dashboard.html")

# ============================================================
# 采集平台配置
# ============================================================

# --- V2EX (深度挖掘所有生活类节点) ---
V2EX_ENDPOINTS = [
    "https://www.v2ex.com/api/topics/latest.json",
]
V2EX_INTERVAL = 3
V2EX_TIMEOUT = 15
V2EX_RELEVANT_NODES = {
    # 问答求助
    "qna", "share", "life", "ideas", "create",
    # 电脑日常使用
    "macos", "windows", "android", "iphone", "chrome", "firefox",
    "hardware", "mbp", "surface", "thinkpad",
    # 日常软件工具
    "notion", "evernote", "dropbox", "ifttt", "trello", "alfred",
    "wunderlist", "omnifocus", "taskade", "logseq",
    # 效率/方法
    "gtd", "pomodoro", "productivity", "tools", "notes",
    # 工作求职
    "work", "career", "jobs", "entrepreneur", "business",
    "pm", "freelance", "remote",
    # 理财消费
    "money", "invest", "finance", "shopping", "free",
    "coupon-hunting", "cheap", "buy", "creditcard",
    # 学习教育
    "education", "learn", "reading", "writing", "english",
    "math", "ielts", "toefl", "book",
    # 生活日常
    "diet", "cook", "food", "health", "sleep",
    "fitness", "bike", "sports", "running", "outdoor",
    "travel", "car", "rent", "home", "lifestyle",
    "dating", "love", "parenting", "family",
    # 影音娱乐
    "music", "movie", "photograph", "game", "tv",
    "podcast", "vlog",
    # 创意设计
    "design", "diy", "art", "craft",
}

# --- Reddit (生活效率类) ---
REDDIT_SUBREDDITS = [
    "lifehacks", "productivity", "LifeProTips",
]
REDDIT_INTERVAL = 1  # 减少到1秒，加快速度
REDDIT_TIMEOUT = 10  # 降低超时

# ============================================================
# 预筛关键词（jieba分词后匹配）
# ============================================================

# 痛点词 — 表达不满/困难/折腾
PAIN_KEYWORDS = {
    "痛点", "难用", "不方便", "吐槽", "麻烦", "烦", "难受", "效率低",
    "浪费时间", "太慢", "崩溃", "bug", "问题", "痛苦", "头大",
    "不好用", "反人类", "垃圾", "吐槽", "失望", "无语", "卡顿",
    "闪退", "报错", "错误", "失败", "缺失", "不够", "缺少",
    "麻烦", "折腾", "费劲", "不便", "累", "乱", "没人做",
    "没法用", "行不通", "搞不定", "不会用", "用不了",
}

# 需求词 — 表达期望/求助/建议
NEED_KEYWORDS = {
    "希望", "要是", "能不能", "为什么没有", "建议", "需求", "想要",
    "期待", "没办法", "如果有", "为什么不能", "应该", "需要",
    "求推荐", "求教", "求助", "有没有", "可不可以", "能不能实现",
    "怎么", "如何", "谁知道", "有没有人", "有什么", "请教",
    "推荐", "介绍", "分享", "指教", "求", "跪求",
    "想", "想做", "想找", "想弄", "想搞", "打算", "准备做",
}

# 大众工具词 — 确保与日常软件/网页/工具相关
# 聚焦老百姓能用的工具，排除数据库/服务器/API等专业开发词
TOOL_KEYWORDS = {
    # 办公效率
    "文档", "表格", "PPT", "PDF", "Word", "Excel", "排版", "打印",
    "格式转换", "批量处理", "翻译", "识别", "OCR", "语音转文字",
    # 文件管理
    "文件", "文件夹", "重命名", "改名", "归类", "去重", "整理",
    "压缩", "解压", "备份", "恢复", "云盘", "网盘", "同步",
    # 笔记/知识管理
    "笔记", "备忘录", "记事本", "便签", "思维导图", "大纲",
    "收藏", "书签", "剪藏", "摘录", "标注",
    # 任务/日程
    "提醒", "日历", "日程", "计划", "待办", "清单", "闹钟",
    "番茄钟", "计时器", "打卡", "习惯", "统计",
    # 图片/媒体
    "图片", "照片", "相册", "视频", "音频", "录屏", "截图",
    "剪辑", "水印", "抠图", "拼图", "滤镜", "画质",
    # 网络浏览
    "网页", "浏览器", "下载", "搜索", "比价", "抢票",
    "监测", "监控", "推送", "通知",
    # 数据分析(轻量)
    "统计", "汇总", "图表", "报表", "计算", "换算", "对比",
    "趋势", "排行榜", "筛选",
    # 生活
    "记账", "预算", "购物", "快递", "天气", "菜谱", "家务",
    "账单", "AA制", "分摊", "旅游", "出行",
    # 学习
    "背单词", "做题", "题库", "刷题", "错题", "阅读",
    "听写", "默写", "跟读", "发音",
    # 通用
    "工具", "软件", "应用", "APP", "小程序", "网页", "插件",
    "扩展", "脚本", "模板", "配置", "设置", "操作",
}
# 显式排除的专业领域词 — 出现这些词的帖子直接跳过
EXCLUDE_KEYWORDS = {
    "微服务", "Kubernetes", "Docker", "容器化", "CI/CD",
    "机器学习", "深度学习", "神经网络", "大模型训练",
    "分布式", "高并发", "负载均衡", "消息队列",
    "编译器", "汇编", "底层", "内核", "驱动",
    "区块链", "加密货币", "智能合约",
    "逆向", "破解", "脱壳", "反编译",
    "芯片", "FPGA", "嵌入式", "单片机",
}

# 英文关键词
EN_PAIN = {
    "annoying", "frustrating", "slow", "crash", "broken", "hate",
    "painful", "tedious", "cumbersome", "difficult", "struggle",
    "frustrated", "irritating", "horrible", "terrible", "worst",
    "tiresome", "messy", "clunky", "nightmare", "drives me crazy",
    "driving me crazy", "waste of time", "time-consuming",
}
EN_NEED = {
    "wish", "hope", "need", "want", "should", "would", "nice",
    "request", "suggest", "feature", "missing", "lack", "unable",
    "cannot", "can't", "intellij", "idea",
    "how to", "how do", "anyone know", "any way to", "is there a",
    "looking for", "recommend", "advice", "help with", "stuck with",
    "alternative to", "replacement for",
}
EN_TOOL = {
    # Everyday tools
    "tool", "app", "software", "website", "extension", "plugin",
    "template", "workflow", "automation", "batch", "shortcut",
    # File/Doc management
    "rename", "organize", "sort", "deduplicate", "sync", "backup",
    "export", "import", "convert", "compress", "extract", "merge",
    # Office productivity
    "document", "spreadsheet", "presentation", "slide", "report",
    "translate", "transcribe", "summarize", "format",
    # Notes/Tasks
    "note", "reminder", "calendar", "todo", "checklist", "habit",
    "timer", "pomodoro", "journal",
    # Media
    "image", "photo", "video", "audio", "screenshot", "recording",
    "crop", "watermark", "resize", "compress",
    # Web
    "browser", "download", "bookmark", "search", "scrape", "monitor",
    "notify", "alert", "track", "compare",
    # Data (lightweight)
    "chart", "graph", "dashboard", "statistics", "calculator",
    "converter", "filter",
    # Life
    "budget", "expense", "shopping", "delivery", "recipe",
    "weather", "travel", "itinerary", "split",
    # Learning
    "flashcard", "quiz", "practice", "reading", "listen",
    # Generic
    "helper", "manager", "generator", "creator", "builder",
}
EN_EXCLUDE = {
    "kubernetes", "docker", "microservice", "cloud", "ci/cd",
    "machine learning", "deep learning", "neural",
    "distributed", "concurrency", "load balancer",
    "compiler", "kernel", "driver", "assembly",
    "blockchain", "crypto", "smart contract",
    "reverse engineer", "crack", "exploit",
    "embedded", "firmware", "microcontroller",
}

# ============================================================
# 聚类配置
# ============================================================
CLUSTER_THRESHOLD = 0.30  # Jaccard相似度阈值，低于此值创建新簇

# ============================================================
# 排序权重
# ============================================================
WEIGHT_FREQUENCY = 0.40  # 频率分量
WEIGHT_RECENCY = 0.30    # 时效分量
WEIGHT_FEASIBILITY = 0.30  # 可行性分量
RECENCY_HALFLIFE_DAYS = 7.0  # 时效半衰期（天）

# 趋势检测
TREND_NEW_DAYS = 3          # 3天内首次出现 → new
TREND_INCREASE_RATIO = 0.5  # 增长>50% → increasing
TREND_DECREASE_RATIO = -0.2  # 下降>20% → decreasing

# ============================================================
# 数据保留策略
# ============================================================
RETENTION_POSTS_DAYS = 30
RETENTION_PAINPOINTS_DAYS = 90
RETENTION_LOGS_DAYS = 30
DISK_WARNING_MB = 500  # 磁盘低于此值触发紧急清理

# ============================================================
# 内容截断
# ============================================================
MAX_CONTENT_LENGTH = 2000   # 帖子内容存储截断
MAX_TITLE_LENGTH = 200

# ============================================================
# 看板配置
# ============================================================
DASHBOARD_TOP_N = 50  # 看板展示前N条
