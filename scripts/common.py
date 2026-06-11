#!/usr/bin/env python3
"""
common.py v3.5 — 全球商业情报仪表盘共享工具库
v3.1: 并发抓取、双层去重、原子写入、关键词外置
v3.3: 信号性词汇检测(signal keywords)、模块版本号升级
v3.3.1: 修复feedparser无HTTP超时导致fetch挂起(socket.setdefaulttimeout)
v3.4: feed并发15+socket超时15s+future超时20s(实测仍不够激进)
v3.5: socket 10s + User-Agent + Google News限速跳过+rate_limited计数
"""

import feedparser
import json
import re
import hashlib
import os
import socket
import difflib
import yaml
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# 全局Socket超时：10s（v3.5: 从15s进一步收紧，快速淘汰无响应源）
socket.setdefaulttimeout(10)

# User-Agent: 标识身份，避免被部分站点拒绝
feedparser.USER_AGENT = "Mozilla/5.0 (compatible; OverseasDataHub/1.0; +https://github.com/WOHO99/overseas-data-hub)"

# 已知限速域名
RATE_LIMITED_DOMAINS = ["news.google.com"]


# ============================================================
# 配置加载
# ============================================================

def load_keywords(config_dir, module_name):
    """从keywords.yaml加载指定模块的关键词"""
    kw_path = os.path.join(config_dir, "keywords.yaml")
    if not os.path.exists(kw_path):
        print(f"  [WARN] keywords.yaml not found at {kw_path}, using empty keywords")
        return [], [], [], []

    with open(kw_path, "r", encoding="utf-8") as f:
        all_kw = yaml.safe_load(f)

    if module_name not in all_kw:
        print(f"  [WARN] Module '{module_name}' not in keywords.yaml, using empty keywords")
        return [], [], [], []

    mod_kw = all_kw[module_name]
    return (
        mod_kw.get("core", []),
        mod_kw.get("important", []),
        mod_kw.get("aux", []),
        mod_kw.get("signal", []),
    )


# ============================================================
# RSS抓取（并发）
# ============================================================

def fetch_feed(url, tag, max_items=30):
    """
    抓取单个RSS源，返回 (items_list, is_rate_limited)。
    对已知限速域名，失败后快速跳过不阻塞。
    """
    items = []
    is_rate_limited = False

    # 检查是否为限速域名
    is_sensitive = any(domain in url for domain in RATE_LIMITED_DOMAINS)

    try:
        feed = feedparser.parse(url)

        # 检查限速标志
        if hasattr(feed, 'status') and feed.status in (429, 503):
            is_rate_limited = True
            print(f"  [RATE_LIMITED] {tag}: HTTP {feed.status}")
            return items, is_rate_limited

        # feedparser没有status属性时，检查bozo（解析异常可能是限速页）
        if is_sensitive and feed.bozo and len(feed.entries) == 0:
            is_rate_limited = True
            print(f"  [RATE_LIMITED] {tag}: bozo parse, likely rate limited")
            return items, is_rate_limited

        for entry in feed.entries[:max_items]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            published = entry.get("published", entry.get("updated", ""))
            summary = entry.get("summary", entry.get("description", ""))
            summary = re.sub(r'<[^>]+>', '', summary).strip()
            if len(summary) > 500:
                summary = summary[:500] + "..."
            items.append({
                "title": title,
                "link": link,
                "published": published,
                "summary": summary,
                "source": tag,
            })
    except socket.timeout:
        if is_sensitive:
            is_rate_limited = True
            print(f"  [RATE_LIMITED] {tag}: socket timeout (sensitive source)")
        else:
            print(f"  [FAIL] {tag}: socket timeout")
    except Exception as e:
        err_str = str(e).lower()
        if is_sensitive and ("429" in err_str or "503" in err_str or "forbidden" in err_str):
            is_rate_limited = True
            print(f"  [RATE_LIMITED] {tag}: {e}")
        else:
            print(f"  [FAIL] {tag}: {e}")

    return items, is_rate_limited


def fetch_feed_concurrent(feeds, max_workers=15, max_items=30):
    """
    并发抓取多个RSS源。
    返回 (all_items, fail_count, rate_limited_count)。
    """
    all_items = []
    fail_count = 0
    rate_limited_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_tag = {}
        for feed_def in feeds:
            url = feed_def["url"]
            tag = feed_def["tag"]
            future = executor.submit(fetch_feed, url, tag, max_items)
            future_to_tag[future] = tag

        for future in as_completed(future_to_tag):
            tag = future_to_tag[future]
            try:
                items, is_rate_limited = future.result(timeout=15)
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
            except Exception as e:
                fail_count += 1
                print(f"    [TIMEOUT/ERROR] {tag}: {e}")

    return all_items, fail_count, rate_limited_count


# ============================================================
# 关键词评分
# ============================================================

def calc_priority(title, summary, core_kw, important_kw, aux_kw):
    """3级关键词评分"""
    text = (title + " " + summary).lower()
    score = 0
    for kw in core_kw:
        if kw.lower() in text:
            score += 5
    for kw in important_kw:
        if kw.lower() in text:
            score += 3
    for kw in aux_kw:
        if kw.lower() in text:
            score += 1
    return score


def detect_signal_keywords(title, summary, signal_kw):
    """v3.3: 信号性词汇检测"""
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
    """URL标准化+哈希"""
    normalized = link.strip()
    if normalized.startswith("http://"):
        normalized = "https://" + normalized[7:]
    for param in ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"]:
        normalized = re.sub(r'[?&]' + param + r'=[^&]*', '', normalized)
    normalized = normalized.rstrip('?&')
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


def title_similarity(t1, t2):
    """标题相似度(0-1)"""
    return difflib.SequenceMatcher(None, t1.lower(), t2.lower()).ratio()


def parse_published_time(pub_str):
    """尝试解析发布时间"""
    if not pub_str:
        return None
    for fmt in [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%d",
    ]:
        try:
            return datetime.strptime(pub_str.strip(), fmt)
        except (ValueError, TypeError):
            continue
    return None


def dedup_link_level(items):
    """第一层：link哈希精确去重"""
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
    """第二层：标题相似度去重"""
    if len(items) < 2:
        return items

    items_sorted = sorted(items, key=lambda x: x["priority"], reverse=True)
    kept = []
    removed = set()

    for i, item in enumerate(items_sorted):
        if i in removed:
            continue
        kept.append(item)
        for j in range(i + 1, len(items_sorted)):
            if j in removed:
                continue
            sim = title_similarity(item["title"], items_sorted[j]["title"])
            if sim >= threshold:
                t1 = parse_published_time(item["published"])
                t2 = parse_published_time(items_sorted[j]["published"])
                if t1 and t2 and abs((t1 - t2).total_seconds()) < hours * 3600:
                    removed.add(j)

    return kept


# ============================================================
# 模块运行
# ============================================================

def run_module(config):
    """
    运行单个模块。
    v3.5: 返回含rate_limited_feeds计数的output。
    """
    name = config["name"]
    print(f"\n{'='*60}")
    print(f"MODULE: {name}")
    print(f"{'='*60}")

    core_kw = config.get("core_keywords", [])
    important_kw = config.get("important_keywords", [])
    aux_kw = config.get("aux_keywords", [])
    signal_kw = config.get("signal_keywords", [])

    all_items = []
    stats = {}
    total_fail = 0
    total_rate_limited = 0

    for category, feeds in config["feeds"].items():
        print(f"  Category: {category} ({len(feeds)} feeds, concurrent fetch...)")
        items, fail_count, rate_limited_count = fetch_feed_concurrent(feeds, max_workers=15)

        for item in items:
            item["priority"] = calc_priority(
                item["title"], item["summary"],
                core_kw, important_kw, aux_kw
            )
            sig_hits = detect_signal_keywords(item["title"], item["summary"], signal_kw)
            if sig_hits:
                item["signal_keywords"] = sig_hits
            item["category"] = category
            item.pop("_feed_tag", None)

        all_items.extend(items)
        stats[category] = {"count": len(items), "feeds": len(feeds)}
        total_fail += fail_count
        total_rate_limited += rate_limited_count

    # 去重
    unique_items = dedup_link_level(all_items)
    print(f"  After link dedup: {len(all_items)} → {len(unique_items)}")

    unique_items = dedup_title_level(unique_items, threshold=0.85, hours=24)
    print(f"  After title dedup: → {len(unique_items)}")

    # 分级
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

    # 写入
    now = datetime.now(timezone.utc)
    signal_stats = {}
    for item in unique_items:
        for sk in item.get("signal_keywords", []):
            signal_stats[sk] = signal_stats.get(sk, 0) + 1

    output = {
        "version": "3.5",
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

    return output


def atomic_write_json(data, filepath):
    """原子写入JSON"""
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if os.path.exists(filepath):
        os.remove(filepath)
    os.rename(tmp_path, filepath)


# ============================================================
# 工具函数
# ============================================================

def gnews_url(query, hl="en-US", gl="US", ceid="US:en"):
    """构造Google News RSS搜索URL"""
    import urllib.parse
    q = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"
