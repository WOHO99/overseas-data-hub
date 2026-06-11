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

# SKILL_CN.md v2.1 — 国内信源收集技能（Trust-Source）

> 与 SKILL.md（海外信源）并列，组成**双核情报技能组**。
> Agent根据用户提问自动路由：国内信号走本Skill，海外信号走海外Skill，双源同时触发时做交叉验证[X1]。
> **v2.0核心变更**：数据获取链路从AKShare(Python依赖)反转为主干HTTP API(webfetch)，AKShare降为可选快捷路径，实现环境无关。

---
## 元数据

| 字段 | 值 |
|------|---|
| skill_id | domestic-source-trust |
| version | 2.1 |
| updated | 2026-06-11 |
| method | Agent Skill规则驱动（零运维，环境无关） |
| config | `config/domestic_sources.yaml` + `config/domestic_search_templates.yaml` |
| env_requirement | 仅需webfetch能力；AKShare为可选增强（需Python+akshare库） |

---
## 核心原则

**信源可信度优先，HTTP API为主干，搜索引擎兜底。**

1. 统计数据/政策/法规类查询 → **必须优先webfetch官方API或官网** (硬性规则，见下)
2. 深度商业分析 → RSSHub/RSS直连 > 限定域名搜索
3. 所有关键数据 → 交叉验证
4. 所有输出 → 信源标注 + 信任度摘要

---
## 必读参考文件

Agent执行国内信源查询前，**必须已读取**以下配置文件：

| 文件 | 内容 | 使用场景 |
|------|------|---------|
| `config/domestic_sources.yaml` v1.1 | A-E级信源评级 + API通道 + 健康规则 | 确定信源级别和获取方式 |
| `config/domestic_search_templates.yaml` v1.1 | 12场景搜索模板 + RSSHub路由表 | 选择搜索策略和限定域名 |

**12场景搜索模板速查**（详见 `domestic_search_templates.yaml`）：

| 模板ID | 场景 | 级别 | 优先方法 |
|--------|------|------|---------|
| T01 | 进出口贸易数据 | A | webfetch统计局API → webfetch海关 → site:搜索 |
| T02 | 宏观经济指标 | A | webfetch统计局API → site:搜索 |
| T05 | 深度商业分析 | B | RSSHub/财新 → RSS → site:搜索 |
| T07 | 资本市场/上市公司 | B | webfetch巨潮/AKShare → RSSHub → site:搜索 |
| T11 | 供应链/制造业 | A+D | webfetch统计局API → site:搜索 |
| T12 | 新能源/碳中和 | A+B | site:财新/能源局 → 搜索 |

Agent在执行 `site:` 限定搜索时，必须从 `domestic_search_templates.yaml` 中选取对应模板的域名组合，不得自行编造域名。

---
## 统一输出标注体系

所有国内信源输出统一使用以下8种标注，**禁止使用旧版标注**（`[A1]`/`[A-v2]`/`[A-wb]`/`[B-fred]`等已废弃）：

| 标注 | 含义 | 获取方式 | Agent处理 |
|------|------|---------|----------|
| `[A-api]` | A级，通过HTTP API获取 | 统计局V2.0/世界银行/海关API等webfetch | 直接采信，最高优先 |
| `[A-ak]` | A级，通过AKShare快捷获取 | Python环境+akshare库（可选） | 同[A-api]，标注来源 |
| `[A-web]` | A级，通过webfetch官网获取 | 直接抓取.gov.cn原页面 | 直接采信 |
| `[A-src]` | A级，通过site:搜索官网链接 | 搜索引擎间接获取 | 采信，优先级略低于直接获取 |
| `[B1]` | B级已验证 | 财新/WallStreetCN等 + 交叉验证 | 采信，A级冲突时让步 |
| `[B0]` | B级未交叉验证 | 单源媒体 | 可采信但需注意 |
| `[D1]` | D级已交叉验证 | 钛媒体/36kr等 + 交叉验证 | 谨慎参考 |
| `[E0]` | E级/未知 | 百家号/头条号/SEO聚合站 | 不采信 |
| `[!!]` | 传闻-未验证 | 未经任何验证 | 禁止作分析依据 |

**降级路径标注**：降级时在标注间加箭头，如 `[A-api→A-src] CPI数据（统计局API超时，降级site:搜索）`

---
## 硬性规则（不可违反）

### 规则1：A级信源HTTP API优先（防信源降级滥用）

> 处理统计数据、政策、法规类查询时，**必须优先尝试webfetch官方API或官网页面**。
> 仅在API/官网不可达时，才使用 `site:` 限定搜索。
> **绝对禁止从非白名单域名采信关键数据。**

执行顺序（不可跳步）：
1. 查 `domestic_sources.yaml` → 该数据是否有官方HTTP API？
   - 有 → webfetch调用API获取结构化数据（标注`[A-api]`）→ 结束
   - 无 → 进入步骤1.5
1.5 是否有可用的AKShare函数？（仅限有Python环境且已安装akshare库的Agent）
   - 有 → 调用函数获取数据（标注`[A-ak]`）→ 结束
   - 无 → 进入步骤2
2. `site:` 限定域名搜索（搜索引擎缓存通常含静态内容，比直接抓取动态页面更稳定）
   - 从 `domestic_search_templates.yaml` 中选取对应模板的域名组合
   - 从结果中**只选取官网域名链接**，不采信转载站（标注`[A-src]`）
   - 成功 → 提取数据
   - 失败 → 进入步骤3
3. webfetch 该信源的 primary_url（降级，因动态网站可能抓不到内容，标注`[A-web]`）
   - 成功 → 提取数据
   - 失败（404/超时）→ 进入步骤4
4. webfetch 该信源的 fallback_url（着陆页备用）
   - 成功 → 从着陆页导航到具体数据
   - 失败 → 报告"该数据当前不可获取"

### 规则2：搜索必须限定域名

泛搜索 `online_search("越南关税")` 仅作为最后兜底，且结果中E级占比通常>60%。

限定域名搜索模板（从 `domestic_search_templates.yaml` 读取）：
- 贸易数据：`site:customs.gov.cn OR site:mofcom.gov.cn {关键词}`
- 宏观指标：`site:stats.gov.cn OR site:pbc.gov.cn {关键词}`
- 深度分析：`site:caixin.com OR site:wallstreetcn.com {关键词}`
- 科技动态：`site:36kr.com OR site:latepost.com {关键词}`

### 规则3：B级信源RSSHub优先

> B级信源获取优先级：RSSHub路由 > 原生RSS > site:限定搜索
> RSSHub直接解析原始网站结构，保证链接直指原始出处，无转载污染。

### 规则4：E级信源不采信

> E级（百家号/头条号/营销号/SEO聚合站）NEVER作为分析依据。
> 仅当A-D级引用到E级内容时，作为"市场情绪"参考，并标注[情绪参考]。

---
## API直连通道（v2.0重构：HTTP API为主干）

> 两层架构：L1 HTTP API(webfetch原生) → L1.5 AKShare(可选快捷)
> 通道标注统一使用上方8种标注体系

### 路由规则

```
Agent收到数据查询请求
  ↓
判断：国内/海外/对比
  ├── 纯国内 → L1 HTTP API → L1.5 AKShare(可选) → site:搜索/webfetch
  ├── 纯海外 → 海外Skill
  └── 对比 → L1国内API + L3国际API → 交叉验证
```

### 按数据类型的路由表

| 数据类型 | 优先通道 | 备选 | 标注 |
|---------|---------|------|------|
| GDP/CPI/PPI等17项常规 | L1 统计局V2.0 | L1.5 AKShare快捷 | `[A-api]` / `[A-ak]` |
| 分省/分行业/人口/就业 | L1 统计局V2.0 | site:搜索 | `[A-api]` / `[A-src]` |
| 全球GDP/CPI/汇率对比 | L3 世界银行 | L3 FRED(美国) | `[A-api]` |
| 美国宏观深度(80万+指标) | L3 FRED(需Key) | L3 世界银行 | `[A-api]` / `[B1]` |
| HS编码级双边贸易 | L3 UN Comtrade(待Key) | L1 AKShare快捷 | `[A-api]` / `[A-ak]` |
| 上市公司公告/行情 | L1 AKShare快捷 | webfetch巨潮 | `[A-ak]` / `[A-web]` |
| 每日新闻摘要 | 中国日报C级API | B级RSS | `[D1]` |

### L1 统计局V2.0 操作手册（webfetch原生前端）

**Base URL**: `https://data.stats.gov.cn/dg/website/publicrelease/web/external`

**健康校验**：Agent首次使用本通道时，应先webfetch测试Base URL是否返回200。若连续失败3次，标记该通道为不可用，降级到site:搜索，并提示用户"统计局API端点可能已变更，建议更新技能文档"。

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

**rootId说明**：已验证该rootId适用于CPI/GDP/PMI等国家统计局常规指标。若用于其他指标POST返回空，请尝试从Step 1或Step 2的响应体中提取对应的rootId。

时间编码：月度=YYYYMM+后缀MM / 季度=YYYYQ+后缀SS / 年度=YYYY+后缀YY

**关键注意**：
- 同一指标因时间分片对应多个cid（通常5年一段），需分别请求后本地拼接
- 跨cid时indicatorId可能不同，每个cid都要重新Step 2
- `i_mark`含统计口径说明（基期/计算方法），展示数据时必须附带
- 日限额1000次，单次查询最多3步=3次请求
- **Step 1搜索无结果时**：不执行"树遍历"（Agent无法手动操作网页），直接降级到webfetch官网或site:搜索

### L3 世界银行操作手册

**Base URL**: `https://api.worldbank.org/v2`

**健康校验**：Agent首次使用时，webfetch测试 `GET https://api.worldbank.org/v2/country/CN?format=json&per_page=1` 是否返回200。连续3次失败则标记通道不可用。

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

### L1.5 AKShare 快捷通道（可选增强）

> 若Agent环境确认有Python且已安装akshare库，可直接调用函数作为快捷路径，无需走完整的L1三步走。
> **无Python环境的Agent跳过本节，不影响任何核心功能。**

**可用API函数清单（已本地验证）**：

| 函数名 | 数据 | 来源 | 更新频率 | 等价HTTP通道 |
|--------|------|------|---------|------------|
| macro_china_gdp | GDP季度数据 | 国家统计局 | 季度 | L1统计局V2.0 |
| macro_china_cpi | CPI月度 | 国家统计局 | 月度 | L1统计局V2.0 |
| macro_china_ppi | PPI月度 | 国家统计局 | 月度 | L1统计局V2.0 |
| macro_china_pmi | PMI制造业+非制造业 | 国家统计局 | 月度 | L1统计局V2.0 |
| macro_china_money_supply | M0/M1/M2 | 央行 | 月度 | webfetch pbc.gov.cn → site:pbc.gov.cn |
| macro_china_trade_balance | 贸易差额 | 海关总署 | 月度 | webfetch customs.gov.cn → site:customs.gov.cn |
| macro_china_fx_reserves_yearly | 外汇储备 | 外管局 | 年度 | webfetch safe.gov.cn → site:safe.gov.cn |
| macro_china_lpr | LPR利率 | 央行 | 月度 | webfetch pbc.gov.cn → site:pbc.gov.cn |
| macro_china_new_financial_credit | 新增社融 | 央行 | 月度 | webfetch pbc.gov.cn → site:pbc.gov.cn |
| macro_china_gdzctz | 固定资产投资 | 国家统计局 | 月度 | L1统计局V2.0 |
| macro_china_urban_unemployment | 城镇失业率 | 国家统计局 | 月度 | L1统计局V2.0 |
| macro_china_exports_yoy | 出口同比 | 海关 | 月度 | webfetch customs.gov.cn → site:customs.gov.cn |
| macro_china_imports_yoy | 进口同比 | 海关 | 月度 | webfetch customs.gov.cn → site:customs.gov.cn |
| macro_china_industrial_production_yoy | 工业增加值同比 | 国家统计局 | 月度 | L1统计局V2.0 |
| macro_china_consumer_goods_retail | 社会消费品零售 | 国家统计局 | 月度 | L1统计局V2.0 |
| stock_notice_report | 上市公司公告 | 巨潮 | 实时 | webfetch巨潮 |
| stock_zh_a_hist | A股历史行情 | 东方财富 | 日度 | webfetch eastmoney.com → site:eastmoney.com |

**调用示例**（仅限有Python环境的Agent）：

```
用户: "最新CPI数据是多少？"

方案A（HTTP API，通用）:
  Agent执行: webfetch "https://data.stats.gov.cn/dg/website/publicrelease/web/external/query?search=CPI&pagenum=1&pageSize=10"
  → 取cid → 获取indicatorId → POST取数据
  Agent输出: [A-api] 统计局V2.0/CPI 2026年05月 → CPI同比1.2%

方案B（AKShare快捷，需Python）:
  Agent执行: python -c "import akshare as ak; print(ak.macro_china_cpi().head(1))"
  Agent输出: [A-ak] AKShare/macro_china_cpi 2026年05月 → CPI同比1.2%
```

### 待Key激活通道

| 通道 | 需要什么 | 价值 | 优先级 | 状态 |
|------|---------|------|--------|------|
| FRED | 免费API Key | 80万+美国宏观指标 | 中 | 待申请 |
| UN Comtrade | 免费注册+确认端点 | HS编码级双边贸易 | 高 | 待注册 |
| DailyHotApi | — | Vercel自部署（待完成） | 尚未部署，Agent忽略 |
| 起零数据 | 免费Token | CCTV/澎湃/Tencent | 低 | 待申请 |

### 降级自动触发规则

1. L1统计局V2.0 API超时/404 → 降级到site:stats.gov.cn搜索
2. L1统计局V2.0 Step1搜索无结果 → 不执行树遍历，直接降级到webfetch官网或site:搜索
3. L3世界银行API超时 → 重试1次 → 降级到site:搜索国际媒体
4. L1.5 AKShare函数调用报错 → 自动回退到L1完整三步走

### 降级链路状态矩阵

> Agent执行国内数据查询时的完整降级决策树。

| 链路 | 层级 | 可用性 | 典型失败原因 | 切换条件 | 切换目标 | 标注 |
|------|------|--------|------------|---------|---------|------|
| L1 API → site:搜索 | L1→3 | ~85% | API超时/404/搜索无cid | 3次请求失败 | site:stats.gov.cn搜索 | `[A-api→A-src]` |
| L1 API → webfetch官网 | L1→2 | ~80% | 搜索无cid | Step1返回空 | webfetch统计局官网 | `[A-api→A-web]` |
| webfetch官网 → site:搜索 | L2→3 | ~80% | 官网JS渲染/改版 | webfetch返回无数据 | site:stats.gov.cn搜索 | `[A-web→A-src]` |
| site:搜索 → 泛搜索 | L3→4 | ~70% | 官网无相关页面 | 限定搜索0条结果 | 去site:限定泛搜索 | `[A-src→B1]` |
| 泛搜索 → webfetch原始页 | L4→2 | ~60% | 动态加载页无内容 | webfetch返回空 | webfetch目标URL直接抓 | `[B1→A-web]` |
| L3世界银行 → site:搜索 | L3→3 | ~95% | 网络超时/DNS | 超时>10s | 国际媒体site:搜索 | `[A-api→A-src]` |
| L1.5 AKShare → L1完整三步走 | L1.5→1 | ~90% | 函数报错/库未安装 | 异常或ImportError | L1统计局V2.0完整流程 | `[A-ak→A-api]` |

**完整降级链示例**（以CPI查询为例）：

```
用户: "最新CPI数据"
  ↓ L1: webfetch统计局V2.0搜索"CPI"
  ├── 搜索到cid → 获取indicatorId → POST取数据 → [A-api] → 结束
  ├── 搜索无结果 → webfetch: stats.gov.cn
  │   ├── 成功 → [A-web] → 结束
  │   └── 失败(JS渲染) → site:stats.gov.cn CPI
  │       ├── 有结果 → [A-src] → 结束
  │       └── 无结果 → [B1] 标注[数据缺口]
  └── API超时/404 → site:stats.gov.cn CPI
      ├── 有结果 → [A-src] → 结束
      └── 无结果 → 泛搜索 → [B1] 标注[数据缺口]

若有Python环境 + akshare:
  可直接: python -c "ak.macro_china_cpi()" → [A-ak] → 结束
  失败则: 回退L1完整三步走
```

**降级记录规则**：每次降级均需在输出中标注实际使用的链路，如 `[A-api→A-src] CPI数据（API超时，降级site:搜索）`

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

### 数值型数据容差带

分两档，不同指标类型的合理偏差范围不同：

**官方统计数据**（GDP/CPI/PPI/贸易额等，来源为国家统计局/海关/央行）：
- 两个独立信源差异 ≤3% → 视为**一致**，采信更高级别版本，注明"另有信源给出X值，差异在合理范围"
- 差异 3%-10% → 采信更高级别版本，标注[数据偏差]和两方数值
- 差异 >10% → 视为**冲突**，标注[数据冲突]，以A级为准，提醒用户注意

**调查/预测类数据**（PMI/失业率/行业调查等，含抽样误差）：
- 差异 ≤5% → 视为**一致**
- 差异 5%-15% → 标注[数据偏差]
- 差异 >15% → 视为**冲突**

---
## 信源信任度摘要

> 每次输出开头必须附加"信源信任度摘要"区块，格式：

```
【信源信任度摘要】A级 3条 | B级 5条 | D级 2条 | 交叉验证通过 8条 | 单源待验证 3条 | 整体可信度：高
```

可信度评级标准：
- **高**：A级占比>50% 且 交叉验证率>80%
- **中**：B级占比>50% 且 交叉验证率>60%
- **低**：D级以下占比>30% 或 交叉验证率<50%

---
## RSS存活监控

> Agent每次调用国内B级数据时，如果某个RSS/RSSHub源连续**2个自然日**fetch结果均为0条，
> 应主动向用户提示：`[RSS告警] XXX信源可能失效，建议验证`

---
## 国内错误处理矩阵

以下错误码仅涉及国内信源通道，海外错误码（E04/E05/E06/E07）见 SKILL.md。

| 编号 | 错误场景 | 错误码 | 检测方式 | 处置策略 | 恢复动作 |
|------|---------|--------|---------|---------|---------|
| E01 | AKShare函数报错/函数名变更 | `AKSHARE_ERR` | try/except捕获异常/ImportError | 降级：L1统计局V2.0完整三步走 | 记录异常函数名，日志标注`[AKSHARE降级]` |
| E02 | 统计局V2.0日限额耗尽 | `NBS_LIMIT` | HTTP 429/403 | 跳过L1，降级到site:搜索 | 告知用户"L1今日限额已用完，降级搜索"，次日自动恢复 |
| E03 | 世界银行API超时 | `WB_TIMEOUT` | HTTP超时>10s | 重试1次 → 降级到site:搜索国际媒体 | 记录超时指标ID |
| E08 | 国内搜索site:无结果 | `SEARCH_EMPTY` | 搜索返回0条结果 | 扩大搜索范围（去site:限定用泛搜索） | 标注`[数据缺口]`，告知用户权威源未检索到相关数据 |
| E09 | 统计局API端点变更 | `API_ENDPOINT_CHANGED` | 健康校验连续3次失败 | 标记通道不可用，降级site:搜索 | 告知用户"API端点可能已变更，建议更新技能文档" |

**恢复优先级**：E09(API可用性) > E02 > E01 > E03 > E08

**国内服务依赖分级**：

| 服务 | 级别 | 降级动作 | 监控方法 |
|------|------|---------|---------|
| 统计局V2.0 API | A | 降级到site:搜索 → webfetch官网 | 健康校验+HTTP状态码 |
| 世界银行 API | A | 降级到site:搜索国际媒体 | 健康校验+超时检测 |
| AKShare | B | 函数报错 → L1完整三步走 → site:搜索 | 调用时try/except |
| 中国日报API（suyanw.cn）| C | 跳过，用B级RSS或online_search | 调用时schema校验 |

---
## 安全规则

- API Key用环境变量存储，严禁写入脚本或技能文档
- JSON API返回数据需通过schema校验，防止注入（校验函数模板见SKILL.md）
- webfetch访问.gov.cn时使用HTTPS，不降级到HTTP
- C级及以下API返回数据必须校验后才能使用

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
- 引用原文时，在引用后用括号标注规范名称
- Agent分析和输出中必须规范

### 免责声明

Agent每次输出情报分析结果时，末尾必须附加以下免责声明（可折叠）：

> **免责声明**：本信息基于公开信源自动收集整理，仅供参考，不构成任何投资、法律或商业决策建议。数据可能存在延迟、偏差或遗漏，请以官方发布为准。

**执行规则**：
- 完整分析报告 → 文末单独一行，不可省略
- 简短问答（<3条数据）→ 可省略完整声明，但需含"仅供参考"
- 用户明确要求不附加时 → 不附加

---
## 与海外Skill联动

| 场景 | 路由 | 操作 |
|------|------|------|
| 纯国内问题 | 本Skill | L1 HTTP API → L1.5 AKShare(可选) → site:搜索 |
| 纯海外问题 | SKILL.md | CDN JSON → 在线搜索 |
| 国内外交叉 | 双Skill联动 | 按 `docs/compare_protocol.md` 协议执行，国内[X1]+海外[OV1]交叉验证 |
| 全球商业雷达 | SKILL.md | 14模块CDN → 信号检测 → 国内补充 |
| 国际宏观数据 | 本Skill L3 | 世界银行/FRED直接API |
| 中美GDP对比 | 本Skill L1+L3 | 统计局V2.0中国GDP + 世界银行美国GDP，口径对齐按compare_protocol第3节 |

**联动协议**：详见 `docs/compare_protocol.md`（请求路由字段 + 响应字段 + 冲突消解规则 + 执行模板）

---
## 变更日志

- v2.1 (2026-06-11): 4处逻辑修正 — 规则1步骤1.5独立化、rootId加适用说明+异常提示、DailyHotApi优先级标—、AKShare函数表等价通道补全降级路径(→标注)
- v2.0 (2026-06-11): 重大重构 — AKShare从L1降为L1.5可选快捷、L1改为HTTP API(webfetch)主干、删除树遍历降级路径、标注体系统一为8种(废弃旧标注)、新增API健康校验+端点变更错误码E09、补充安全规则/免责声明/领土地名规范(从SKILL.md同步)、容差带分两档、RSS监控改为自然日、DailyHotApi标待部署
- v1.4 (2026-06-11): 审查修复 — 国内错误矩阵迁入、国内服务依赖分级迁入、文件路径移除scripts/前缀
- v1.3 (2026-06-11): Phase 3文档更新
- v1.2 (2026-06-11): 新增API直连通道三层架构
- v1.1 (2026-06-11): 整合老K 8条建议 + AKShare API优先策略
- v1.0 (2026-06-11): 初始版本
