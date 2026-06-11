---
name: overseas-news-fetcher
description: >
  Overseas data auto-fetcher: dual-engine architecture.
  Engine A (Base): GitHub Actions + jsDelivr CDN, daily full scan, 14 modules, 340+ RSS.
  Engine B (Scout): RSSHub on Vercel, real-time targeted fetch for sites without RSS.
  Triggers when user asks about: 海外新闻/出海新闻/海外商业动态/国际贸易/海外信源/
  overseas news/international trade/tariff/sanctions/301/1260H/supply chain/
  东南亚/南亚/中东/拉美/非洲/欧洲/独联体/日韩/
  金融资讯/全球宏观/大宗商品/汇率/股市政策/
  半导体/芯片/AI/科技/能源/大宗/地缘政治/ESG/碳排放/可持续发展/
  特定网站监控/即时验证/RSSHub/
  the overseas-data-hub repo's JSON files.
name_cn: 全球商业情报仪表盘
description_cn: 双引擎全球商业情报：定时全量扫描(GitHub Actions 14模块)+即时定点深探(RSSHub)，覆盖全球商业/金融/科技/能源/地缘/ESG/8大区域，信号性词汇异常检测，Agent无需翻墙随时取用
create_source: super-agent-skill-creator
last_updated: 2026-06-11
module_count: 14
phase3_progress: "3.1-3.8 done"
---

# 海外信源自动抓取服务 v3.4

## Agent启动前需读取的用户配置

Agent在执行本技能前，**必须**已从用户的USER.md、MEMORY.md或对话上下文获取以下变量：

| 变量 | 说明 | 缺失时处理 |
|------|------|-----------|
| `GITHUB_USERNAME` | GitHub用户名，用于拼接CDN地址 | 主动向用户询问，不得猜测 |
| `RSSHUB_BASE_URL` | RSSHub实例域名（如`https://rsshub.yourdomain.com`） | 引擎B不可用，用online_search替代 |

**CDN前缀** = `https://cdn.jsdelivr.net/gh/{GITHUB_USERNAME}/overseas-data-hub@main/`

若任一变量缺失，Agent应主动向用户询问，不得擅自猜测或编造URL。

## 双引擎架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                    海外信源双引擎体系                          │
├──────────────────────────┬──────────────────────────────────┤
│  引擎A: 基座 (Base)      │  引擎B: 尖兵 (Scout)             │
│  GitHub Actions + CDN    │  RSSHub + Vercel                 │
├──────────────────────────┼──────────────────────────────────┤
│  定时全量扫描             │  即时定点深探                     │
│  类比：卫星遥感           │  类比：无人机看哪飞哪              │
│  每天1次，340+RSS源      │  用户需求驱动，3000+路由           │
│  输出15个JSON(含索引)    │  即时返回JSON                     │
│  适合：日常扫描/概览      │  适合：深度追踪/即时验证           │
│  成本：GitHub 240min/月  │  成本：Vercel几乎为0              │
│  国内访问：CDN直连        │  国内访问：Vercel直连             │
└──────────────────────────┴──────────────────────────────────┘
```

**铁律：引擎A优先，引擎B仅作补充。永远先查CDN缓存，再决定是否需要即时抓取。**

## 双核情报技能组

本Skill（SKILL.md）处理**海外信源**，与 **SKILL_CN.md**（国内信源，Trust-Source架构）并列组成双核情报技能组。

| 维度 | SKILL.md（海外） | SKILL_CN.md（国内） |
|------|-----------------|-------------------|
| 方法 | GitHub Actions定时抓取 + RSSHub即时 | AKShare API + webfetch + 限定搜索 |
| 信源 | 340+海外RSS源 | A-E级信源可信度体系 |
| 数据流 | CDN JSON → Agent读取 | API返回 / webfetch / online_search |
| 交叉验证 | 海外多源去重 | 国内A-D级交叉 + 海外[X1]/[OV1]互验 |

**路由规则**：
- 纯海外问题 → 本Skill
- 纯国内问题 → SKILL_CN.md
- 国内外交叉话题 → 双Skill联动，按 `docs/compare_protocol.md` 协议执行，输出标注 `[国内X1]` / `[海外OV1]`
- 全球商业雷达 → 本Skill 14模块CDN → 信号检测 → SKILL_CN.md国内补充

**联动协议**：详见 `docs/compare_protocol.md`（请求路由字段 + 响应字段 + 冲突消解规则 + 执行模板）

## 引擎A: 基座 — GitHub Actions + jsDelivr CDN

### 数据流

```
GitHub Actions (境外服务器, 每天1次 UTC 00:00 = 北京08:00)
  ↓ 运行 fetch_all.py (主调度)
  ↓ 顺序执行14个模块 → 各自输出JSON
  ↓ 全局跨模块去重 + 信号性词汇聚集检测 → index.json
  ↓ git push + CDN purge
jsDelivr CDN (全球加速, 国内直连)
  ↓ 静态文件分发
Agent (本机)
  ↓ HTTP GET 读取 JSON
  ↓ 按场景/区域/优先级筛选
  → 输出给用户
```

### 仓库结构（GitHub: overseas-data-hub）

所有Python文件和子目录直接放在仓库根目录，与下图一致：

```
overseas-data-hub/
├── .github/workflows/daily-fetch.yml
├── config/
│   ├── keywords.yaml               ← 关键词配置(外置，改词不动代码，v3.3含signal词)
│   └── search_queries.md           ← 搜索词设计意图文档
├── common.py                       ← 共享工具库(并发+双层去重+原子写入+信号检测)
├── fetch_all.py                    ← 主调度(超时+错误隔离+连续失败告警+14模块)
├── modules/
│   ├── global_business.py          ← 全球商业与产业链重构 (原出海商业，v3.3升级)
│   ├── finance_global.py           ← 全球宏观与资本流动
│   ├── tech_industry.py            ← 全球科技与工业前沿 (v3.3新增)
│   ├── energy_commodities.py       ← 全球能源与大宗商品 (v3.3新增)
│   ├── geopolitics_risk.py         ← 全球治理与地缘风险 (v3.3新增)
│   ├── esg_sustainability.py       ← ESG与可持续发展 (v3.3新增)
│   ├── region_se_asia.py           ← 东南亚
│   ├── region_south_asia.py        ← 南亚
│   ├── region_middle_east.py       ← 中东
│   ├── region_latin_america.py     ← 拉美
│   ├── region_africa.py            ← 非洲
│   ├── region_europe.py            ← 欧洲
│   ├── region_cis.py               ← 独联体
│   └── region_east_asia.py         ← 东亚(日韩)
├── *.json                          ← 各模块输出 + index.json
└── fail_counts.json                ← 连续失败计数(自动维护)
```

### API接口一览

**CDN前缀**：`https://cdn.jsdelivr.net/gh/{GITHUB_USERNAME}/overseas-data-hub@main/`

| 文件 | 场景 | 说明 |
|------|------|------|
| `index.json` | 全局索引 | 跨模块去重后的global top100 + 各模块统计 + 信号性词汇告警 |
| `global_business.json` | 全球商业与产业链 | 6组(全球财经/科技出海/政策制裁/全球产业链重构/东南亚本地/信号) |
| `finance.json` | 全球宏观与资本流动 | 9组(宏观/系统性风险/去美元化/股市/大宗/汇率/债市/资本流动/信号) |
| `tech_industry.json` | 全球科技与工业前沿 | 5组(半导体/AI/电动车+电池/生物+航天/信号) |
| `energy_commodities.json` | 全球能源与大宗商品 | 5组(油气/关键矿产/粮食安全/能源转型+碳/信号) |
| `geopolitics_risk.json` | 全球治理与地缘风险 | 5组(联合国/军事冲突/选举+政策/网络+安全/信号) |
| `esg_sustainability.json` | ESG与可持续发展 | 5组(ESG法规/碳+绿/可持续供应链/气候风险/信号) |
| `se_asia.json` | 东南亚深度 | 11组(7国+政治+基础设施+气候+大国关系+信号) |
| `south_asia.json` | 南亚深度 | 10组(4国+政治+基础设施+气候+大国关系+本地语言+信号) |
| `middle_east.json` | 中东深度 | 10组(海湾/伊朗土耳其/以色列+政治+基础设施+气候+大国关系+阿拉伯语+信号) |
| `latam.json` | 拉美深度 | 10组(墨西哥/巴西/阿根廷等+政治+基础设施+气候+大国关系+葡西语+信号) |
| `africa.json` | 非洲深度 | 9组(5国+矿业+贸易+政治冲突+基础设施+气候+大国关系+信号) |
| `europe.json` | 欧洲深度 | 10组(EU政策+主要国家+ECB+政治+基础设施+气候+大国关系+德法语+信号) |
| `cis.json` | 独联体深度 | 9组(俄罗斯/中亚/白俄罗斯+战争+基础设施+气候+大国关系+俄语+信号) |
| `east_asia.json` | 东亚深度 | 9组(日本/韩国/朝鲜+政治+基础设施+气候+大国关系+日韩语+信号) |

- 协议：HTTPS GET，无鉴权
- 国内延迟：<500ms
- 更新频率：每日1次
- 读取不消耗GitHub Actions额度

### CDN备用分发方案

主用CDN可能被墙或缓存刷新延迟，Agent应按以下优先级自动切换：

| 优先级 | 服务 | URL模板 | 预期延迟 | 限制 |
|--------|------|---------|---------|------|
| 主用 | jsDelivr | `https://cdn.jsdelivr.net/gh/{GITHUB_USERNAME}/overseas-data-hub@main/{file}` | <500ms | 国内直连，偶有缓存延迟 |
| 备用1 | GitHub Raw | `https://raw.githubusercontent.com/{GITHUB_USERNAME}/overseas-data-hub/main/{file}` | 1-3s | 国内偶尔波动，但有保障 |
| 备用2 | Statically | `https://cdn.statically.io/gh/{GITHUB_USERNAME}/overseas-data-hub/main/{file}` | <1s | 第三方CDN，稳定性待验证 |

**Agent降级逻辑**：
1. 尝试主用jsDelivr，超时2秒
2. 超时/404 → 切换备用1 GitHub Raw，超时5秒
3. 仍失败 → 切换备用2 Statically，超时3秒
4. 全部失败 → 告知用户"海外数据CDN暂不可达，可用`gh repo clone`本地获取"

**缓存刷新策略**：
- jsDelivr缓存约12小时自动更新，Actions推送后已自动purge
- 若仍获取旧数据 → URL末尾加`?t={timestamp}`强制刷新
- GitHub Raw始终为最新commit，无缓存问题

**日志记录**：每次CDN降级切换均记录到对话日志，格式：`[CDN降级] jsDelivr超时 → 切换GitHub Raw`

### JSON结构

**index.json**：含 `version/updated/fetch_date_utc/global_total/global_high/global_signal_alerts/modules统计/high_priority_articles(top100)`

**各模块JSON**：含 `version/module/updated/total/high_priority/medium_priority/signal_alerts/stats_by_category/articles`

**article字段**：title/link/published/summary/source/priority/relevance/category/signal_keywords(可选)

### 3级关键词评分体系 + 信号性词汇检测

| 级别 | 权重 | 判定规则 | 示例 |
|------|------|---------|------|
| 核心词 | +5 | 1个即 high | 301/tariff/sanctions/FOMC/CBAM/制裁... |
| 重要词 | +3 | 2个即 high | supply chain/FDI/出口管制/ECB/反倾销... |
| 辅助词 | +1 | 累加 | trade/export/manufacturing/GDP/投资... |
| 信号词 | 不计分 | 独立检测 | "first ever"/"unprecedented"/"supply disruption"/"force majeure"/"emergency meeting"... |

**信号性词汇聚集检测(v3.3)**：每个模块的keywords.yaml中新增`signal`词组。当同一信号词在全局出现次数 ≥ `max(7天最高值, 3)` 时触发告警 → index.json中的`global_signal_alerts`会列出告警。Agent读取时应优先检查此项，发现告警即提示用户："今日信号词'{X}'异常聚集（{N}次），基线{baseline}，可能暗示{领域}有重大事件正在发生。" [待Phase4实现动态基线，当前版本仍使用固定阈值≥5]

**relevance判定**：priority≥10 → high, ≥3 → medium, <3 → low

**关键词外置**：所有关键词配置在 `config/keywords.yaml`，改关键词不需要改代码，直接在GitHub网页编辑yaml文件，Actions下次运行自动生效。

### 矛盾信号报告准则

当同一话题在跨模块/跨信源中出现方向性矛盾时（如"增长"vs"衰退"、"制裁升级"vs"谈判突破"），Agent必须执行以下行为模板，**不得自行调和矛盾**：

**Step 1 — 识别矛盾**：在同一分析输出中，发现两个high/medium条目对同一事件/指标给出方向相反的判断。

**Step 2 — 分列双方**：以表格形式呈现，禁止模糊化：

| 信源A | 观点摘要 | 信源B | 观点摘要 | 分歧核心 |
|-------|---------|-------|---------|---------|
| Reuters | 制造业PMI降至48.5 | Nikkei Asia | 新订单指数回升至51.2 | 当期vs前瞻指标 |
| SCMP | 越南301关税下月生效 | VNExpress | 越美达成初步协议 | 官方未确认 vs 乐观预期 |

**Step 3 — 标注可能原因**：从以下维度解释差异：
- 统计口径差异（当期/前瞻、名义/实际）
- 地区视角差异（中方/美方/第三方）
- 发布时间差（一方引用最新数据，另一方引用上月）
- 信源可信度差异（A级官方 vs B级媒体解读）

**Step 4 — 给出验证建议**：建议用户关注哪一信源的后续更新，或建议用引擎B抓取原始报告验证。

**禁止事项**：
- 禁止输出"尽管有分歧，但总体趋于XX"的模糊结论
- 禁止仅选取一方而忽略另一方
- 矛盾本身即是信号，标记 `[矛盾信号]`

### 双层去重

1. **第一层：link哈希精确去重** — URL标准化(https+去跟踪参数) → MD5前12位，保留priority最高的，快速排除80%重复
2. **第二层：标题相似度去重** — `difflib.SequenceMatcher`，相似度≥85%且发布时间差<24h → 视为重复，保留priority最高的，再筛掉15%重复

### 容错机制

| 机制 | 说明 |
|------|------|
| 模块超时 | 每模块15分钟硬超时，超时杀进程，输出已完成部分 |
| 错误隔离 | try/except包裹每个模块，单模块失败不影响其他13个 |
| 连续失败告警 | 核心模块(global_business)连续3天失败→Actions报错，需人工介入 |
| JSON原子写入 | 先写.tmp再rename，防止崩溃留下半个烂JSON |
| 并发抓取 | 8线程池并发请求RSS，30秒单源超时，压低总耗时 |
| CDN即时刷新 | 每日抓取后主动purge jsDelivr缓存，更新即时生效 |

### 数据新鲜度检测

Agent读取index.json时，必须检查 `updated` 字段：
- **超过48小时未更新** → 提示用户："数据可能已过期，请检查GitHub Actions运行状态，必要时手动触发一次。"
- **global_high=0但global_total很大** → 提示用户："今日无high级文章，可能关键词需更新（编辑config/keywords.yaml）。"

### 额度管理

| 场景 | 月耗分钟 | 占比 |
|------|---------|------|
| 每日自动(1次/天×14模块) | ~360 | 18% |
| +每周手动触发3次 | +36 | 14% |
| +紧急事件5次/月 | +60 | 17% |

远低于2000分钟上限，安全边界极大。（注：本仓库为公开仓库，Actions分钟数完全免费且无上限，2000分钟仅为私有仓库限额）

## 引擎B: 尖兵 — RSSHub + Vercel

### 定位

仅当引擎A无法覆盖时启用，满足以下任一条件：
1. 用户明确要求监控**特定网站/页面**的动态（某政府公告页、某行业论坛、某数据平台报告列表）
2. 用户需要**即时验证**某条新闻，引擎A的1天间隔太久
3. 用户要求抓取**非标准新闻源**（社交媒体趋势、政府公告、特定企业官网更新）

### 调用方式

**前提**：用户已部署RSSHub实例到Vercel并绑定自定义域名。若`RSSHUB_BASE_URL`未配置，引擎B不可用。

**路由文档**：https://docs.rsshub.app/ — 在此搜索对应路由。

**API格式**：
```
GET {RSSHUB_BASE_URL}/路由路径?format=json
```

**返回结构**：
```json
{
  "items": [
    {
      "title": "标题",
      "link": "原文链接",
      "pubDate": "发布时间",
      "description": "内容摘要",
      ...
    }
  ]
}
```

**常用路由速查**：见 `references/rsshub_routes.md`

### RSSHub部署步骤

1. Fork https://github.com/DIYgod/RSSHub 到自己GitHub
2. 在Vercel导入该仓库，自动部署
3. 绑定自定义域名（可选但推荐，避免Vercel默认域名被墙）
4. 验证：浏览器访问 `{你的域名}/`
5. 将域名记入USER.md或MEMORY.md，Agent根据RSSHUB_BASE_URL变量调用

### 使用约束

| 约束 | 说明 |
|------|------|
| 优先级 | 永远优先用引擎A缓存数据，RSSHub仅在需要时补充 |
| 成本 | Vercel免费版100GB带宽/月，个人即时查询远用不完 |
| 降级策略 | 路由失效时：①online_search site:限定搜索（搜索引擎缓存通常含静态内容，比webfetch更可靠） ②webfetch直接访问目标页面 ③告知用户路由可能过时 |
| 空数据判断 | RSSHub返回items=0或异常少(如常年30条突然只有2条) → Agent主动提示"该路由可能已失效"，而非默默降级 |
| 未部署处理 | 若`RSSHUB_BASE_URL`未配置 → 跳过引擎B，直接用online_search等替代，并告知用户"RSSHub尚未部署，无法定点即时抓取，已用搜索替代" |
| 禁止行为 | 不得将RSSHub加入GitHub Actions定时抓取（违反"即时定点"定位，且与引擎A功能重叠） |

## 角色路由表

不同角色使用两引擎的方式不同，Agent根据用户身份/需求自动匹配：

| 角色 | 引擎A使用 | 引擎B使用 | 典型触发场景 |
|------|---------|---------|------------|
| 全球商业雷达员 | `index.json` → 各主题模块 | 按信号词定向验证 | "今天全球有什么重大商业事件？" |
| 出海研究员 | `global_business.json` + 区域JSON | 某国政府公告/行业论坛 | "越南工贸部301回应" |
| 金融分析师 | `finance.json` | 央行官网/SEC文件即查 | "Fed刚发声明看原文" |
| 供应链研究员 | `global_business.json`制裁组 + `energy_commodities.json` | BIS实体列表实时查 | "某公司是否新上清单" |
| 内容写手 | `index.json`→global_business/区域 | 特定企业/X账号动态 | "Temu在X上最新声明" |
| 风控法务 | `europe.json`(CBAM/GDPR) + `esg_sustainability.json` | USTR/FedReg即时文件 | "USTR新调查通知原文" |
| 管理层 | `index.json`(全局top10+信号告警) | 通常不用 | 快速了解今日海外动态 |

**全球商业雷达员(v3.3新增)**的默认行为：
1. 先读 `index.json` 获取全局top 100
2. 检查 `global_signal_alerts`（信号性词汇异常聚集）
3. 按需加载科技、能源、地缘等主题模块
4. 给出跨领域关联分析（例："今日半导体板块high priority 12条，同时地缘风险板块出现台湾海峡军演新闻，两者可能相关"）

**默认行为**：当无法判定角色时，Agent应先读`index.json`给出全局概览，再根据用户追问加载具体模块JSON。

### keyword→role 映射规则

当用户未明确指定角色时，Agent根据关键词自动匹配角色。匹配优先级：**长句优先**（先匹配多词组合，再匹配单关键词）。

| 角色 | 关键词（按匹配优先级排序） |
|------|------------------------|
| 全球商业雷达员 | 全球动态、今日概览、重大事件、热点、今日必读、全球扫描 |
| 出海研究员 | 出海、建厂、海外投资、FDI、东南亚工厂、越南+缅甸+泰国+印尼+马来西亚+菲律宾、本地化、合规 |
| 金融分析师 | 通胀、CPI、PPI、利率、降息、加息、汇率、美元、美联储、FOMC、债市、资本流动、去美元化 |
| 供应链研究员 | 供应链、制裁、出口管制、BIS、301、1260H、实体清单、关键矿产、稀土、卡脖子 |
| 内容写手 | 写文、选题、素材、头条号、文章、深度分析（当用户明确为写作目的时） |
| 风控法务 | 合规、CBAM、GDPR、ESG法规、USTR调查、反倾销、双反、WTO争端、制裁规避 |
| 管理层 | 概览、简报、摘要、核心要点、有什么重大、快速了解 |

**Python正则示例**：

```python
import re

ROLE_PATTERNS = [
    # 多词组合优先匹配
    ("供应链研究员", re.compile(r"(供应链|出口管制|制裁|BIS|实体清单|301|1260H|关键矿产|稀土|卡脖子)")),
    ("金融分析师", re.compile(r"(通胀|CPI|PPI|利率|降息|加息|汇率|美元|美联储|FOMC|债市|资本流动|去美元化)")),
    ("出海研究员", re.compile(r"(出海|建厂|海外投资|FDI|本地化|合规(?!.*CBAM)|越南|泰国|印尼|马来西亚|菲律宾|缅甸)")),
    ("风控法务", re.compile(r"(合规.*法规|CBAM|GDPR|ESG法规|USTR调查|反倾销|双反|WTO争端|制裁规避)")),
    ("全球商业雷达员", re.compile(r"(全球动态|今日概览|重大事件|热点|今日必读|全球扫描|有什么重大)")),
    ("管理层", re.compile(r"(概览|简报|摘要|核心要点|快速了解)")),
    ("内容写手", re.compile(r"(写文|选题|素材|头条号|文章)")),
]

def match_role(query: str) -> str:
    """从用户查询中匹配角色。返回角色名，无匹配则返回'全球商业雷达员'。"""
    for role, pattern in ROLE_PATTERNS:
        if pattern.search(query):
            return role
    return "全球商业雷达员"  # 默认角色
```

**注意**：一个查询可能匹配多个角色（如"越南供应链"同时匹配出海+供应链），此时按**先匹配到的角色为主**，同时加载两个角色的JSON模块做综合分析。

## Agent调用工作流

### 触发条件

用户问及以下任一领域时触发：
- 出海/全球化/跨境/海外商业
- 金融/宏观/利率/汇率/大宗商品/股市政策
- 特定区域贸易（东南亚/南亚/中东/拉美/非洲/欧洲/独联体/日韩）
- 制裁/关税/301/1260H/出口管制等政策
- 半导体/芯片/AI/科技/能源/大宗/地缘政治/ESG/碳排放/可持续发展
- 特定网站监控/即时验证/某网站动态

### 标准流程

1. **国内/海外路由判断**：
   - 问题涉及国内数据（GDP/CPI/政策/上市公司等）→ 转到 SKILL_CN.md 处理，不走海外引擎
   - 问题涉及海外数据 → 继续（步骤2起）
   - 国内外交叉 → 先走海外引擎获取海外部分，再按 SKILL_CN.md 获取国内部分，做交叉验证
2. **读取index.json**：webfetch获取全局索引，检查数据新鲜度（见"数据新鲜度检测"）
3. **按需读取模块JSON**：根据用户关注领域，读取1-2个模块的完整数据
4. **逐条处理，禁止抽样**：对当前读取到的模块JSON中的全部articles逐一分析，不得只读取前几条或随机选择，确保不遗漏任何一条可能重要的信息
   - **上下文安全阀**：若某模块total > 200条，仅对high + medium逐条分析，low条目只报告数量（`low: N条`），避免Agent上下文溢出
5. **按维度输出**：
   - 今日必读 Top 10（全局high priority）
   - 分赛道雷达（标记趋势方向↑↓→）
   - 数据与报告洞察（提取具体数字、预测、百分比）
   - 趋势信号与风险预警（跨模块关联分析）
   - 来源媒体统计
6. **判断是否需要引擎B**：当用户需求超出引擎A覆盖时，启用RSSHub（见下方子流程）
7. **判断是否需要国内补充**：当海外数据分析涉及国内对比/验证时，按 SKILL_CN.md 规则获取国内数据，输出标注 `[国内X1]`
8. **深度追踪**：对high priority条目用webfetch访问原文全文（按需）

### 引擎B子流程（条件触发）

触发条件：用户需求满足以下任一：
- 指定特定网站/页面
- 要求即时验证（"最新"/"刚才"/"刚刚"）
- 需要非标准源（社交媒体/企业官网/政府公告）

执行步骤：
0. **部署状态检查**：若`RSSHUB_BASE_URL`未配置 → 跳过引擎B，进入"特殊需求补充"流程（用online_search替代），并告知用户"RSSHub尚未部署，无法定点即时抓取，已用搜索替代"
0.5 **路由实时验证**：用 `online_search` 搜索 `site:docs.rsshub.app {目标站点名}` 确认路由是否存在且路径正确，避免使用过时路由
1. 确认路由 → 调用 `{RSSHUB_BASE_URL}/路由?format=json`
2. 若路由无效/无路由 → 告知用户RSSHub可自定义路由但需开发，同时用online_search补充
3. 将RSSHub结果与引擎A数据**合并分析**
4. 所有RSSHub来源条目标注 `[RSSHub]` + 原始链接

### 缓存规则

- 单次对话内每个JSON文件仅调用1次webfetch
- 后续分析使用缓存数据
- 用户明确要求"刷新"时才重新请求
- RSSHub即时请求不缓存（每次都是最新数据）

### 特殊需求补充

当用户的具体话题在两引擎中均未找到高质量命中时：
1. 先报告引擎A+引擎B的相关条目
2. 再用online_search针对性补充
3. 明确标注来源：`[CDN]` / `[RSSHub]` / `[实时搜索]`

## GitHub部署与维护

### 引擎A部署

1. 创建公开仓库 `overseas-data-hub`
2. 将Python文件和子目录按仓库结构图直接放入仓库根目录（`common.py`、`fetch_all.py`、`modules/`、`config/`均在根目录下），将`daily-fetch.yml`放入`.github/workflows/`
3. 开启写入权限：Settings → Actions → General → Read and write permissions
4. 手动触发1次验证
5. 确认所有JSON生成后，获取CDN地址

### 引擎B部署

1. Fork https://github.com/DIYgod/RSSHub 到自己GitHub
2. Vercel导入部署，绑定自定义域名
3. 验证访问正常
4. 将 `RSSHUB_BASE_URL` 记入USER.md

### 新增模块（引擎A）

1. 在 `modules/` 下新建Python文件，定义 `CONFIG` 字典
2. 在 `fetch_all.py` 的 `MODULE_REGISTRY` 加一行
3. 在 `config/keywords.yaml` 加对应的关键词配置

### 新增路由（引擎B）

无需改代码——RSSHub 3000+路由开箱即用，查文档找路由即可。如需自定义路由，参考RSSHub官方贡献指南。

### 故障排查

| 问题 | 引擎 | 排查 |
|------|------|------|
| 某JSON未更新 | A | Actions日志 → 写入权限 → 手动触发 |
| 某模块超时 | A | 检查该模块源响应速度 → 减少源数/拆分模块 |
| 核心模块连续失败 | A | fail_counts.json记录连续天数 → 检查Python依赖/语法 |
| JSON解析错误(半截) | A | 不会发生了——原子写入保证完整性，若出现则删除该JSON重新触发 |
| CDN返回旧数据 | A | 已自动purge；若仍旧 → 加`?t=时间戳`强制刷新 |
| CDN返回404 | A | 仓库可能未正确部署 → 检查文件是否在main分支 → 手动触发Actions |
| 数据超过48h未更新 | A | 提示用户检查Actions → 手动触发 → 必要时检查fail_counts.json |
| 某源始终0条 | A | 浏览器直接访问RSS URL验证 |
| RSSHub路由404 | B | 查路由文档确认路径 → 路由可能过时 |
| RSSHub返回空/异常少 | B | 目标网站可能改版 → 主动提示用户路由可能失效 |
| RSSHub超时 | B | Vercel冷启动，重试1次 → 检查Vercel部署状态 |
| RSSHub未部署 | B | 跳过引擎B → 用online_search替代 → 告知用户可部署 |
| 两引擎数据矛盾 | A+B | 以原文为准(webfetch验证)，注明来源差异 |
| 关键词没标high | A | 编辑config/keywords.yaml加新词 → 下次运行生效 |

## 第三方服务依赖分级

所有外部服务按关键度分A/B/C三级，C级可断不影响核心功能。

| 级别 | 含义 | 降级触发 | 降级动作 | 监控方法 |
|------|------|---------|---------|---------|
| **A级** | 必须可用，否则阻断 | 连续3次不可达 | 告警+人工介入 | 每日fetch成功否 |
| **B级** | 可用性高，失效时可降级 | 连续2次不可达 | 自动降级到搜索 | Agent调用时检测 |
| **C级** | 仅作补充，不可作唯一信源 | 任何异常 | 跳过该源 | Agent调用时检测 |

### 具体分级

| 服务 | 级别 | 降级动作 | 监控方法 |
|------|------|---------|---------|
| jsDelivr CDN | A | 切换GitHub Raw → Statically | Agent调用时超时/404 |
| RSSHub | B | 路由404 → webfetch原始页 → online_search | Agent调用时HTTP状态码 |
| Statically CDN | C | 跳过，用GitHub Raw | Agent调用时超时检测 |

**国内服务分级及错误码**见 SKILL_CN.md v2.0（L1=HTTP API主干，L1.5=AKShare可选快捷）。

## 安全规则

- 本地零风险：全部云端完成
- API Key用GitHub Secrets存储，严禁写入脚本
- GitHub账号开启2FA
- JSON为只读API，Agent不写入
- RSSHub实例为私有部署，不暴露给外部

### 领土地名规范

根据中国法律法规，Agent输出中出现以下地区时，必须使用规范全称：

| 常见写法 | 规范全称 | 备注 |
|---------|---------|------|
| 台湾 | 中国台湾省 | 含"台湾地区"时可视语境使用 |
| 香港 | 中国香港特别行政区 | 简称"中国香港"可用 |
| 澳门 | 中国澳门特别行政区 | 简称"中国澳门"可用 |
| 西藏 | 中国西藏 | 不使用"Tibet"作为独立指代 |
| 新疆 | 中国新疆维吾尔自治区 | 简称"中国新疆"可用 |
| 南海 | 中国南海 | 含争议海域时标注"根据中国主张" |

**执行规则**：
- 首次出现时使用完整规范全称，后续可用简称
- 引用海外原文时，在引用后用括号标注规范名称
- 海外RSS数据中的原文不改写，但Agent分析和输出中必须规范

### API响应Schema校验（C级信源）

C级及以下第三方API（如 suyanw.cn、aa1.cn 等个人开发者API）返回数据时，必须进行schema校验，防止注入或格式异常导致后续处理崩溃。

校验函数模板：

```python
def validate_api_response(data: dict, expected_schema: dict) -> tuple[bool, str]:
    """
    校验API响应是否符合预期schema。
    
    Args:
        data: API返回的JSON数据（已解析为dict）
        expected_schema: 期望的schema，格式为 {字段名: (类型, 是否必填)}
            例如: {"title": (str, True), "count": (int, False)}
    
    Returns:
        (是否通过, 错误信息)
    """
    for field, (expected_type, required) in expected_schema.items():
        if field not in data:
            if required:
                return False, f"缺少必填字段: {field}"
            continue
        if not isinstance(data[field], expected_type):
            # 容忍int/float互转
            if expected_type in (int, float) and isinstance(data[field], (int, float)):
                continue
            return False, f"字段'{field}'类型错误: 期望{expected_type.__name__}, 实际{type(data[field]).__name__}"
    
    # 检查XSS/注入：字符串字段不含<script>标签
    for field, (_, _) in expected_schema.items():
        if field in data and isinstance(data[field], str):
            if "<script" in data[field].lower():
                return False, f"字段'{field}'含可疑脚本注入"
    
    return True, "ok"
```

**使用示例**：
```python
# 中国日报API校验
schema = {"news": (list, True), "date": (str, False)}
ok, msg = validate_api_response(response, schema)
if not ok:
    logger.warning(f"API响应校验失败: {msg}")
```

### 免责声明

Agent每次输出情报分析结果时，末尾必须附加以下免责声明（可折叠）：

> **免责声明**：本信息基于公开信源自动收集整理，仅供参考，不构成任何投资、法律或商业决策建议。数据可能存在延迟、偏差或遗漏，请以官方发布为准。

**执行规则**：
- 完整分析报告 → 文末单独一行，不可省略
- 简短问答（<3条数据）→ 可省略完整声明，但需含"仅供参考"
- 用户明确要求不附加时 → 不附加

## 错误处理矩阵

| 编号 | 错误场景 | 错误码 | 检测方式 | 处置策略 | 恢复动作 |
|------|---------|--------|---------|---------|---------|
| E04 | CDN返回404 | `CDN_404` | HTTP 404 | 切换备用CDN（GitHub Raw → Statically） | 检查仓库文件是否在main分支 |
| E05 | 第三方API返回恶意/异常内容 | `API_INJECTION` | schema校验失败 | 拒绝采纳该数据，跳过该源 | 记录可疑API URL+响应片段，告警用户 |
| E06 | 抓取模块超时（subprocess kill） | `MODULE_TIMEOUT` | subprocess超时退出 | 保留已完成部分JSON，跳过该模块其余源 | fail_counts.json计数+1，连续3天触发告警 |
| E07 | Git push 403（权限失效） | `GIT_403` | git push返回403 | 放弃本次推送，保留本地JSON | 检查Actions写入权限，重新授权 |

**恢复优先级**：E05(安全) > E07(数据持久性) > E06 > E04

**国内错误码**（E01 AKSHARE_ERR / E02 NBS_LIMIT / E03 WB_TIMEOUT / E08 SEARCH_EMPTY / E09 API_ENDPOINT_CHANGED）见 SKILL_CN.md。

**告警阈值**：
- E06连续3天 → 必须人工介入
- E07出现1次 → 必须检查权限
- E05出现1次 → 必须记录并告知用户

| 文件 | 用途 | 部署位置 |
|------|------|---------|
| `common.py` | 共享工具库 | 仓库根目录 |
| `fetch_all.py` | 主调度脚本 | 仓库根目录 |
| `modules/*.py` | 14个模块(×14) | 仓库modules/目录 |
| `daily-fetch.yml` | GitHub Actions工作流 | `.github/workflows/` |
| `config/keywords.yaml` | 关键词配置(外置) | 仓库config/目录 |
| `config/search_queries.md` | 搜索词设计意图文档 | 仓库config/目录 |
| `references/rsshub_routes.md` | RSSHub常用路由速查 | Agent按需读取 |
| `docs/compare_protocol.md` | 双技能联动compare_request协议 | 双核联动时必读 |
| `docs/rsshub_routes.md` | RSSHub常用路由速查（副本） | Agent按需读取 |
| `config/domestic_sources.yaml` | 国内信源A-E级数据库 | Agent读取（SKILL_CN.md使用） |
| `config/domestic_search_templates.yaml` | 国内12场景搜索模板 | Agent读取（SKILL_CN.md使用） |
| `SKILL_CN.md` | 国内信源收集技能v2.0(Trust-Source, HTTP API主干) | 双核联动，纯国内问题走此Skill |
