# 双技能联动 compare_request 协议 v1.0

> 本文档定义 SKILL.md（海外）与 SKILL_CN.md（国内）之间的请求路由、响应格式与冲突消解规则。
> Agent执行双Skill联动时，必须遵循本协议。

---
## 元数据

| 字段 | 值 |
|------|---|
| version | 1.0 |
| updated | 2026-06-11 |
| scope | SKILL.md + SKILL_CN.md 双核联动 |

---
## 1. 请求路由字段

Agent在判断需要双核联动时，应构造如下请求对象（逻辑结构，无需序列化）：

```yaml
compare_request:
  intent_type:     # 必填。枚举：macro | trade | policy | industry | risk | comparison
  region:          # 必填。枚举：domestic | overseas | cross（国内外交叉）
  indicator:       # 条件必填。指标ID（如 GDP/CPI/tariff_rate/FDI），intent_type=macro|comparison时必填
  time_range:      # 可选。时间范围（如 2025Q1-2026Q2），默认取最新
  priority:        # 可选。枚举：high | medium | low，默认 medium
  keywords:        # 可选。用户原始查询关键词列表，供搜索模板匹配
```

### intent_type 枚举说明

| 值 | 含义 | 典型场景 | 路由倾向 |
|----|------|---------|---------|
| macro | 宏观经济指标 | "中美GDP对比" | 国内L1/L3 + 海外finance |
| trade | 贸易/关税/制裁 | "301关税对东南亚影响" | 海外global_business + 国内L1贸易 |
| policy | 政策/法规 | "USTR新调查" | 海外geopolitics + 国内L2政策 |
| industry | 产业/供应链 | "越南半导体产能" | 海外tech_industry + 区域JSON |
| risk | 风险/地缘 | "台海局势对供应链影响" | 海外geopolitics + esg |
| comparison | 明确的中外对比 | "中越制造业成本对比" | 国内L1 + 海外多模块 |

### region 路由决策树

```
用户问题
  ↓
含国内指标关键词（GDP/CPI/PMI/社融/LPR/A股/海关/国务院）？
  ├── 是 → region=domestic → SKILL_CN.md
  └── 否 → 含海外区域/国家名称？
        ├── 是 → 含国内对比需求？
        │     ├── 是 → region=cross → 双Skill联动
        │     └── 否 → region=overseas → SKILL.md
        └── 否 → 含全球/跨国关键词？
              ├── 是 → region=cross → 双Skill联动
              └── 否 → 默认 region=overseas → SKILL.md
```

---
## 2. 响应字段

每个Skill返回数据时，应附带以下元数据：

```yaml
compare_response:
  data_source:     # 必填。数据来源标识（如 [A-api]/[A-wb]/[CDN finance.json]）
  confidence:      # 必填。枚举：high | medium | low
  caliber:         # 必填。统计口径说明（如"累计同比"/"现价美元"/"不变价本币"）
  unit:            # 必填。单位（如 % / 亿美元 / 指数点）
  time_coverage:   # 必填。数据时间范围（如 2025Q1-2026Q1）
  freshness:       # 必填。数据更新时间戳（ISO 8601）
  conflict_resolution:  # 条件必填。冲突时说明消解方式（见第3节）
```

### confidence 评级规则

| 级别 | 条件 |
|------|------|
| high | A级信源 + 已交叉验证 |
| medium | B级信源 或 A级但未交叉验证 |
| low | C级及以下 或 数据口径不明确 |

---
## 3. 冲突消解规则

当国内和海外数据对同一指标给出不同值时，按以下优先级消解：

### 规则1：信源等级优先

| 场景 | 消解策略 |
|------|---------|
| 国内A级 vs 海外数据 | 以国内A级为准，海外数据作为参考标注 |
| 海外A级（世界银行）vs 海外B级 | 以世界银行为准 |
| 国内A级 vs 国内A级 | 以发布日期更近的为准；同日发布则取国家统计局 |
| 均为B级 | 取保守值（对负面判断取更严重值），标注[数据偏差] |

### 规则2：口径一致性检查

比较前必须检查 `caliber` 字段：

| 口径差异 | 处理方式 |
|---------|---------|
| 同一口径 | 直接比较 |
| 累计同比 vs 当月同比 | **不可直接比较**，输出警告，各自标注口径 |
| 现价 vs 不变价 | **不可直接比较**，需折算（标注折算系数来源） |
| 人民币 vs 美元 | 用同期汇率折算，标注汇率来源和日期 |
| 年度 vs 季度 | 需对齐时间粒度，年度数据不应用于季度比较 |

### 规则3：时效性优先

- 发布日期差 > 30天 → 以较新的为准，标注旧数据过期风险
- 发布日期差 ≤ 30天 → 按规则1处理

---
## 4. 联动执行模板

### 模板A：宏观指标对比（最常见）

```
用户: "中美GDP增速对比"
Agent执行:
  1. 构造 compare_request:
     intent_type: macro, region: cross, indicator: GDP_growth,
     time_range: 最新年度, priority: high
  2. 国内侧: AKShare macro_china_gdp → [A-api] 中国GDP增速
  3. 海外侧: 世界银行 NY.GDP.MKTP.KD.ZG → [A-wb] 美国GDP增速
  4. 口径检查: 中国=累计同比, 美国=年度同比 → 标注口径差异
  5. 输出: 双列对比表 + 口径说明 + 信源标注
```

### 模板B：贸易政策影响

```
用户: "301关税对东南亚出口影响"
Agent执行:
  1. 构造 compare_request:
     intent_type: trade, region: cross, indicator: tariff_rate,
     keywords: [301, 东南亚, 出口]
  2. 海外侧: CDN se_asia.json → 301相关high文章
  3. 国内侧: AKShare macro_china_exports_yoy → [A-api] 中国出口数据
  4. 交叉分析: 海外301政策动态 + 国内出口数据变化
  5. 输出: 政策动态表 + 出口数据变化 + 关联分析（标注[推断]）
```

### 模板C：即时验证

```
用户: "USTR刚刚发了新调查通知？"
Agent执行:
  1. 构造 compare_request:
     intent_type: policy, region: overseas, priority: high
  2. 引擎B: RSSHub /ustr/press-releases → 即时抓取
  3. 引擎A降级: CDN geopolitics_risk.json → 交叉验证
  4. 输出: 原文摘要 + 链接 + 影响评估
```

---
## 5. 禁止事项

1. **禁止强行对比口径不同的数据** — 不做"中国CPI 0.8% vs 美国CPI 3.2%"这种无口径说明的对比
2. **禁止仅用单一海外数据源做国内判断** — 国内数据必须走SKILL_CN.md
3. **禁止省略caliber说明** — 每个数值必须附带统计口径
4. **禁止用E级信源做消解依据** — 冲突时E级信源不参与判定

---
## 6. 口径一致性算法规格

> 本节定义跨源数据比较时的口径对齐规则。Phase 4将实现为Python函数 `compare_indicators()`。

### 6.1 常见口径差异矩阵

| 指标 | 国内口径（国家统计局/AKShare） | 海外口径（世界银行/IMF） | 对齐方式 |
|------|--------------------------|----------------------|---------|
| GDP | 累计同比，不变价人民币 | 年度增长率%，现价美元 | 不可直接比较，各自标注口径 |
| CPI | 当月同比%，环比% | 年均通胀率% | 取同比口径对齐，标注基数差异 |
| PMI | 制造业/非制造业分列 | 制造业单一值 | 仅比较制造业PMI |
| 贸易额 | 人民币计价/美元计价双口径 | 现价美元 | 统一用美元计价口径 |
| 汇率 | 央行中间价 | 市场汇率（年均） | 标注时点差异，中间价≠市场汇率 |

### 6.2 口径对齐三步法

```
Step 1: 读取两边数据的caliber字段
  ├── caliber相同 → 直接比较
  ├── caliber不同但可转换 → 执行转换，标注转换系数来源
  └── caliber不同且不可转换 → 输出警告，各自标注口径，不做数值对比

Step 2: 转换规则
  ├── 币种差异 → 用同期央行中间价折算，标注汇率日期
  ├── 计价方式差异（现价/不变价）→ 标注GDP deflator系数来源
  ├── 时间粒度差异 → 年度可拆季度平均，但不可反向
  └── 同比/环比差异 → 不可转换，各自标注

Step 3: 冲突消解
  ├── A级 vs A级 → 发布日期更新者优先
  ├── A级 vs B级 → A级优先
  ├── 官方 vs 第三方 → 官方优先
  └── 均为B级 → 取保守值（负面判断取更严重值）
```

### 6.3 compare_indicators() 函数规格（Phase 4实现）

```python
def compare_indicators(
    value1: float, source1: str, caliber1: str, confidence1: str,
    value2: float, source2: str, caliber2: str, confidence2: str,
    tolerance_pct: float = 3.0
) -> dict:
    """
    跨源指标比较。
    
    Returns:
        {
            "comparable": bool,        # 是否可直接比较
            "alignment_action": str,   # "direct" | "converted" | "incomparable"
            "conversion_note": str,    # 转换说明（如有）
            "conflict": bool,          # 是否存在冲突
            "conflict_resolution": str,# 消解方式
            "preferred_value": float,  # 推荐采信值
            "preferred_source": str    # 推荐采信来源
        }
    """
    # Phase 4 实现
    pass
```

### 6.4 已知口径问题清单

| 问题 | 影响 | 修复计划 |
|------|------|---------|
| NHK World RSS时间格式 `+0000`（无冒号） | 71条east_asia文章无法正确判断时效，被保守保留 | Phase 4: `parse_published_time()` 补充 `%Y-%m-%dT%H:%M:%S.%f%z` 格式 |
| AKShare返回季度累计值 vs 世界银行年度值 | GDP对比时口径不匹配 | 本规则6.2处理：不可直接比较 |
| 中国CPI权重不公开 | 与海外CPI不可严格对比 | 输出时标注"权重差异" |
