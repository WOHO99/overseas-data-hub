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
---

# 海外信源自动抓取服务 v3.3

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
- 国内外交叉话题 → 双Skill联动，输出标注 `[国内X1]` / `[海外OV1]`
- 全球商业雷达 → 本Skill 14模块CDN → 信号检测 → SKILL_CN.md国内补充

详见 SKILL_CN.md "与海外Skill联动" 章节。

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

**信号性词汇聚集检测(v3.3)**：每个模块的keywords.yaml中新增`signal`词组。当同一信号词在全局出现≥5次 → index.json中的`global_signal_alerts`会列出告警。Agent读取时应优先检查此项，发现告警即提示用户："今日信号词'{X}'异常聚集（{N}次），可能暗示{领域}有重大事件正在发生。"

**relevance判定**：priority≥10 → high, ≥3 → medium, <3 → low

**关键词外置**：所有关键词配置在 `config/keywords.yaml`，改关键词不需要改代码，直接在GitHub网页编辑yaml文件，Actions下次运行自动生效。

### 双层去重

1. **第一层：link哈希精确去重** — URL标准化(https+去跟踪参数) → MD5前12位，保留priority最高的，快速排除80%重复
2. **第二层：标题相似度去重** — `difflib.SequenceMatcher`，相似度≥85%且发布时间差<24h → 视为重复，保留priority最高的，再筛掉15%重复

### 容错机制

| 机制 | 说明 |
|------|------|
| 模块超时 | 每模块15分钟硬超时，超时杀进程，输出已完成部分 |
| 错误隔离 | try/except包裹每个模块，单模块失败不影响其他9个 |
| 连续失败告警 | 核心模块(global_business)连续3天失败→Actions报错，需人工介入 |
| JSON原子写入 | 先写.tmp再rename，防止崩溃留下半个烂JSON |
| 并发抓取 | 8线程线程池并发请求RSS，30秒单源超时，压低总耗时 |
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

远低于2000分钟上限，安全边界极大。

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
| 降级策略 | 路由失效时：①webfetch直接访问目标页面 ②online_search补充搜索 ③告知用户路由可能过时 |
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
1. 在RSSHub路由文档中搜索对应路由
2. 若找到路由 → 调用 `{RSSHUB_BASE_URL}/路由?format=json`
3. 若无路由 → 告知用户RSSHub可自定义路由但需开发，同时用online_search补充
4. 将RSSHub结果与引擎A数据**合并分析**
5. 所有RSSHub来源条目标注 `[RSSHub]` + 原始链接

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

## 安全规则

- 本地零风险：全部云端完成
- API Key用GitHub Secrets存储，严禁写入脚本
- GitHub账号开启2FA
- JSON为只读API，Agent不写入
- RSSHub实例为私有部署，不暴露给外部

## 资源文件清单

| 文件 | 用途 | 部署位置 |
|------|------|---------|
| `scripts/common.py` | 共享工具库 | 仓库根目录 |
| `scripts/fetch_all.py` | 主调度脚本 | 仓库根目录 |
| `scripts/modules/*.py` | 14个模块(×14) | 仓库modules/目录 |
| `scripts/daily-fetch.yml` | GitHub Actions工作流 | `.github/workflows/` |
| `scripts/config/keywords.yaml` | 关键词配置(外置) | 仓库config/目录 |
| `scripts/config/search_queries.md` | 搜索词设计意图文档 | 仓库config/目录 |
| `references/rsshub_routes.md` | RSSHub常用路由速查 | Agent按需读取 |
| `scripts/config/domestic_sources.yaml` | 国内信源A-E级数据库 | Agent读取（SKILL_CN.md使用） |
| `scripts/config/domestic_search_templates.yaml` | 国内12场景搜索模板 | Agent读取（SKILL_CN.md使用） |
| `SKILL_CN.md` | 国内信源收集技能v1.1(Trust-Source) | 双核联动，纯国内问题走此Skill |
