#!/usr/bin/env python3
"""
common.py v3.3.1 — 全球商业情报仪表盘共享工具库
v3.1: 并发抓取、双层去重、原子写入、关键词外置
v3.3: 信号性词汇检测(signal keywords)、模块版本号升级
v3.3.1: 修复feedparser无HTTP超时导致fetch挂起的致命bug(socket.setdefaulttimeout)
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

# 全局Socket超时：防止feedparser.parse()对无响应服务器无限挂起
socket.setdefaulttimeout(30)


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
        mod_kw.get("signal", []),  # v3.3: 信号性词汇
    )


# ============================================================
# RSS抓取（并发）
# ============================================================

def fetch_feed(url, tag, max_items=30):
    """抓取单个RSS源，返回条目列表"""
    items = []
    try:
        feed = feedparser.parse(url)
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
    except Exception as e:
        print(f"  [FAIL] {tag}: {e}")
    return items


def fetch_feed_concurrent(feeds, max_workers=8, max_items=30):
    """并发抓取多个RSS源"""
    all_items = []
    fail_count = 0

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
                items = future.result(timeout=30)  # 单源30秒超时
                if not items:
                    fail_count += 1
                print(f"    Got {len(items)} items from {tag}")
                for item in items:
                    item["_feed_tag"] = tag  # 临时标记来源
                all_items.extend(items)
            except Exception as e:
                fail_count += 1
                print(f"    [TIMEOUT/ERROR] {tag}: {e}")

    return all_items, fail_count


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
    """
    v3.3: 信号性词汇检测。
    返回命中的信号词列表。用于index.json中的信号聚集告警。
    """
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
    # 统一https，去跟踪参数
    normalized = link.strip()
    if normalized.startswith("http://"):
        normalized = "https://" + normalized[7:]
    # 去常见跟踪参数
    for param in ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"]:
        normalized = re.sub(r'[?&]' + param + r'=[^&]*', '', normalized)
    normalized = normalized.rstrip('?&')
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


def title_similarity(t1, t2):
    """标题相似度(0-1)，用difflib.SequenceMatcher"""
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
    """
    第二层：标题相似度去重
    相似度>threshold 且 发布时间差<hours → 视为重复，保留priority最高的
    """
    if len(items) < 2:
        return items

    # 按priority降序排列，高优先级保留
    items_sorted = sorted(items, key=lambda x: x["priority"], reverse=True)
    kept = []
    removed = set()

    for i, item in enumerate(items_sorted):
        if i in removed:
            continue
        kept.append(item)
        # 与后续条目比较
        for j in range(i + 1, len(items_sorted)):
            if j in removed:
                continue
            sim = title_similarity(item["title"], items_sorted[j]["title"])
            if sim >= threshold:
                # 检查时间窗口
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
    运行单个模块。config现在从yaml加载关键词，feeds仍在模块内定义。
    """
    name = config["name"]
    print(f"\n{'='*60}")
    print(f"MODULE: {name}")
    print(f"{'='*60}")

    # 加载关键词（从yaml）
    core_kw = config.get("core_keywords", [])
    important_kw = config.get("important_keywords", [])
    aux_kw = config.get("aux_keywords", [])
    signal_kw = config.get("signal_keywords", [])  # v3.3

    all_items = []
    stats = {}
    total_fail = 0

    for category, feeds in config["feeds"].items():
        print(f"  Category: {category} ({len(feeds)} feeds, concurrent fetch...)")
        items, fail_count = fetch_feed_concurrent(feeds, max_workers=8)

        # 计算优先级
        for item in items:
            item["priority"] = calc_priority(
                item["title"], item["summary"],
                core_kw, important_kw, aux_kw
            )
            # v3.3: 信号性词汇检测
            sig_hits = detect_signal_keywords(item["title"], item["summary"], signal_kw)
            if sig_hits:
                item["signal_keywords"] = sig_hits
            item["category"] = category
            # 清理临时字段
            item.pop("_feed_tag", None)

        all_items.extend(items)
        stats[category] = {"count": len(items), "feeds": len(feeds)}
        total_fail += fail_count

    # 第一层去重：link哈希
    unique_items = dedup_link_level(all_items)
    print(f"  After link dedup: {len(all_items)} → {len(unique_items)}")

    # 第二层去重：标题相似度
    unique_items = dedup_title_level(unique_items, threshold=0.85, hours=24)
    print(f"  After title dedup: → {len(unique_items)}")

    # 分级标记
    for item in unique_items:
        if item["priority"] >= 10:
            item["relevance"] = "high"
        elif item["priority"] >= 3:
            item["relevance"] = "medium"
        else:
            item["relevance"] = "low"

    # 排序
    unique_items.sort(key=lambda x: (x["priority"], x["published"]), reverse=True)

    # 截断
    max_articles = config.get("max_articles", 500)
    unique_items = unique_items[:max_articles]

    # 原子写入JSON
    now = datetime.now(timezone.utc)
    # v3.3: 信号性词汇统计
    signal_stats = {}
    all_signals = []
    for item in unique_items:
        for sk in item.get("signal_keywords", []):
            signal_stats[sk] = signal_stats.get(sk, 0) + 1
            all_signals.append({"keyword": sk, "title": item["title"], "link": item["link"]})

    output = {
        "version": "3.3",
        "module": name,
        "updated": now.isoformat(),
        "fetch_date_utc": now.strftime("%Y-%m-%d"),
        "total": len(unique_items),
        "high_priority": len([i for i in unique_items if i["relevance"] == "high"]),
        "medium_priority": len([i for i in unique_items if i["relevance"] == "medium"]),
        "signal_alerts": signal_stats,
        "stats_by_category": stats,
        "fail_feeds": total_fail,
        "articles": unique_items,
    }

    output_file = config["output_file"]
    atomic_write_json(output, output_file)

    print(f"\nMODULE DONE: {name}")
    print(f"  Total: {output['total']}, High: {output['high_priority']}, Medium: {output['medium_priority']}")
    print(f"  Failed feeds: {total_fail}")
    print(f"  Output: {output_file}")

    return output


def atomic_write_json(data, filepath):
    """原子写入JSON：先写.tmp，再rename覆盖"""
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # Windows需先删目标文件
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
