---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '8eb0ec45-c2c0-4d0b-886f-7c3067d2a0f0'
  PropagateID: '8eb0ec45-c2c0-4d0b-886f-7c3067d2a0f0'
  ReservedCode1: '318a5671-3bde-48cd-9d07-7723b1ea9cc8'
  ReservedCode2: '318a5671-3bde-48cd-9d07-7723b1ea9cc8'
---

# SKILL_CN.md v1.1 — 国内信源收集技能（Trust-Source）

> 与 SKILL.md（海外信源）并列，组成**双核情报技能组**。
> Agent根据用户提问自动路由：国内信号走本Skill，海外信号走海外Skill，双源同时触发时做交叉验证[X1]。

---
## 元数据

| 字段 | 值 |
|------|---|
| skill_id | domestic-source-trust |
| version | 1.1 |
| updated | 2026-06-11 |
| method | Agent Skill规则驱动（零运维） |
| config | `scripts/config/domestic_sources.yaml` + `scripts/config/domestic_search_templates.yaml` |

---
## 核心原则

**信源可信度优先，搜索引擎兜底。**

1. 统计数据/政策/法规类查询 → **必须优先AKShare API或webfetch官网** (硬性规则，见下)
2. 深度商业分析 → RSSHub/RSS直连 > 限定域名搜索
3. 所有关键数据 → 交叉验证
4. 所有输出 → 信源标注 + 信任度摘要

---
## 硬性规则（不可违反）

### 规则1：A级信源webfetch优先（建议6：防信源降级滥用）

> 处理统计数据、政策、法规类查询时，**必须优先尝试AKShare API调用或webfetch原始官网页面**。
> 仅在官网不可达且API无对应函数时，才使用 `site:` 限定搜索。
> **绝对禁止从非白名单域名采信关键数据。**

执行顺序（不可跳步）：
1. 查 `domestic_sources.yaml` → 该数据是否有AKShare API？
   - 有 → 执行 `akshare.function()` 获取结构化数据
   - 无 → 进入步骤2
2. webfetch 该信源的 primary_url
   - 成功 → 提取数据
   - 失败（404/超时）→ 进入步骤3
3. webfetch 该信源的 fallback_url（着陆页备用，建议1）
   - 成功 → 从着陆页导航到具体数据
   - 失败 → 进入步骤4
4. `site:该信源域名 + 关键词` 限定搜索
   - 从结果中**只选取官网域名链接**，不采信转载站
   - 找不到官网链接 → 报告"该数据当前不可获取"

### 规则2：搜索必须限定域名

泛搜索 `online_search("越南关税")` 仅作为最后兜底，且结果中E级占比通常>60%。

限定域名搜索模板（从 `domestic_search_templates.yaml` 读取）：
- 贸易数据：`site:customs.gov.cn OR site:mofcom.gov.cn {关键词}`
- 宏观指标：`site:stats.gov.cn OR site:pbc.gov.cn {关键词}`
- 深度分析：`site:caixin.com OR site:wallstreetcn.com {关键词}`
- 科技动态：`site:36kr.com OR site:latepost.com {关键词}`

### 规则3：B级信源RSSHub优先（建议4）

> B级信源获取优先级：RSSHub路由 > 原生RSS > site:限定搜索
> RSSHub直接解析原始网站结构，保证链接直指原始出处，无转载污染。

### 规则4：E级信源不采信

> E级（百家号/头条号/营销号/SEO聚合站）NEVER作为分析依据。
> 仅当A-D级引用到E级内容时，作为"市场情绪"参考，并标注[情绪参考]。

---
## 交叉验证规则

### 验证分级

| 数据类型 | 最低信源要求 | 冲突处理 |
|---------|------------|---------|
| 官方统计（GDP/CPI/贸易额） | 1个A级 | A级 > 其他所有级别 |
| 政策/法规 | 1个A级 gov.cn原文 | 必须链接原文 |
| 企业财务数据 | 1个B级 + 1个C级以上 | 以官方公告/财报为准 |
| 行业数据 | 2个B级以上独立信源 | 取保守值 |
| 传闻/未确认 | 标注[!!]传闻 | 禁止作分析依据 |

### 数值型数据容差带（建议3）

- 两个独立信源差异 ≤3% → 视为**一致**，采信更高级别版本，注明"另有信源给出X值，差异在合理范围"
- 两个独立信源差异 3%-10% → 采信更高级别版本，标注[数据偏差]和两方数值
- 两个独立信源差异 >10% → 视为**冲突**，标注[数据冲突]，以A级为准，提醒用户注意

---
## 输出标注格式

### 单条信息标注

| 标注 | 含义 | Agent处理 |
|------|------|----------|
| `[A1] 海关总署 2026-06-09` | A级已验证 | 直接采信，最高优先 |
| `[A-api] AKShare/macro_china_gdp 2026Q1` | A级API数据 | 同[A1]，数据来源标注API |
| `[B1] 财新网 2026-06-08` | B级已验证 | 采信，A级冲突时让步 |
| `[B0] 华尔街见闻 2026-06-07` | B级未交叉验证 | 可采信但需注意 |
| `[D1] 钛媒体 2026-06-06` | D级已交叉验证 | 谨慎参考 |
| `[E0] 未知信源 2026-06-05` | E级/未知 | 不采信 |
| `[!!] 传闻-未验证` | 未经任何验证 | 禁止作分析依据 |

### 信源信任度摘要（建议5）

> 每次输出开头必须附加"信源信任度摘要"区块，格式：

```
【信源信任度摘要】A级 3条 | B级 5条 | C级 2条 | 交叉验证通过 8条 | 单源待验证 3条 | 整体可信度：高
```

可信度评级标准：
- **高**：A级占比>50% 且 交叉验证率>80%
- **中**：B级占比>50% 且 交叉验证率>60%
- **低**：D级以下占比>30% 或 交叉验证率<50%

---
## RSS存活监控（建议2）

> Agent每次调用国内B级数据时，如果某个RSS/RSSHub源连续2次返回文章数为0，
> 应主动向用户提示：`[RSS告警] XXX信源可能失效，建议验证`

---
## AKShare API调用规范

### 可用API函数清单（已本地验证）

| 函数名 | 数据 | 来源 | 更新频率 |
|--------|------|------|---------|
| macro_china_gdp | GDP季度数据 | 国家统计局 | 季度 |
| macro_china_cpi | CPI月度 | 国家统计局 | 月度 |
| macro_china_ppi | PPI月度 | 国家统计局 | 月度 |
| macro_china_pmi | PMI制造业+非制造业 | 国家统计局 | 月度 |
| macro_china_money_supply | M0/M1/M2 | 央行 | 月度 |
| macro_china_trade_balance | 贸易差额 | 海关总署 | 月度 |
| macro_china_fx_reserves_yearly | 外汇储备 | 外管局 | 年度 |
| macro_china_lpr | LPR利率 | 央行 | 月度 |
| macro_china_new_financial_credit | 新增社融 | 央行 | 月度 |
| macro_china_gdzctz | 固定资产投资 | 国家统计局 | 月度 |
| macro_china_urban_unemployment | 城镇失业率 | 国家统计局 | 月度 |
| macro_china_exports_yoy | 出口同比 | 海关 | 月度 |
| macro_china_imports_yoy | 进口同比 | 海关 | 月度 |
| macro_china_industrial_production_yoy | 工业增加值同比 | 国家统计局 | 月度 |
| macro_china_consumer_goods_retail | 社会消费品零售 | 国家统计局 | 月度 |
| stock_notice_report | 上市公司公告 | 巨潮 | 实时 |
| stock_zh_a_hist | A股历史行情 | 东方财富 | 日度 |

### 调用模板

当用户查询涉及以下数据时，Agent应直接调用AKShare：

```
用户: "最新CPI数据是多少？"
Agent执行: python -c "import akshare as ak; print(ak.macro_china_cpi().head(1))"
Agent输出: [A级-api] AKShare/macro_china_cpi 2026年05月 → CPI同比1.2%
```

---
## API直连通道（v1.2新增，2026-06-11全量实测）

> 三层架构：L1快速(AKShare) → L2深度(统计局V2.0) → L3国际(世界银行)
> 所有通道均实测通过，标注规则见"输出标注格式"

### 三层路由规则

```
Agent收到数据查询请求
  ↓
判断：国内/海外/对比
  ├── 纯国内 → L1→L2→SKILL_CN原有规则
  ├── 纯海外 → L3→海外Skill
  └── 对比 → L1/L2国内 + L3国际 → 交叉验证
```

### 按数据类型的路由表

| 数据类型 | 优先通道 | 备选 | 标注 |
|---------|---------|------|------|
| GDP/CPI/PPI等17项常规 | L1 AKShare | L2 统计局V2.0 | [A-api] |
| 分省/分行业/人口/就业 | L2 统计局V2.0 | site:搜索 | [A-v2] |
| 统计局V2.0关键词查不到的 | L2 树遍历 | webfetch官网 | [A-v2] |
| 全球GDP/CPI/汇率对比 | L3 世界银行 | L3 FRED(美国) | [A-wb] |
| 美国宏观深度(80万+指标) | L3 FRED(需Key) | L3 世界银行 | [B-fred] |
| HS编码级双边贸易 | L3 UN Comtrade(待Key) | L1 AKShare | [A-un] |
| 上市公司公告/行情 | L1 AKShare | webfetch巨潮 | [A-api] |
| 每日新闻摘要 | 中国日报API | B级RSS | [C-api] |

### L2 统计局V2.0 三步走操作手册

**Base URL**: `https://data.stats.gov.cn/dg/website/publicrelease/web/external`

**Step 1: 搜索定位cid**

```
GET {BASE}/query?search={关键词}&pagenum=1&pageSize=10
```

返回结果中取 `cid`（数据集ID）和 `type_text`（月度/季度/年度）。
已验证可用关键词：GDP、CPI、PMI、居民消费价格、出口

**Step 2: 获取indicatorId**

```
GET {BASE}/new/queryIndicatorsByCid?cid={cid}
```

返回 `list` 数组，每个元素含 `_id`(indicatorId)、`i_showname`(指标名)、`i_mark`(统计口径)、`du`(单位)。

**Step 3: POST取数据**

```json
POST {BASE}/getEsDataByCidAndDt
Content-Type: application/json

{
  "cid": "{cid}",
  "indicatorIds": ["{id1}", "{id2}"],
  "das": [{"text": "全国", "value": "000000000000"}],
  "dts": ["202501MM-202602MM"],
  "showType": "1",
  "rootId": "fc982599aa684be7969d7b90b1bd0e84"
}
```

时间编码：月度=YYYYMM+后缀MM / 季度=YYYYQ+后缀SS / 年度=YYYY+后缀YY

**关键注意**：
- 同一指标因时间分片对应多个cid（通常5年一段），需分别请求后本地拼接
- 跨cid时indicatorId可能不同，每个cid都要重新Step 2
- `i_mark`含统计口径说明（基期/计算方法），展示数据时必须附带
- 日限额1000次，单次查询最多3步=3次请求

### L3 世界银行操作手册

**Base URL**: `https://api.worldbank.org/v2`

```
GET /country/{国家代码}/indicator/{指标ID}?format=json&date={起始}:{结束}&per_page=50
```

- 国家代码：ISO2（CN/US/JP/DE/KR/IN/BR/RU，多国用`;`分隔）
- 无需Key，无限额，完全免费
- 常用指标：
  - GDP(现价美元): `NY.GDP.MKTP.CD`
  - GDP增长率: `NY.GDP.MKTP.KD.ZG`
  - CPI通胀率: `FP.CPI.TOTL.ZG`
  - 贸易占GDP比: `NE.TRD.GNFS.ZS`
  - 出口(美元): `NE.EXP.GNFS.CD`
  - 进口(美元): `NE.IMP.GNFS.CD`
  - 汇率: `PA.NUS.FCRF`
  - 失业率: `SL.UEM.TOTL.ZS`
  - 政府债务占GDP: `GC.DOD.TOTL.GD.ZS`
  - FDI占GDP: `BX.KLT.DINV.WD.GD.ZS`

### 待Key激活通道

| 通道 | 需要什么 | 价值 | 优先级 |
|------|---------|------|--------|
| FRED | 免费API Key | 80万+美国宏观指标 | 中 |
| UN Comtrade | 免费注册+确认端点 | HS编码级双边贸易 | 高 |
| DailyHotApi | Vercel自部署 | 20+平台热榜 | 高 |
| 起零数据 | 免费Token | CCTV/澎湃/Tencent | 低 |

### L1→L2降级自动触发规则

1. AKShare函数调用报错（函数名变更/数据源改版）→ 自动尝试L2统计局V2.0搜索同关键词
2. AKShare函数返回空DataFrame → 检查是否为数据未更新，若为真→L2取最新发布
3. 查询涉及AKShare未覆盖的指标（分省/分行业/人口/投资细分）→ 直接走L2

---
## 与海外Skill联动

| 场景 | 路由 | 操作 |
|------|------|------|
| 纯国内问题 | 本Skill | L1 AKShare → L2 统计局V2.0 → B级RSS → C级搜索 |
| 纯海外问题 | SKILL.md | CDN JSON → 在线搜索 |
| 国内外交叉 | 双Skill联动 | 国内[X1]+海外[OV1]交叉验证 |
| 全球商业雷达 | SKILL.md | 14模块CDN → 信号检测 → 国内补充 |
| 国际宏观数据 | 本Skill L3 | 世界银行/FRED直接API |
| 中美GDP对比 | 本Skill L1+L3 | AKShare中国GDP + 世界银行美国GDP |

---
## 变更日志

- v1.2 (2026-06-11): 新增API直连通道三层架构(L1 AKShare + L2 统计局V2.0 + L3 世界银行)，全量实测验证，新增中国日报C级API，媒体类API实测淘汰
- v1.1 (2026-06-11): 整合老K 8条建议 + AKShare API优先策略
- v1.0 (2026-06-11): 初始版本