#!/usr/bin/env python3
"""
common.py v4.3 — 全球商业情报仪表盘共享工具库 (asyncio+aiohttp + RapidFuzz版)
v3.5: 顺序版止血，socket 10s + User-Agent + rate_limited
v4.0: asyncio+aiohttp全量异步重构，预期3-5分钟完成376源抓取
v4.2: title_similarity用RapidFuzz(206x faster)替代difflib,
      dedup_title_level用Bucket分桶(88x fewer comparisons)
v4.3: 新增 batch_resolve_gnews_urls() — 所有模块完成后批量解析GNews redirect,
      解决fetch_one()内GNews semaphore(5)瓶颈导致0/1140 canonical_url的问题
"""

import asyncio
import aiohttp
import feedparser
import json
import re
import hashlib
import os
import socket
import yaml
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor

try:
    from rapidfuzz import fuzz as _rf_fuzz
    def title_similarity(t1, t2):
        return _rf_fuzz.ratio(t1.lower(), t2.lower()) / 100.0
except ImportError:
    import difflib as _difflib
    def title_similarity(t1, t2):
        return _difflib.SequenceMatcher(None, t1.lower(), t2.lower()).ratio()

# 保留socket超时作为底层安全网
socket.setdefaulttimeout(10)

feedparser.USER_AGENT = "Mozilla/5.0 (compatible; OverseasDataHub/1.0; +https://github.com/WOHO99/overseas-data-hub)"

RATE_LIMITED_DOMAINS = ["news.google.com"]

# 全局并发控制
SEMAPHORE_GLOBAL = 50
SEMAPHORE_GNEWS = 5
MAX_PARSE_WORKERS = 2

_parse_executor = ThreadPoolExecutor(max_workers=MAX_PARSE_WORKERS)


# ============================================================
# 配置加载
# ============================================================

def load_keywords(config_dir, module_name):
    """从keywords.yaml加载指定模块的关键词。返回 (core, important, aux, signal, exclude)"""
    kw_path = os.path.join(config_dir, "keywords.yaml")
    if not os.path.exists(kw_path):
        print(f"  [WARN] keywords.yaml not found at {kw_path}, using empty keywords")
        return [], [], [], []

    with open(kw_path, "r", encoding="utf-8") as f:
        all_kw = yaml.safe_load(f)

    if module_name not in all_kw:
        print(f"  [WARN] Module '{module_name}' not in keywords.yaml, using empty keywords")
        return [], [], [], [], []

    mod_kw = all_kw[module_name]
    return (
        mod_kw.get("core", []),
        mod_kw.get("important", []),
        mod_kw.get("aux", []),
        mod_kw.get("signal", []),
        mod_kw.get("exclude", []),
    )


def load_source_authority(config_dir):
    """从keywords.yaml加载全局源权威度系数表。返回 dict{tag_pattern: coefficient}"""
    kw_path = os.path.join(config_dir, "keywords.yaml")
    if not os.path.exists(kw_path):
        return {}
    with open(kw_path, "r", encoding="utf-8") as f:
        all_kw = yaml.safe_load(f)
    return all_kw.get("source_authority", {}) or {}


def get_source_coefficient(source_tag, authority_map):
    """
    匹配源权威度系数。
    规则：exact match > prefix match (前缀匹配 GNews|xxx → GNews) > 默认1.0
    """
    if not authority_map:
        return 1.0
    # 精确匹配
    if source_tag in authority_map:
        return authority_map[source_tag]
    # 前缀匹配：取tag中 | 前的部分（如 "GNews | China Trade" → "GNews"）
    prefix = source_tag.split("|")[0].strip() if "|" in source_tag else source_tag.split(":")[0].strip()
    if prefix in authority_map:
        return authority_map[prefix]
    # 空格分隔的第一词（如 "FedReg | BIS" → "FedReg"）
    first_word = source_tag.strip().split()[0] if source_tag else ""
    if first_word in authority_map:
        return authority_map[first_word]
    return 1.0


# ============================================================
# 异步RSS抓取
# ============================================================

def _is_sensitive_url(url):
    return any(domain in url for domain in RATE_LIMITED_DOMAINS)


def _is_gnews_url(url):
    """判定URL是否为Google News跟踪链接"""
    return bool(url and "news.google.com" in url)


async def _resolve_gnews_redirect(session, gnews_url, timeout_sec=8):
    """
    解析GNews跟踪URL的最终跳转地址。
    在Actions环境（ubuntu）下news.google.com可达，本地可能不可达。
    成功返回canonical_url，失败返回None。
    """
    try:
        async with session.get(
            gnews_url,
            timeout=aiohttp.ClientTimeout(total=timeout_sec, connect=3),
            allow_redirects=True,
        ) as resp:
            if resp.status == 200:
                final_url = str(resp.url)
                # 确认不是还在google.com上
                if "google.com" not in final_url:
                    return final_url
    except Exception:
        pass
    return None


async def batch_resolve_gnews_urls(articles_by_file, concurrency=15, timeout_sec=6):
    """
    批量解析GNews跟踪URL的canonical_url（所有模块完成后专用）。
    
    问题：fetch_one()内GNews semaphore(5并发)限制下，大多数URL无法及时解析，
    导致生产数据中0/1140 canonical_url被填充。
    
    此函数以更高并发+更短超时作为post-module步骤专门处理。
    已有canonical_url的文章自动跳过。
    
    articles_by_file: {filename: [article_dicts]} — 原地修改(modifies in-place)
    返回: (resolved_count, total_gnews_count, elapsed_seconds)
    """
    import time as _time
    start = _time.monotonic()
    
    # 收集需要解析的文章
    resolve_items = []  # [(filename, article_index, gnews_url)]
    for filename, articles in articles_by_file.items():
        for idx, article in enumerate(articles):
            link = article.get("link", "")
            if _is_gnews_url(link) and "canonical_url" not in article:
                resolve_items.append((filename, idx, link))
    
    total_gnews = len(resolve_items)
    if not resolve_items:
        return 0, 0, 0.0
    
    print(f"  [BATCH_RESOLVE] {total_gnews} GNews URLs pending (concurrency={concurrency}, timeout={timeout_sec}s)")
    
    sem = asyncio.Semaphore(concurrency)
    headers = {"User-Agent": feedparser.USER_AGENT}
    
    async with aiohttp.ClientSession(headers=headers) as session:
        async def _resolve_one(item):
            filename, idx, url = item
            async with sem:
                canonical = await _resolve_gnews_redirect(session, url, timeout_sec)
                return (filename, idx, canonical)
        
        # 分批处理，每100个打印进度
        batch_size = 100
        resolved = 0
        failed = 0
        
        for i in range(0, total_gnews, batch_size):
            batch = resolve_items[i:i+batch_size]
            batch_end = min(i + batch_size, total_gnews)
            
            tasks = [_resolve_one(item) for item in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    failed += 1
                    continue
                filename, idx, canonical = result
                if canonical:
                    articles_by_file[filename][idx]["canonical_url"] = canonical
                    resolved += 1
                else:
                    failed += 1
            
            elapsed = _time.monotonic() - start
            print(f"  [BATCH_RESOLVE] Progress: {batch_end}/{total_gnews} "
                  f"({resolved} resolved, {failed} failed, {elapsed:.1f}s elapsed)")
    
    elapsed = _time.monotonic() - start
    print(f"  [BATCH_RESOLVE] Done: {resolved}/{total_gnews} resolved ({failed} failed, {elapsed:.1f}s)")
    return resolved, total_gnews, elapsed


def _parse_feed_text(text):
    return feedparser.parse(text)


async def fetch_one(session, url, tag, max_items=30, max_retries=1):
    """
    异步抓取单个RSS源。
    返回 (items_list, is_rate_limited)。
    P3: Google News 429/503 指数退避重试 (60+random(0,30)s后重试1次)
    """
    import random
    is_sensitive = _is_sensitive_url(url)

    for attempt in range(max_retries + 1):
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10, connect=5)) as resp:
                if resp.status in (429, 503):
                    if is_sensitive and attempt < max_retries:
                        # P3: 指数退避 — 60+random(0,30)s后重试1次
                        backoff = 60 + random.uniform(0, 30)
                        print(f"  [RATE_LIMITED] {tag}: HTTP {resp.status}, retrying in {backoff:.0f}s...")
                        await asyncio.sleep(backoff)
                        continue
                    print(f"  [RATE_LIMITED] {tag}: HTTP {resp.status}, no more retries")
                    return [], True

                if resp.status != 200:
                    if attempt < max_retries:
                        await asyncio.sleep(1)
                        continue
                    return [], False

                text = await resp.text()

                loop = asyncio.get_event_loop()
                feed = await loop.run_in_executor(_parse_executor, _parse_feed_text, text)

                if is_sensitive and feed.bozo and len(feed.entries) == 0:
                    print(f"  [RATE_LIMITED] {tag}: bozo parse, likely rate limited")
                    return [], True

                items = []
                for entry in feed.entries[:max_items]:
                    title = entry.get("title", "")
                    link = entry.get("link", "")
                    published = entry.get("published", entry.get("updated", ""))
                    summary = entry.get("summary", entry.get("description", ""))
                    summary = re.sub(r'<[^>]+>', '', summary).strip()
                    if len(summary) > 500:
                        summary = summary[:500] + "..."
                    item = {
                        "title": title,
                        "link": link,
                        "published": published,
                        "summary": summary,
                        "source": tag,
                    }
                    # GNews跟踪URL解析canonical_url（Actions环境可达）
                    if _is_gnews_url(link):
                        canonical = await _resolve_gnews_redirect(session, link)
                        if canonical:
                            item["canonical_url"] = canonical
                    items.append(item)
                return items, False

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            err_str = str(e).lower()
            # P3: 敏感源429/503异常也走退避
            if is_sensitive and ("429" in err_str or "503" in err_str or "rate" in err_str):
                if attempt < max_retries:
                    backoff = 60 + random.uniform(0, 30)
                    print(f"  [RATE_LIMITED] {tag}: {e}, retrying in {backoff:.0f}s...")
                    await asyncio.sleep(backoff)
                    continue
                return [], True
            if is_sensitive and attempt < max_retries:
                await asyncio.sleep(1)
                continue
            if attempt < max_retries:
                await asyncio.sleep(1)
                continue
            return [], False
        except Exception as e:
            if attempt < max_retries:
                await asyncio.sleep(1)
                continue
            print(f"  [FAIL] {tag}: {e}")
            return [], False

    return [], False


async def fetch_feed_concurrent_async(feeds, max_items=30):
    """
    异步并发抓取多个RSS源。
    使用双信号量：全局Semaphore(50) + Google News Semaphore(5)。
    """
    global_sem = asyncio.Semaphore(SEMAPHORE_GLOBAL)
    gnews_sem = asyncio.Semaphore(SEMAPHORE_GNEWS)

    all_items = []
    fail_count = 0
    rate_limited_count = 0

    headers = {"User-Agent": feedparser.USER_AGENT}
    async with aiohttp.ClientSession(headers=headers) as session:

        async def _fetch_wrapped(feed_def):
            url = feed_def["url"]
            tag = feed_def["tag"]
            sem = gnews_sem if _is_sensitive_url(url) else global_sem
            async with sem:
                return await fetch_one(session, url, tag, max_items)

        tasks = [_fetch_wrapped(fd) for fd in feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            tag = feeds[i]["tag"]
            if isinstance(result, Exception):
                fail_count += 1
                print(f"    [EXCEPTION] {tag}: {result}")
                continue

            items, is_rate_limited = result
            if is_rate_limited:
                rate_limited_count += 1
            if not items:
                if not is_rate_limited:
                    fail_count += 1
            else:
                print(f"    Got {len(items)} items from {tag}")
                for item in items:
                    item["_feed_tag"] = tag
                all_items.extend(items)

    return all_items, fail_count, rate_limited_count


# 同步包装（兼容）
def fetch_feed_concurrent(feeds, max_workers=15, max_items=30):
    return asyncio.run(fetch_feed_concurrent_async(feeds, max_items))


# ============================================================
# 增量状态管理 (P4-7)
# ============================================================

def load_last_state(state_dir):
    """加载上一轮增量状态文件。返回 {module_name: {link_hash: "new"|"continuing"}} 字典"""
    path = os.path.join(state_dir, "last_state.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_last_state(state_dir, state):
    """保存增量状态文件"""
    path = os.path.join(state_dir, "last_state.json")
    atomic_write_json(state, path)


def tag_incremental(items, prev_hashes):
    """
    对文章列表标记增量状态。
    items: 当前轮文章列表（每项需有 "link" 字段）
    prev_hashes: 上一轮该模块的 link_hash 集合 set(str)
    返回: items（原地修改，添加 _incremental="new"|"continuing"），新hash集合
    """
    new_hashes = set()
    for item in items:
        h = link_hash(item["link"])
        new_hashes.add(h)
        if h in prev_hashes:
            item["_incremental"] = "continuing"
        else:
            item["_incremental"] = "new"
    return items, new_hashes


# ============================================================
# 关键词评分
# ============================================================

def calc_priority(title, summary, core_kw, important_kw, aux_kw, source_coefficient=1.0, exclude_kw=None):
    """计算文章优先级分数。source_coefficient: 源权威度系数(P4-2)，exclude_kw: 排除词(P4-4)，命中扣3分"""
    # P4-3: 标题/摘要拆分权重 — 标题命中 ×1.5
    title_lower = title.lower()
    text_lower = (title + " " + summary).lower()

    score = 0
    for kw in core_kw:
        kw_l = kw.lower()
        if kw_l in title_lower:
            score += 5 * 1.5  # 标题命中 ×1.5
        elif kw_l in text_lower:
            score += 5
    for kw in important_kw:
        kw_l = kw.lower()
        if kw_l in title_lower:
            score += 3 * 1.5
        elif kw_l in text_lower:
            score += 3
    for kw in aux_kw:
        kw_l = kw.lower()
        if kw_l in title_lower:
            score += 1 * 1.5
        elif kw_l in text_lower:
            score += 1

    # P4-4: 排除词扣分（每个命中扣除3分，最低0）
    if exclude_kw:
        for kw in exclude_kw:
            if kw.lower() in title_lower:
                score -= 3
            elif kw.lower() in text_lower:
                score -= 2
        score = max(score, 0)

    # P4-2: 乘以源权威度系数
    score = round(score * source_coefficient, 2)
    return score


def detect_signal_keywords(title, summary, signal_kw):
    if not signal_kw:
        return []
    text = (title + " " + summary).lower()
    hits = []
    for kw in signal_kw:
        if kw.lower() in text:
            hits.append(kw)
    return hits


# ============================================================
# 两层去重
# ============================================================

def link_hash(link):
    normalized = link.strip()
    if normalized.startswith("http://"):
        normalized = "https://" + normalized[7:]
    for param in ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"]:
        normalized = re.sub(r'[?&]' + param + r'=[^&]*', '', normalized)
    normalized = normalized.rstrip('?&')
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


# title_similarity 已在文件顶部定义（RapidFuzz优先，fallback difflib）

# 常见快讯前缀，分桶前需清洗
_BREAKING_PREFIXES = re.compile(
    r'^(breaking|just in|update|exclusive|alert|urgent|flash|developing|'
    r'morning brief|evening brief|news flash|live|watch|report)[\s:：\-–—]*',
    re.IGNORECASE
)

# 停用词（英文常见虚词，不作为实体特征）
_STOP_WORDS = frozenset(
    "the a an is are was were be been being have has had do does did "
    "will would shall should may might can could of in on at to for "
    "with by from and or but not no nor so yet it its this that these "
    "those he she they we you i me him her us them my your his their "
    "our its as if then than too very also just more most how what "
    "when where which who whom whose new says said after over into".split()
)


def _bucket_key(title):
    """
    改进分桶策略：清洗标题+提取核心实体词取代"前3字符"。
    解决：冠词/快讯前缀/特殊字符导致相似标题被分到不同桶的假阴性问题。
    步骤：1)去快讯前缀 2)小写+去标点 3)去停用词 4)取最长2个词组合为桶key
    """
    t = _BREAKING_PREFIXES.sub('', title)
    t = re.sub(r'[^\w\s]', '', t.lower()).strip()
    words = [w for w in t.split() if w not in _STOP_WORDS and len(w) > 1]
    if not words:
        # 回退：去标点后前5字符
        return re.sub(r'[^\w\s]', '', title.lower()).strip()[:5] or "_"
    # 按词长降序排列，取最长2个词组合 → 语义特征稳定
    words.sort(key=len, reverse=True)
    key_parts = sorted(words[:2])  # sorted保证顺序无关
    return "+".join(key_parts)


def parse_published_time(pub_str):
    if not pub_str:
        return None
    for fmt in [
        "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ",
        "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT", "%Y-%m-%d",
    ]:
        try:
            return datetime.strptime(pub_str.strip(), fmt)
        except (ValueError, TypeError):
            continue
    return None


def dedup_link_level(items):
    seen = {}
    for item in items:
        h = link_hash(item["link"])
        if h in seen:
            if item["priority"] > seen[h]["priority"]:
                seen[h] = item
        else:
            seen[h] = item
    return list(seen.values())


def dedup_title_level(items, threshold=0.85, hours=24):
    """v4.4: 核心实体词分桶 + RapidFuzz，解决前3字符分桶的假阴性问题"""
    if len(items) < 2:
        return items
    items_sorted = sorted(items, key=lambda x: x["priority"], reverse=True)

    buckets = {}
    for idx, item in enumerate(items_sorted):
        key = _bucket_key(item["title"])
        buckets.setdefault(key, []).append(idx)

    removed = set()
    for bucket_indices in buckets.values():
        for i_pos in range(len(bucket_indices)):
            i = bucket_indices[i_pos]
            if i in removed:
                continue
            for j_pos in range(i_pos + 1, len(bucket_indices)):
                j = bucket_indices[j_pos]
                if j in removed:
                    continue
                sim = title_similarity(items_sorted[i]["title"], items_sorted[j]["title"])
                if sim >= threshold:
                    t1 = parse_published_time(items_sorted[i]["published"])
                    t2 = parse_published_time(items_sorted[j]["published"])
                    if t1 and t2 and abs((t1 - t2).total_seconds()) < hours * 3600:
                        removed.add(j)

    return [items_sorted[i] for i in range(len(items_sorted)) if i not in removed]


# ============================================================
# 模块运行
# ============================================================

async def run_module_async(config, prev_hashes=None):
    """异步运行单个模块（subprocess隔离模式下prev_hashes不使用，增量标记由fetch_all.py在全局层面处理）"""
    name = config["name"]
    print(f"\n{'='*60}")
    print(f"MODULE: {name}")
    print(f"{'='*60}")

    core_kw = config.get("core_keywords", [])
    important_kw = config.get("important_keywords", [])
    aux_kw = config.get("aux_keywords", [])
    signal_kw = config.get("signal_keywords", [])
    exclude_kw = config.get("exclude_keywords", [])

    # P4-2: 加载源权威度系数表
    config_dir = config.get("config_dir", "")
    if not config_dir:
        # 从common.py所在目录推断: scripts/config/
        config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    authority_map = load_source_authority(config_dir)

    all_items = []
    stats = {}
    total_fail = 0
    total_rate_limited = 0

    for category, feeds in config["feeds"].items():
        print(f"  Category: {category} ({len(feeds)} feeds, async fetch...)")
        items, fail_count, rate_limited_count = await fetch_feed_concurrent_async(feeds)

        for item in items:
            source_coeff = get_source_coefficient(item.get("source", ""), authority_map)
            item["priority"] = calc_priority(item["title"], item["summary"], core_kw, important_kw, aux_kw, source_coeff, exclude_kw)
            sig_hits = detect_signal_keywords(item["title"], item["summary"], signal_kw)
            if sig_hits:
                item["signal_keywords"] = sig_hits
            item["category"] = category
            item.pop("_feed_tag", None)

        all_items.extend(items)
        stats[category] = {"count": len(items), "feeds": len(feeds)}
        total_fail += fail_count
        total_rate_limited += rate_limited_count

    unique_items = dedup_link_level(all_items)
    print(f"  After link dedup: {len(all_items)} → {len(unique_items)}")

    unique_items = dedup_title_level(unique_items, threshold=0.85, hours=24)
    print(f"  After title dedup: → {len(unique_items)}")

    # 时效过滤：保留近max_age_days天的文章，published解析失败的保守保留
    max_age_days = config.get("max_age_days", 30)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    before_filter = len(unique_items)
    filtered_items = []
    for item in unique_items:
        pt = parse_published_time(item.get("published", ""))
        if pt is None:
            filtered_items.append(item)  # 无法解析时间的保守保留
        else:
            # 统一转UTC比较
            if pt.tzinfo is None:
                pt = pt.replace(tzinfo=timezone.utc)
            if pt >= cutoff:
                filtered_items.append(item)
    unique_items = filtered_items
    removed_by_age = before_filter - len(unique_items)
    if removed_by_age > 0:
        print(f"  After age filter ({max_age_days}d): {before_filter} → {len(unique_items)} (-{removed_by_age})")

    # P4-7: 增量标记
    if prev_hashes is None:
        prev_hashes = set()
    unique_items, new_hashes = tag_incremental(unique_items, prev_hashes)
    new_count = sum(1 for i in unique_items if i.get("_incremental") == "new")
    cont_count = sum(1 for i in unique_items if i.get("_incremental") == "continuing")
    print(f"  Incremental: {new_count} new, {cont_count} continuing")

    for item in unique_items:
        if item["priority"] >= 10:
            item["relevance"] = "high"
        elif item["priority"] >= 3:
            item["relevance"] = "medium"
        else:
            item["relevance"] = "low"

    unique_items.sort(key=lambda x: (x["priority"], x["published"]), reverse=True)

    max_articles = config.get("max_articles", 500)
    unique_items = unique_items[:max_articles]

    now = datetime.now(timezone.utc)
    signal_stats = {}
    for item in unique_items:
        for sk in item.get("signal_keywords", []):
            signal_stats[sk] = signal_stats.get(sk, 0) + 1

    output = {
        "version": "4.0",
        "module": name,
        "updated": now.isoformat(),
        "fetch_date_utc": now.strftime("%Y-%m-%d"),
        "total": len(unique_items),
        "high_priority": len([i for i in unique_items if i["relevance"] == "high"]),
        "medium_priority": len([i for i in unique_items if i["relevance"] == "medium"]),
        "signal_alerts": signal_stats,
        "stats_by_category": stats,
        "fail_feeds": total_fail,
        "rate_limited_feeds": total_rate_limited,
        "articles": unique_items,
    }

    output_file = config["output_file"]
    atomic_write_json(output, output_file)

    print(f"\nMODULE DONE: {name}")
    print(f"  Total: {output['total']}, High: {output['high_priority']}, Medium: {output['medium_priority']}")
    print(f"  Failed feeds: {total_fail}")
    if total_rate_limited:
        print(f"  Rate limited feeds: {total_rate_limited}")
    print(f"  Output: {output_file}")

    return output, new_hashes


def run_module(config, prev_hashes=None):
    """同步包装"""
    return asyncio.run(run_module_async(config, prev_hashes))


def atomic_write_json(data, filepath):
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if os.path.exists(filepath):
        os.remove(filepath)
    os.rename(tmp_path, filepath)


def gnews_url(query, hl="en-US", gl="US", ceid="US:en"):
    import urllib.parse
    q = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"
