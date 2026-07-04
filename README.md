# LEO · 大众需求排行榜

每日自动从互联网收集老百姓日常生活中的痛点、需求和痒点，智能聚类排序，生成交互式排行榜看板。

## 功能

- **每日自动采集** V2EX（50+ 生活节点）+ Reddit（生活效率版块）
- **智能预筛** 基于 jieba 分词 + 关键词匹配，过滤专业/技术内容
- **痛点聚类** Jaccard 相似度算法自动归类
- **多维排序** 频率 × 时效 × 可行性 综合评分
- **交互看板** 分类筛选、可行性过滤、趋势追踪、实时搜索、一键刷新

## 架构

```
collectors.py    →  采集 V2EX/Reddit 帖子
processor.py     →  预筛 + 聚类 + 排序 + 趋势检测
database.py      →  SQLite 数据持久化
dashboard.py     →  HTML 看板生成
server.py        →  HTTP 服务器 + 每日8点自动调度
main.py          →  主编排器
```

## 本地运行

```bash
pip install -r requirements.txt
python main.py                    # 全流程
python server.py                  # 启动 HTTP 服务 → http://localhost:7531
```

## Render 部署

1. Fork/克隆此仓库到你的 GitHub
2. 在 [Render](https://render.com) 中连接 GitHub
3. Render 自动识别 `render.yaml` 创建 Web Service
4. 服务内置每日 08:00 (北京时间) 自动刷新

> **提示**: Render 免费套餐服务空闲 15 分钟后会休眠。建议使用 [UptimeRobot](https://uptimerobot.com) 设置每 10 分钟 ping 保持活跃。
