---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '8d9301d9-2ded-4bb9-90bb-30e43bcf684d'
  PropagateID: '8d9301d9-2ded-4bb9-90bb-30e43bcf684d'
  ReservedCode1: 'a9423212-dbc3-4aaf-87c4-b14332835f0e'
  ReservedCode2: 'a9423212-dbc3-4aaf-87c4-b14332835f0e'
---

---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: 'c402f67d-51d5-403d-af57-d0404b5d3c1b'
  PropagateID: 'c402f67d-51d5-403d-af57-d0404b5d3c1b'
  ReservedCode1: '701d07ea-6830-4e67-8945-39671c375621'
  ReservedCode2: '701d07ea-6830-4e67-8945-39671c375621'
---

# search_queries.md v3.3 — Google News RSS搜索词设计意图
# 每个搜索词的设计理由、语言、地域、效果评价
# 改搜索词前先看此文档，理解设计意图后再改

## 搜索策略升级（v3.3）

### 宽窄组合拳
每个主题设一个**宽口查询**（确保不漏）和数个**精准查询**（确保核心）。
- 宽口：`semiconductor chip` → 捕获所有半导体话题
- 精准：`"semiconductor equipment" export ban China` → 聚焦出口管制
- 精准：`TSMC factory US Japan Germany` → 聚焦产能扩张

### 信号性查询
专门捕捉突发、早期信号，用引号精确匹配：
- `"first ever" breakthrough discovery` → 前所未有的突破
- `"unprecedented" "record high" "record low"` → 极端事件
- `"supply disruption" "force majeure"` → 供应链中断
- `"emergency meeting" central bank` → 央行紧急会议
- `"sanctions announced" "new restrictions"` → 新制裁

### 多语言覆盖
区域模块中加入当地语言搜索词，捕获本地媒体独有报道：
- 越南语：`xuất khẩu thuế quan đầu tư FDI Việt Nam`
- 印尼语：`ekspor tarif investasi Indonesia`
- 阿拉伯语：`السعودية استثمار تجارة تصدير اقتصاد`
- 葡语：`Brasil exportação comércio investimento economia`
- 西语：`México exportación comercio inversión economía`
- 日语：`日本 輸出 貿易 規制 経済`
- 韩语：`한국 수출 무역 투자 경제`
- 俄语：`Россия экономика торговля инвестиции экспорт`
- 德语：`Deutschland Wirtschaft Handel Investition Industrie`
- 法语：`France économie commerce investissement industrie`
- 印地语：`भारत निर्यात व्यापार निवेश अर्थव्यवस्था`

---

## global_business（全球商业与产业链重构）

### v3.3升级逻辑
从"只看中国出海"→"看全球产业链怎么动"。

### 新增搜索词

| 搜索词 | 意图 | 语言 | 备注 |
|--------|------|------|------|
| global supply chain reshoring nearshoring friendshoring factory relocation | 全球产业链重构全息信号 | EN | 4个-reshoring词并列=最高概率命中 |
| India manufacturing rise electronic vehicle semiconductor plant | 印度制造崛起 | EN | EV+半导体代表高端制造 |
| Mexico nearshoring manufacturing investment USMCA factory | 墨西哥近岸 | EN | USMCA区分离岸关税 |
| global industrial policy CHIPS Act IRA EU Green Deal industrial plan | 各国产业政策 | EN | 3大法案覆盖美欧 |
| multinational supply chain diversification strategy 2026 | 跨国公司多元化 | EN | 加年份限流 |
| Vietnam Indonesia manufacturing hub alternative China | ASEAN替代性 | EN | 不提中国也命中相关 |
| Eastern Europe manufacturing investment Poland Czech Hungary | 东欧制造 | EN | 容易被忽略的转移目的地 |

### 信号性查询

| 搜索词 | 意图 |
|--------|------|
| "supply disruption" "force majeure" supply chain trade | 供应链中断信号 |
| "sanctions announced" "new restrictions" trade export control | 新制裁/管制信号 |
| "first ever" breakthrough discovery trade technology | 前所未有突破 |

---

## finance_global（全球宏观与资本流动）

### v3.3升级逻辑
从"按资产品类分层"→"加上系统性风险+去美元化维度"。

### 新增搜索词

| 搜索词 | 意图 | 备注 |
|--------|------|------|
| global systemic risk financial stability report IMF BIS | 系统性风险 | IMF/BIS报告=权威 |
| emerging market debt crisis default restructuring 2026 | 新兴市场债务危机 | 2026斯里兰卡/加纳之后谁下一个 |
| global liquidity tightening capital outflow emerging market | 全球流动性紧缩 | 紧缩→资金从EM撤出 |
| de-dollarization central bank digital currency cross-border payment | 去美元化+CBDC | 长期趋势但加速时即信号 |
| BRICS currency alternative settlement system SWIFT | BRICS替代体系 | 旁路系统=实质去美元化 |
| sovereign wealth fund investment shift allocation 2026 | 主权基金调仓 | 海湾石油美元流向变化 |

### 信号性查询

| 搜索词 | 意图 |
|--------|------|
| "emergency meeting" central bank rate decision | 央行紧急会议 |
| "warning" IMF World Bank BIS financial stability | 国际组织警告 |
| "record high" "record low" market bond yield price | 市场极端记录 |

---

## tech_industry（全球科技与工业前沿）

### 设计逻辑
跨地域主题模块，只追前沿不论产地。按技术领域分组。

| 搜索词 | 意图 | 备注 |
|--------|------|------|
| semiconductor chip foundry TSMC Samsung Intel ASML | 晶圆厂全景 | 5大关键公司 |
| "semiconductor equipment" export ban China restriction | 精准：设备出口禁令 | 引号+组合=高信噪 |
| CHIPS Act EU Chips Act Japan chip fab investment | 各国芯片产业政策 | 三大补贴计划 |
| AI regulation ban deepfake generative AI | AI监管 | ban+regulation双管 |
| AI chip export control NVIDIA compute restriction | AI算力管制 | NVIDIA=核心标的 |
| electric vehicle battery solid state charging infrastructure | EV+电池+充电 | solid-state是新变量 |
| weight loss drug GLP-1 Ozempic pharmaceutical | GLP-1减肥药 | 2024-2026最大医药赛道 |
| space industry launch satellite Starlink military | 商业航天 | Starlink+军事=新维度 |
| quantum computing breakthrough error correction | 量子计算 | breakthrough=信号词 |

---

## energy_commodities（全球能源与大宗商品）

### 设计逻辑
金融模块有价格维度，本模块是物理维度：谁在争、谁在禁、谁在转型。

| 搜索词 | 意图 | 备注 |
|--------|------|------|
| OPEC+ oil output quota production cut price war | OPEC+产量政策 | quota+cut+price war三态 |
| strategic petroleum reserve release drawdown | SPR释放 | 释放=供给紧张信号 |
| critical mineral lithium cobalt nickel rare earth supply chain | 关键矿产全景 | 4矿种+SC |
| mine nationalization export ban mineral Indonesia Chile | 矿产国有化/出口禁 | 两个典型案例国 |
| global food crisis grain export ban wheat corn rice | 粮食安全 | ban=直接信号 |
| EU carbon border tax CBAM steel aluminum fertilizer | CBAM落地 | 覆盖3大行业 |
| nuclear energy renaissance reactor SMR project | 核能复兴 | SMR=新变量 |
| hydrogen green blue project investment policy | 氢能 | green vs blue=转型方向 |

---

## geopolitics_risk（全球治理与地缘风险）

### 设计逻辑
跨地域的地缘政治模块，纯事件驱动。

| 搜索词 | 意图 | 备注 |
|--------|------|------|
| UN Security Council resolution sanctions vote veto | 安理会行动 | veto=大国否决信号 |
| Russia Ukraine ceasefire negotiation peace deal frontline | 俄乌和谈 | ceasefire=直接信号 |
| Israel Gaza ceasefire hostage negotiation | 以加和谈 | |
| South China Sea Taiwan Strait military tension patrol | 台海/南海军事 | |
| Iran nuclear deal JCPOA diplomacy enrichment | 伊朗核协议 | enrichment=实质进展 |
| cyber attack critical infrastructure ransomware state-sponsored | 网络攻击 | state-sponsored=国家级 |
| US election presidential policy trade tariff 2028 campaign | 美国大选 | 2028+campaign=前瞻 |
| sanctions announced new restrictions trade embargo | 新制裁 | 广口捕获所有新制裁 |

---

## esg_sustainability（ESG与可持续发展）

### 设计逻辑
欧美合规刚需，不再是可选项。

| 搜索词 | 意图 | 备注 |
|--------|------|------|
| ESG regulation disclosure requirement SEC EU CSRD ISSB | ESG法规全景 | SEC+EU+ISSB三体系 |
| EU taxonomy sustainable investment classification | 欧盟分类法 | 定义什么是"绿" |
| carbon credit offset market price greenwashing investigation | 碳信用市场 | greenwashing=风险信号 |
| sustainable supply chain due diligence forced labor regulation | 供应链尽职调查 | forced labor=核心合规 |
| EU deforestation regulation EUDR compliance implementation | EUDR | 企业高合规成本新规 |
| PFAS ban chemical regulation water contamination | PFAS禁令 | 永久化学品=新合规热点 |
| climate risk adaptation insurance loss damage extreme weather | 气候风险保险 | loss and damage=UN机制 |
| "greenwashing" scandal investigation penalty corporate | 信号：洗绿丑闻 | |

---

## region_*（区域模块通用升级逻辑）

所有8个区域模块统一新增4组维度：

### 新增分组

| 分组 | 搜索词模板 | 意图 |
|------|-----------|------|
| 政治+社会 | {区域} political stability protest election policy change | 政治风险信号 |
| 基础设施+科技 | {区域} infrastructure project port railway technology hub | 发展能力 |
| 气候+人口 | {区域} climate change drought flood demographic youth | 长期结构性风险 |
| 大国关系 | {区域} relations with US EU China Russia | 地缘定位 |
| 本地语言搜索 | 当地语言关键词 | 捕获本地媒体独有报道 |
| 信号性查询 | "supply disruption" "military escalation" 等 | 突发事件 |

### 需要持续优化的搜索词
- 某搜索词返回0条 → 可能是查询太窄/太新，需放宽或换词
- 某搜索词返回大量low relevance → 查询太宽，需加限定词
- 某重要话题总是漏掉 → 考虑新增搜索词或在keywords.yaml加关键词
- 多语言搜索词返回乱码/噪音 → 可能需调整hl/gl/ceid参数或换词

---

## cross_border_ecommerce（跨境电商）

### 设计逻辑
聚焦中国企业出海电商全链路：平台政策变动、关税/合规、物流支付。
核心视角：亚马逊封号→Temu关税→SHEIN IPO→TikTok Shop禁令，按平台分组。

| 搜索词 | 意图 | 备注 |
|--------|------|------|
| Amazon seller ban suspension policy change | 亚马逊政策变动 | 卖家最怕的封号 |
| "Amazon seller ban" account suspended listing removed | 精准：封号信号 | 引号+组合 |
| Temu tariff regulation EU US compliance investigation | Temu合规风险 | 欧美双管 |
| SHEIN IPO supply chain compliance forced labor | SHEIN上市+供应链 | forced labor=核心指控 |
| TikTok Shop ban suspension EU regulation | TikTok Shop监管 | 欧盟DSA为最大风险 |
| de minimis repeal small parcel tariff exemption end | 小额免税取消 | 直接影响Temu/SHEIN |
| EU digital services tax marketplace platform liability | 欧盟数字服务税 | 平台责任扩大 |
| VAT cross-border e-commerce retroactive audit | VAT追溯 | 卖家隐性风险 |
| customs seizure counterfeit product e-commerce import | 海关扣留 | 假冒品=高频事件 |

### 信号性查询

| 搜索词 | 意图 |
|--------|------|
| "platform ban" "total ban" marketplace seller | 平台封杀信号 |
| "customs detention" "forced recall" "product delisting" | 海关/召回信号 |
| "market exit" "platform shutdown" e-commerce | 市场退出信号 |

---

## trade_import_export（进出口贸易）

### 设计逻辑
不追价格追政策——301/232/反倾销/原产地规则，直接影响企业进出口成本。
按贸易管制→自贸协定→贸易壁垒三层分组。

| 搜索词 | 意图 | 备注 |
|--------|------|------|
| Section 301 tariff US China trade war escalation | 301关税 | 中美贸易核心 |
| Section 232 tariff steel aluminum national security | 232关税 | 钢铝+national security |
| anti-dumping countervailing duty investigation China | 双反调查 | 高频事件 |
| RCEP implementation trade agreement tariff reduction | RCEP执行 | 降税=机遇 |
| rules of origin transshipment circumvention trade | 原产地规则 | 转运规避=合规风险 |
| WTO dispute settlement ruling trade complaint | WTO争端 | 裁决=政策依据 |
| technical barrier trade TBT SPS import restriction | TBT/SPS壁垒 | 隐性保护主义 |
| import quota license trade restriction emergency | 配额/许可证 | 紧急限制=直接信号 |

### 信号性查询

| 搜索词 | 意图 |
|--------|------|
| "import ban" "export ban" "emergency restriction" | 贸易禁令信号 |
| "trade sanctions" "quota suspension" "mandatory recall" | 贸易制裁信号 |
| "sudden inspection" import export customs seizure | 突击检查信号 |

---

## global_risk（国际风险）

### 设计逻辑
企业级跨境风险——制裁清单/外资审查/征用/资本管制/主权违约。
互斥边界：不含国家间军事冲突（geopolitics_risk管）、不含宏观金融（finance管）。
用exclude词表确保互斥，命中"election""missile""interest rate hike"等词的文章降低评分。

| 搜索词 | 意图 | 备注 |
|--------|------|------|
| OFAC sanctions list designation entity update | OFAC清单更新 | 最高频制裁 |
| BIS entity list addition export control US | BIS实体清单 | 中国企业最常上 |
| EU sanctions package Russia China designation | 欧盟制裁包 | 含中国关联 |
| CFIUS review block acquisition national security | CFIUS审查/否决 | 中企并购最大障碍 |
| EU FDI screening investment review regulation | 欧盟FDI审查 | 2024法规落地 |
| expropriation nationalization foreign investment sovereign | 征收/国有化 | 极端风险 |
| forced divestiture sell-off foreign company order | 被迫出售 | TikTok式风险 |
| capital controls foreign exchange restriction | 资本/外汇管制 | 资金回不来 |
| sovereign default debt restructuring emerging market | 主权违约 | 新兴市场风险 |
| FCPA anticorruption enforcement compliance penalty | FCPA反腐 | 中企高风险 |

### 信号性查询

| 搜索词 | 意图 |
|--------|------|
| "blacklisted" "freeze order" "forced expropriation" | 制裁行动信号 |
| "capital controls imposed" "default declared" "force majeure invoked" | 风险升级信号 |
| "investment blocked" "deal blocked" national security review | 投资被阻信号 |

---

## chinese_firms_overseas（中企海外动态）

### 设计逻辑
跟踪50家重点中国企业的海外动态，按行业分组查询。
核心输入：企业名+事件词组合查询（如"BYD factory Europe tariff"）。
按行业分组：新能源车→半导体→电商→安防→光伏→基建→能源→制造→金融。

### 行业分组查询

| 分组 | 代表搜索词 | 意图 |
|------|-----------|------|
| 新能源车 | BYD factory Europe Hungary tariff | 比亚迪海外建厂+关税 |
| 新能源车 | CATL battery plant Hungary Germany | 宁德时代海外工厂 |
| 半导体 | Huawei ban overseas contract 5G chip | 华为海外禁令 |
| 半导体 | SMIC YMTC CXMT entity list sanctions | 芯片企业制裁 |
| 电商 | Temu EU regulation tariff forced labor | Temu合规 |
| 电商 | ByteDance TikTok ban EU DSA divestiture | TikTok禁令 |
| 安防 | DJI ban entity list restriction drone | 大疆禁令 |
| 安防 | Hikvision Dahua entity list ban surveillance | 海康大华制裁 |
| 光伏 | LONGi JinkoSolar tariff anti-circumvention | 光伏关税 |
| 基建 | CCCC CRRC CRCC CRECG Belt and Road | 基建企业一带一路 |
| 能源 | PetroChina Sinopec CNOOC overseas sanction | 三桶油海外 |
| 制造 | Xiaomi OPPO vivo overseas India patent | 手机企业海外 |
| 金融 | Bank of China ICBC CCB overseas sanctions | 中资银行海外 |

### 信号性查询

| 搜索词 | 意图 |
|--------|------|
| "construction halted" "contract terminated" "worker strike" Chinese company | 项目停工信号 |
| "license revoked" "forced divestiture" "added to list" Chinese firm | 许可/清单信号 |
| "compliance fine" "regulatory penalty" "investigation" Chinese overseas | 合规处罚信号 |

### 企业名单可升级说明
50家重点企业名单存储在 keywords.yaml 的 aux 词表中（英文名），更换/新增企业只需编辑 keywords.yaml 的 aux 字段，无需修改代码。