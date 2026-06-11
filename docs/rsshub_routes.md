---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '2911cf8e-757a-455e-9a79-022df1ede6be'
  PropagateID: '2911cf8e-757a-455e-9a79-022df1ede6be'
  ReservedCode1: 'e78a2bde-d7f3-4957-83c4-14aa7158254b'
  ReservedCode2: 'e78a2bde-d7f3-4957-83c4-14aa7158254b'
---

# RSSHub 常用路由速查

> Agent读取本文件的条件：用户需求触发引擎B，需要查找特定网站的RSSHub路由。

## 调用格式

```
GET {RSSHUB_BASE_URL}/路由?format=json
```

完整路由文档：https://docs.rsshub.app/

## 按角色/场景分类

### 政府/监管机构

| 目标网站 | 路由 | 说明 |
|---------|------|------|
| USTR公告 | `/ustr/press-releases` | 美国贸易代表署新闻 |
| Federal Register | `/federalregister/{agency}` | 联邦公报(按机构) |
| BIS出口管制 | `/federalregister/department-of-commerce-bureau-of-industry-and-security` | BIS规则 |
| SEC文件 | `/sec/filings/{ticker}` | 按股票代码查SEC文件 |
| EU官方公报 | `/eu/official-journal` | EU法规 |
| 中国商务部 | `/mofcom/article/{category}` | 商务部通知公告 |

### 财经媒体

| 目标网站 | 路由 | 说明 |
|---------|------|------|
| Financial Times | `/ft/{category}` | 按板块 |
| Wall Street Journal | `/wsj/opinion` | WSJ观点版 |
| Reuters | `/reuters/{topic}` | 按主题 |
| CNBC | `/cnbc/{topic}` | 按主题 |
| South China Morning Post | `/scmp/{category}` | SCMP按板块 |

### 科技/产业

| 目标网站 | 路由 | 说明 |
|---------|------|------|
| TechCrunch | `/techcrunch/{tag}` | 按标签 |
| The Information | `/theinformation/{category}` | 付费内容标题 |
| 36Kr | `/36kr/motif/{id}` | 36氪话题 |
| IT桔子 | `/itjuzi/investment` | 投融资事件 |

### 社交媒体

| 目标网站 | 路由 | 说明 |
|---------|------|------|
| X/Twitter用户 | `/twitter/user/{username}` | 某用户推文 |
| X/Twitter搜索 | `/twitter/search/{keyword}` | 关键词搜索 |
| X/Twitter列表 | `/twitter/list/{id}` | Twitter列表 |
| Reddit | `/reddit/subreddit/{name}` | 某子版块 |
| Reddit搜索 | `/reddit/search/{keyword}` | Reddit搜索 |

### 企业/数据平台

| 目标网站 | 路由 | 说明 |
|---------|------|------|
| World Bank数据 | `/worldbank/doc` | 世界银行文件 |
| IMF报告 | `/imf/publications` | IMF出版物 |
| WTO文件 | `/wto/disputes` | WTO争端 |
| UN Comtrade | 无直接路由 | 用online_search替代 |

### 东南亚本地媒体

| 目标网站 | 路由 | 说明 |
|---------|------|------|
| VnExpress | `/vnexpress/{category}` | 越南快讯 |
| The Star | `/thestar/{category}` | 马来西亚星报 |
| Bangkok Post | `/bangkokpost/{category}` | 曼谷邮报 |

## 降级策略

当RSSHub路由不可用时，按以下优先级降级：

1. **online_search** `site:docs.rsshub.app <关键词>` 验证路由是否仍存在（路由变化快，静态文档可能过时）
2. **webfetch** 直接访问 `https://docs.rsshub.app/routes/<分类>` 实时确认
3. **online_search** `site:<目标网站域名> <关键词>` 搜索替代信息（搜索引擎缓存比webfetch更可靠）
4. **webfetch** 直接访问目标页面，提取关键信息
5. 告知用户路由可能过时，建议检查RSSHub文档更新

## 路由实时验证规则

Agent在使用本文件中的路由前，应先验证路由是否仍然有效：

1. **首次使用某路由** → 直接调用，如果返回404则走降级策略
2. **路由返回异常（空数据/格式错误）** → 先用 `online_search` 查 `site:docs.rsshub.app <网站名>` 确认路由是否变更
3. **确认路由已变更** → 更新本地记忆，后续使用新路由
4. **路由确认不存在** → 走降级策略第3-5步

## 注意事项

- 路由名称可能随RSSHub版本更新而变化，以官方文档为准
- 某些路由需要配置环境变量（如Twitter API Key），在Vercel环境变量中设置
- `format=json` 参数确保返回JSON而非XML
- 复杂路由参数参考官方文档中的具体说明