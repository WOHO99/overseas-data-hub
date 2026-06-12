#!/usr/bin/env python3
"""
fetch_full_text.py v1.1 — 正文自动抓取（本地运行，trafilatura驱动）

v1.0: 初始版本
v1.1: 优先使用canonical_url（Actions端解析的GNews重定向目标URL）

优先级分层：
  P0: high+signal 且属于中企/新模块 → 立即抓取
  P1: high → 排队抓取
  P2: medium/low → 跳过

输入：data/YYYY-MM-DD/*.json（模块JSON，含canonical_url字段）
输出：
  - data/YYYY-MM-DD/full_text/{hash}.txt（正文临时存储）
  - data/YYYY-MM-DD/full_text_map.json（link → {full_text_path, canonical_url, priority}）
  - data/YYYY-MM-DD/fetch_failed.json（抓取失败列表）

用法：
  python fetch_full_text.py                    # 自动检测最新日期目录
  python fetch_full_text.py 2026-06-12         # 指定日期
  python fetch_full_text.py --p0-only          # 只抓P0
  python fetch_full_text.py --retry-failed     # 重试上次失败的文章
"""

import json
import os
import sys
import time
import hashlib
import argparse
import re
from datetime import datetime, timezone

# trafilatura必须可用
try:
    import trafilatura
except ImportError:
    print("ERROR: trafilatura not installed. Run: pip install trafilatura")
    sys.exit(2)

# ── 配置 ────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_ROOT = os.path.join(SCRIPT_DIR, "data")

# 中企相关模块名（P0判定条件之一）
CHINESE_FIRMS_MODULES = {"chinese_firms_overseas"}

# 新增4模块（P0判定：属于新模块且high+signal也算P0）
NEW_FOCUS_MODULES = {
    "cross_border_ecommerce",
    "trade_import_export",
    "global_risk",
    "chinese_firms_overseas",
}

# 抓取配置
P0_DELAY = 1.0           # P0篇间延迟（秒）
P1_DELAY = 2.0           # P1篇间延迟
MIN_TEXT_LENGTH = 200     # 正文最短有效长度（字符）

# GNews跟踪URL特征
GNEWS_URL_PATTERN = re.compile(r"https?://news\.google\.com/", re.IGNORECASE)


# ── 优先级分类 ──────────────────────────────────────────────────

def classify_priority(article, module_name=None):
    """
    判定文章抓取优先级: P0/P1/P2
    P0: high+signal+(中企/新模块)
    P1: high
    P2: medium/low → 不抓
    """
    relevance = article.get("relevance", "")
    has_signal = bool(article.get("signal_keywords"))
    is_chinese_firm = module_name in CHINESE_FIRMS_MODULES
    is_new_focus = module_name in NEW_FOCUS_MODULES

    if relevance == "high":
        if has_signal and (is_chinese_firm or is_new_focus):
            return "P0"
        elif has_signal or is_chinese_firm or is_new_focus:
            return "P0"
        else:
            return "P1"
    elif relevance == "medium" and is_chinese_firm and has_signal:
        return "P1"
    else:
        return "P2"


# ── URL策略 ─────────────────────────────────────────────────────

def resolve_fetch_url(article):
    """
    确定用于抓取正文的URL。
    优先级：canonical_url > link（跳过GNews跟踪URL）
    返回: (fetch_url, is_gnews_only)
    is_gnews_only=True 表示只有GNews链接，本地可能无法抓取
    """
    canonical = article.get("canonical_url", "")
    link = article.get("link", "")

    if canonical:
        return canonical, False
    if link and not GNEWS_URL_PATTERN.match(link):
        return link, False
    if link:
        # 只有GNews URL，无canonical（Actions未解析或解析失败）
        return link, True
    return "", True


# ── 正文抓取 ────────────────────────────────────────────────────

def fetch_text(url):
    """
    用trafilatura抓取正文。
    返回: (text, status)
    """
    try:
        # trafilatura 2.x 的 fetch_url 不接受 timeout 参数
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None, "download_failed"

        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            favor_precision=True,   # 宁可少抓也不抓噪音
            include_formatting=False,
        )

        if not text or len(text.strip()) < MIN_TEXT_LENGTH:
            return None, "empty_or_short"

        return text.strip(), "success"

    except Exception as e:
        err_str = str(e).lower()
        if "timeout" in err_str or "timed out" in err_str:
            return None, "timeout"
        elif "403" in err_str or "forbidden" in err_str:
            return None, "forbidden"
        elif "404" in err_str or "not found" in err_str:
            return None, "not_found"
        elif "429" in err_str or "rate" in err_str:
            return None, "rate_limited"
        else:
            return None, f"error:{str(e)[:80]}"


def article_hash(link):
    """生成文章唯一标识"""
    normalized = link.strip()
    if normalized.startswith("http://"):
        normalized = "https://" + normalized[7:]
    for param in ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"]:
        normalized = re.sub(r'[?&]' + param + r'=[^&]*', '', normalized)
    normalized = normalized.rstrip('?&')
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


# ── 数据加载 ────────────────────────────────────────────────────

def detect_date_dir(data_root):
    """自动检测最新的日期子目录"""
    date_dirs = []
    for entry in os.listdir(data_root):
        if re.match(r"^\d{4}-\d{2}-\d{2}$", entry):
            full_path = os.path.join(data_root, entry)
            if os.path.isdir(full_path):
                date_dirs.append((entry, full_path))
    if not date_dirs:
        return None, None
    date_dirs.sort(reverse=True)
    return date_dirs[0]


SKIP_JSONS = frozenset({
    "index.json", "signal_summary.json", "signal_baseline.json",
    "source_fingerprint.json", "sources_dead.json", "last_state.json",
    "full_text_map.json", "fetch_failed.json", "_summary.json",
})


def load_module_jsons(date_dir):
    """加载指定日期目录下所有模块JSON"""
    articles_by_module = {}
    for fname in os.listdir(date_dir):
        if not fname.endswith(".json") or fname in SKIP_JSONS:
            continue
        fpath = os.path.join(date_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        module_name = fname.replace(".json", "")
        articles = data.get("articles", [])
        if articles:
            articles_by_module[module_name] = articles
    return articles_by_module


# ── 主流程 ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="fetch_full_text.py v1.1 — 正文自动抓取")
    parser.add_argument("date", nargs="?", help="指定日期 YYYY-MM-DD，默认自动检测最新")
    parser.add_argument("--p0-only", action="store_true", help="只抓P0优先级文章")
    parser.add_argument("--retry-failed", action="store_true", help="重试上次失败的文章")
    parser.add_argument("--data-root", default=DEFAULT_DATA_ROOT, help="数据根目录")
    args = parser.parse_args()

    # 确定日期目录
    if args.date:
        date_str = args.date
        date_dir = os.path.join(args.data_root, date_str)
        if not os.path.isdir(date_dir):
            print(f"ERROR: 目录不存在: {date_dir}")
            sys.exit(1)
    else:
        result = detect_date_dir(args.data_root)
        if not result[0]:
            print(f"ERROR: {args.data_root} 下无日期子目录")
            sys.exit(1)
        date_str, date_dir = result
        print(f"自动检测最新日期: {date_str}")

    print(f"数据目录: {date_dir}")

    # 加载模块JSON
    articles_by_module = load_module_jsons(date_dir)
    total_modules = len(articles_by_module)
    total_articles = sum(len(arts) for arts in articles_by_module.values())
    print(f"已加载 {total_modules} 个模块，共 {total_articles} 篇文章")

    # 统计canonical_url覆盖
    has_canonical = 0
    gnews_only = 0
    for mod_name, articles in articles_by_module.items():
        for art in articles:
            if art.get("canonical_url"):
                has_canonical += 1
            elif GNEWS_URL_PATTERN.match(art.get("link", "")):
                gnews_only += 1
    print(f"canonical_url覆盖: {has_canonical}/{total_articles} ({has_canonical*100//max(total_articles,1)}%), GNews-only(待解析): {gnews_only}")

    if total_articles == 0:
        print("无文章可处理，退出")
        sys.exit(0)

    # 创建正文存储目录
    full_text_dir = os.path.join(date_dir, "full_text")
    os.makedirs(full_text_dir, exist_ok=True)

    # 加载已有映射（增量模式）
    map_path = os.path.join(date_dir, "full_text_map.json")
    full_text_map = {}
    if os.path.exists(map_path):
        try:
            with open(map_path, "r", encoding="utf-8") as f:
                full_text_map = json.load(f)
            print(f"已有正文映射: {len(full_text_map)} 篇")
        except (json.JSONDecodeError, OSError):
            full_text_map = {}

    # 加载失败列表
    failed_path = os.path.join(date_dir, "fetch_failed.json")
    prev_failed = {}
    if os.path.exists(failed_path):
        try:
            with open(failed_path, "r", encoding="utf-8") as f:
                prev_failed = json.load(f)
        except (json.JSONDecodeError, OSError):
            prev_failed = {}

    # 分类
    p0_articles = []
    p1_articles = []
    p2_count = 0
    skip_fetched = 0
    skip_gnews_only = 0

    fetched_links = set(full_text_map.keys())

    for mod_name, articles in articles_by_module.items():
        for art in articles:
            link = art.get("link", "")
            # 跳过已抓取
            if link in fetched_links:
                skip_fetched += 1
                continue

            priority = classify_priority(art, mod_name)
            _, is_gnews = resolve_fetch_url(art)

            # 只有GNews URL且无canonical → 本地无法抓取，直接跳过
            if is_gnews:
                skip_gnews_only += 1
                if priority != "P2":
                    # 高优先级但无法抓取，记入failed供后续处理
                    prev_failed[link] = {
                        "module": mod_name,
                        "title": art.get("title", ""),
                        "status": "gnews_no_canonical",
                        "priority": priority,
                    }
                continue

            art["_module"] = mod_name
            art["_fetch_priority"] = priority
            if priority == "P0":
                p0_articles.append(art)
            elif priority == "P1":
                p1_articles.append(art)
            else:
                p2_count += 1

    print(f"\n分类结果: P0={len(p0_articles)}, P1={len(p1_articles)}, P2={p2_count}(跳过)")
    print(f"  已抓取跳过: {skip_fetched}, GNews-only跳过: {skip_gnews_only}")

    # 如果 --retry-failed，只重试有canonical_url的失败文章
    if args.retry_failed and prev_failed:
        retry_arts = []
        retry_skip = 0
        for link, info in list(prev_failed.items()):
            if info.get("status") == "gnews_no_canonical":
                retry_skip += 1
                continue
            retry_arts.append({
                "link": link,
                "_module": info.get("module", "unknown"),
                "_fetch_priority": "P0",
                "title": info.get("title", ""),
            })
        p0_articles.extend(retry_arts)
        print(f"重试: {len(retry_arts)} 篇加入P0 (GNews-only跳过: {retry_skip})")

    # 开始抓取
    fetch_queue = p0_articles.copy()
    if not args.p0_only:
        fetch_queue.extend(p1_articles)

    if not fetch_queue:
        print("无文章需要抓取")
        # 即使不抓取也保存failed列表
        with open(failed_path, "w", encoding="utf-8") as f:
            json.dump(prev_failed, f, ensure_ascii=False, indent=2)
        sys.exit(0)

    print(f"\n开始抓取: {len(fetch_queue)} 篇 (P0={len(p0_articles)}, P1={len(p1_articles) if not args.p0_only else 0})")

    success_count = 0
    fail_count = 0
    new_failed = dict(prev_failed)

    for i, art in enumerate(fetch_queue, 1):
        link = art.get("link", "")
        title = art.get("title", "")[:60]
        priority = art.get("_fetch_priority", "P1")
        module = art.get("_module", "unknown")

        if not link:
            continue

        # 确定抓取URL
        fetch_url, is_gnews = resolve_fetch_url(art)
        if not fetch_url or is_gnews:
            continue

        # 延迟
        delay = P0_DELAY if priority == "P0" else P1_DELAY
        if i > 1:
            time.sleep(delay)

        print(f"  [{i}/{len(fetch_queue)}] {priority} [{module}] {title}...", end=" ", flush=True)

        text, status = fetch_text(fetch_url)

        if text and status == "success":
            # 保存正文
            h = article_hash(fetch_url)
            text_path = os.path.join(full_text_dir, f"{h}.txt")
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(text)

            # 更新映射
            rel_path = os.path.relpath(text_path, date_dir).replace("\\", "/")
            full_text_map[link] = {
                "full_text_path": rel_path,
                "canonical_url": fetch_url,
                "priority": priority,
                "module": module,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }

            # 从失败列表中移除
            if link in new_failed:
                del new_failed[link]

            success_count += 1
            print(f"OK ({len(text)} chars)")
        else:
            # 记录失败
            new_failed[link] = {
                "module": module,
                "title": art.get("title", ""),
                "status": status,
                "fetch_url": fetch_url[:200],
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "retry_count": new_failed.get(link, {}).get("retry_count", 0) + 1,
            }
            fail_count += 1
            print(f"FAIL ({status})")

    # 保存映射
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(full_text_map, f, ensure_ascii=False, indent=2)

    # 保存失败列表
    with open(failed_path, "w", encoding="utf-8") as f:
        json.dump(new_failed, f, ensure_ascii=False, indent=2)

    # 汇总
    print(f"\n{'='*60}")
    print(f"抓取完成")
    print(f"  成功: {success_count}")
    print(f"  失败: {fail_count}")
    print(f"  跳过(P2): {p2_count}")
    print(f"  已抓取跳过: {skip_fetched}")
    print(f"  GNews-only跳过: {skip_gnews_only}")
    print(f"  累计正文: {len(full_text_map)} 篇")
    print(f"  待重试: {len(new_failed)} 篇")
    print(f"  映射文件: {map_path}")
    print(f"  失败文件: {failed_path}")

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
