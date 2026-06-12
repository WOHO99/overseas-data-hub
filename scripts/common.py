#!/usr/bin/env python3
"""
common.py v4.8 — 全球商业情报仪表盘共享工具库 (asyncio+aiohttp + RapidFuzz版)
v3.5: 顺序版止血，socket 10s + User-Agent + rate_limited
v4.0: asyncio+aiohttp全量异步重构，预期3-5分钟完成376源抓取
v4.2: title_similarity用RapidFuzz(206x faster)替代difflib,
      dedup_title_level用Bucket分桶(88x fewer comparisons)
v4.3: 新增 batch_resolve_gnews_urls() — 所有模块完成后批量解析GNews redirect,
      解决fetch_one()内GNews semaphore(5)瓶颈导致0/1140 canonical_url的问题
v4.4: 三合一升级
  - _resolve_gnews_redirect: allow_redirects=False先读Location, fallback allow_redirects=True
  - fetch_one: feedburner_origlink/guid回退 + published_beijing时间标准化
  - fetch_full_text_batch: Actions端正文抓取(trafilatura), high+medium优先级
  - normalize_to_beijing_time: 统一北京时间+08:00
v4.5: Playwright无头浏览器解析GNews canonical_url
  - batch_resolve_gnews_with_browser: 用Chromium执行JS渲染，解决纯HTTP 0%覆盖率的问题
  - 仅处理high priority文章中的GNews URL（约60-70篇/日），串行6-8分钟
  - 单进程模式+no-sandbox，适配2核VM
v4.6: GNews RSS功能利用率优化
  - gnews_url(): 新增num(默认100)+when(默认7d)+topic模式
  - max_items 30→50, max_articles 500→800
  - fetch_one: GNews <source>元素提取(source_detail)
v4.8: priority_filter参数统一
  - batch_resolve_gnews_with_browser + fetch_full_text_batch 统一使用priority_map
  - 新增"all"选项(>=0)，支持全量抓取
"""

import asyncio
import aiohttp
import feedparser
import json
import re
import hashlib
import os
import socket
import calendar
import random
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

# 北京时间时区
BEIJING_TZ = timezone(timedelta(hours=8))

# 浏览器模拟请求头（用于GNews redirect解析和正文抓取）
_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

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


async def _resolve_gnews_redirect(session, gnews_url, timeout_sec=10):
    """
    v4.4: 解析GNews跟踪URL的最终跳转地址。
    策略1(快): allow_redirects=False → 读Location头（单跳，省带宽）
    策略2(兜底): allow_redirects=True → 跟踪全部跳转读resp.url
    加入浏览器模拟请求头 + 随机延迟，绕过Google反爬。
    """
    # 随机延迟避免触发Google速率限制
    await asyncio.sleep(random.uniform(0.3, 1.0))

    # 策略1: 读取302 Location头
    try:
        async with session.get(
            gnews_url,
            headers=_BROWSER_HEADERS,
            timeout=aiohttp.ClientTimeout(total=timeout_sec, connect=3),
            allow_redirects=False,
        ) as resp:
            if resp.status in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location", "")
                if location and "google.com" not in location:
                    # 补全相对URL
                    if location.startswith("/"):
                        from urllib.parse import urlparse
                        parsed = urlparse(gnews_url)
                        location = f"{parsed.scheme}://{parsed.netloc}{location}"
                    return location
    except Exception:
        pass

    # 策略2: 跟踪全部重定向
    try:
        async with session.get(
            gnews_url,
            headers=_BROWSER_HEADERS,
            timeout=aiohttp.ClientTimeout(total=timeout_sec + 5, connect=3),
            allow_redirects=True,
        ) as resp:
            if resp.status == 200:
                final_url = str(resp.url)
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
    headers = dict(_BROWSER_HEADERS)  # v4.4: 使用浏览器模拟头
    
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


# ============================================================
# 北京时间标准化 (v4.4)
# ============================================================

def normalize_to_beijing_time(published_str, published_parsed=None):
    """
    将各种格式的时间统一转换为北京时间 ISO 格式。
    优先使用 feedparser 提供的 published_parsed (time.struct_time)，
    其次用 dateutil.parser 解析原始字符串，最后手动格式匹配。
    
    返回: "2026-06-12T08:00:00+08:00" 格式字符串，失败返回 None
    """
    if not published_str and published_parsed is None:
        return None
    
    dt = None
    
    # 方法1: feedparser 的 time.struct_time（最可靠，UTC基准）
    if published_parsed is not None:
        try:
            ts = calendar.timegm(published_parsed)
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            pass
    
    # 方法2: dateutil.parser（灵活解析各种字符串格式）
    if dt is None and published_str:
        try:
            from dateutil import parser as dateutil_parser
            dt = dateutil_parser.parse(published_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)  # RSS常见：无时区默认UTC
        except Exception:
            pass
    
    # 方法3: 手动格式匹配（dateutil不可用时的fallback）
    if dt is None and published_str:
        for fmt in [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S GMT",
            "%a, %d %b %Y %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]:
            try:
                dt = datetime.strptime(published_str.strip(), fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                break
            except (ValueError, TypeError):
                continue
    
    if dt is None:
        return None
    
    dt_beijing = dt.astimezone(BEIJING_TZ)
    return dt_beijing.strftime("%Y-%m-%dT%H:%M:%S+08:00")


# ============================================================
# Actions端正文抓取 (v4.4)
# ============================================================

def _extract_text_sync(html, url):
    """同步函数：用trafilatura从HTML提取正文"""
    try:
        import trafilatura
        return trafilatura.extract(html, url=url, include_comments=False, include_tables=True)
    except ImportError:
        return None


async def fetch_full_text_async(session, url, timeout=15):
    """
    在Actions端异步抓取单篇文章正文。
    使用trafilatura提取纯文本，自动处理重定向。
    返回: 正文文本(>100字符) 或 None
    """
    try:
        async with session.get(
            url,
            headers=_BROWSER_HEADERS,
            timeout=aiohttp.ClientTimeout(total=timeout, connect=5),
            allow_redirects=True,
        ) as resp:
            if resp.status == 200:
                # 检查Content-Type，只处理HTML
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" not in content_type and "application/xhtml" not in content_type:
                    return None
                html = await resp.text()
                if not html or len(html) < 200:
                    return None
                # trafilatura是同步库，用run_in_executor避免阻塞事件循环
                loop = asyncio.get_event_loop()
                text = await loop.run_in_executor(None, _extract_text_sync, html, str(resp.url))
                if text and len(text) > 100:
                    return text[:10000]  # 限制单篇正文最大10000字符
    except Exception:
        pass
    return None


async def fetch_full_text_batch(articles_by_file, priority_filter="high", concurrency=10, timeout=15):
    """
    v4.4: 批量抓取文章正文（Actions端专用，在batch_resolve之后执行）。
    v4.8: priority_filter新增"all"选项，全量抓取(>=0分)。
    
    articles_by_file: {filename: [article_dicts]} — 原地修改
    priority_filter: "high"=仅high(>=10分), "high+medium"=high+medium(>=3分), "all"=全量(>=0)
    concurrency: 并发数
    timeout: 单篇超时秒数
    
    返回: (fetched_count, total_attempted, elapsed_seconds)
    """
    import time as _time
    start = _time.monotonic()
    
    # 收集需要抓取正文的文章
    fetch_items = []  # [(filename, article_index, url)]
    
    priority_map = {"high": 10, "high+medium": 3, "all": 0}
    min_priority = priority_map.get(priority_filter, 10)
    
    for filename, articles in articles_by_file.items():
        for idx, article in enumerate(articles):
            # 跳过已有正文的
            if article.get("full_text"):
                continue
            # 优先级过滤
            if article.get("priority", 0) < min_priority:
                continue
            # 获取URL：canonical_url优先 > link fallback
            url = article.get("canonical_url") or article.get("link", "")
            if not url or _is_gnews_url(url):
                continue  # 跳过GNews跟踪URL
            fetch_items.append((filename, idx, url))
    
    total = len(fetch_items)
    if not fetch_items:
        return 0, 0, 0.0
    
    print(f"  [FULL_TEXT] {total} articles to fetch (priority>={min_priority}, concurrency={concurrency})")
    
    sem = asyncio.Semaphore(concurrency)
    
    async with aiohttp.ClientSession() as session:
        async def _fetch_one(item):
            filename, idx, url = item
            async with sem:
                # 随机延迟，避免过于集中请求同一源
                await asyncio.sleep(random.uniform(0.1, 0.5))
                text = await fetch_full_text_async(session, url, timeout)
                return (filename, idx, text)
        
        # 分批处理
        batch_size = 50
        fetched = 0
        failed = 0
        
        for i in range(0, total, batch_size):
            batch = fetch_items[i:i+batch_size]
            batch_end = min(i + batch_size, total)
            
            tasks = [_fetch_one(item) for item in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    failed += 1
                    continue
                filename, idx, text = result
                if text:
                    articles_by_file[filename][idx]["full_text"] = text
                    fetched += 1
                else:
                    failed += 1
            
            elapsed = _time.monotonic() - start
            print(f"  [FULL_TEXT] Progress: {batch_end}/{total} "
                  f"({fetched} fetched, {failed} failed, {elapsed:.1f}s elapsed)")
    
    elapsed = _time.monotonic() - start
    print(f"  [FULL_TEXT] Done: {fetched}/{total} fetched ({failed} failed, {elapsed:.1f}s)")
    return fetched, total, elapsed


# ============================================================
# v4.5: Playwright 无头浏览器解析 GNews canonical_url
# ============================================================

async def batch_resolve_gnews_with_browser(articles_by_file, priority_filter="high"):
    """
    v4.5: 使用 Playwright 无头浏览器批量解析 GNews 跟踪 URL。
    只处理指定优先级的文章中的 GNews 链接（默认仅 high）。
    
    Google News 跟踪 URL 不是标准 HTTP 302，而是 JS 渲染后才跳转，
    纯 HTTP(batch_resolve_gnews_urls)覆盖率为 0%。
    Playwright 启动无头 Chromium，完整执行 JS 渲染，成功率预计 85-95%。
    
    v4.5优化：解析URL后直接从已加载的页面提取正文（trafilatura解析HTML），
    不需要后续fetch_full_text_batch再发第二次HTTP请求。
    
    articles_by_file: {filename: [article_dicts]} — 原地修改，补充 canonical_url + full_text
    priority_filter: "high"=仅high(>=10分), "high+medium"=high+medium(>=3分), "all"=全量(>=0)
    
    返回: (resolved_count, total_attempted, elapsed_seconds)
    """
    import time as _time
    start = _time.monotonic()
    
    # 收集需要解析的 GNews URL
    targets = []  # [(filename, article_index, gnews_url)]
    
    priority_map = {"high": 10, "high+medium": 3, "all": 0}
    min_priority = priority_map.get(priority_filter, 10)
    
    for filename, articles in articles_by_file.items():
        for idx, article in enumerate(articles):
            # 只处理 GNews URL 且尚未解析的
            if not _is_gnews_url(article.get("link", "")):
                continue
            if article.get("canonical_url"):
                continue  # 已有 canonical_url（feedburner_origlink/guid回退已解析）
            # 已有正文的不需要解析（路径1RSS提取已覆盖）
            if article.get("full_text"):
                continue
            # 优先级过滤
            if article.get("priority", 0) < min_priority:
                continue
            targets.append((filename, idx, article["link"]))
    
    total = len(targets)
    if not targets:
        print(f"  [PLAYWRIGHT] No high-priority GNews URLs to resolve, skipping")
        return 0, 0, 0.0
    
    print(f"  [PLAYWRIGHT] Resolving {total} GNews URLs with headless Chromium...")
    
    resolved = 0
    text_extracted = 0
    failed = 0
    
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print(f"  [PLAYWRIGHT] ERROR: playwright not installed, skipping browser resolve")
        print(f"  [PLAYWRIGHT] Install with: pip install playwright && playwright install chromium")
        return 0, total, _time.monotonic() - start
    
    # 预加载trafilatura用于正文提取（页面HTML已在内存，无需第二次网络请求）
    try:
        import trafilatura
        _has_trafilatura = True
    except ImportError:
        _has_trafilatura = False
        print(f"  [PLAYWRIGHT] WARNING: trafilatura not installed, will only resolve URLs without extracting text")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",       # 2核VM内存有限，禁用/dev/shm
                "--disable-gpu",
                "--single-process",              # 单进程模式，减少内存占用
            ]
        )
        
        context = await browser.new_context(
            user_agent=_BROWSER_HEADERS.get("User-Agent", "Mozilla/5.0"),
            viewport={"width": 1280, "height": 720},
        )
        
        page = await context.new_page()
        
        for i, (filename, idx, gnews_url) in enumerate(targets, 1):
            try:
                # 导航到 GNews 跟踪 URL，等待 JS 重定向完成
                # domcontentloaded 比 networkidle 更快，GNews redirect 不依赖完整网络加载
                await page.goto(gnews_url, wait_until="domcontentloaded", timeout=15000)
                
                # 额外等待 JS 重定向执行（GNews 有时需要 1-3 秒）
                await asyncio.sleep(random.uniform(1.0, 2.5))
                
                final_url = page.url
                
                # 验证：最终 URL 不再是 Google News 跟踪链接
                if final_url != gnews_url and "news.google.com" not in final_url:
                    articles_by_file[filename][idx]["canonical_url"] = final_url
                    resolved += 1
                    
                    # v4.5优化：页面已加载，直接提取正文（省掉后续fetch_full_text_batch的HTTP请求）
                    if _has_trafilatura and not articles_by_file[filename][idx].get("full_text"):
                        try:
                            html_content = await page.content()
                            loop = asyncio.get_event_loop()
                            extracted_text = await loop.run_in_executor(
                                None,
                                lambda: trafilatura.extract(html_content, url=final_url,
                                                           include_tables=True, favor_precision=True)
                            )
                            if extracted_text and len(extracted_text) > 100:
                                articles_by_file[filename][idx]["full_text"] = extracted_text[:10000]
                                text_extracted += 1
                        except Exception:
                            pass  # 正文提取失败不影响canonical_url解析
                else:
                    failed += 1
                    
            except Exception as e:
                # 超时/导航失败/页面崩溃等
                failed += 1
                err_name = type(e).__name__
                # 只在首次失败时打印详细错误，避免刷屏
                if failed <= 3:
                    print(f"  [PLAYWRIGHT] {err_name} for article {idx}: {str(e)[:100]}")
                continue
            
            # 每20篇打印进度
            if i % 20 == 0:
                elapsed = _time.monotonic() - start
                print(f"  [PLAYWRIGHT] Progress: {i}/{total} "
                      f"({resolved} resolved, {text_extracted} text, {failed} failed, {elapsed:.1f}s elapsed)")
            
            # 随机小延迟，避免被 Google 检测为自动化访问
            await asyncio.sleep(random.uniform(0.3, 0.8))
        
        await browser.close()
    
    elapsed = _time.monotonic() - start
    print(f"  [PLAYWRIGHT] Done: {resolved}/{total} resolved, {text_extracted} text extracted ({failed} failed, {elapsed:.1f}s)")
    return resolved, total, elapsed


async def fetch_one(session, url, tag, max_items=50, max_retries=1):
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
                    published_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
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
                    
                    # v4.5: 路径1 — RSS字段正文提取（零网络成本）
                    # 优先从content:encoded提取全文，其次从长description提取
                    rss_full_text = None
                    # 方法1: content:encoded（部分RSS源在字段中直接提供全文HTML）
                    content_list = entry.get("content")
                    if content_list:
                        for c in content_list:
                            ctype = c.get("type", "")
                            if ctype.startswith("text/html") or ctype.startswith("text/plain"):
                                raw = c.get("value", "")
                                text = re.sub(r'<[^>]+>', '', raw).strip()
                                if len(text) > 500:
                                    rss_full_text = text[:10000]
                                    break
                    # 方法2: description字段较长时视为全文（>800字符原文≈500字纯文本）
                    if not rss_full_text:
                        desc_raw = entry.get("description", "")
                        if len(desc_raw) > 800:
                            text = re.sub(r'<[^>]+>', '', desc_raw).strip()
                            if len(text) > 500:
                                rss_full_text = text[:10000]
                    if rss_full_text:
                        item["full_text"] = rss_full_text
                    
                    # v4.4: 北京时间标准化
                    beijing = normalize_to_beijing_time(published, published_parsed)
                    if beijing:
                        item["published_beijing"] = beijing
                    
                    # v4.4: canonical_url 多源回退（仅本地字段，不做网络请求）
                    # GNews redirect解析由 batch_resolve_gnews_urls() 统一处理，不在fetch_one中逐个解析
                    if _is_gnews_url(link):
                        # 方法1: feedburner_origlink（FeedBurner代理RSS的真实链接）
                        origlink = entry.get("feedburner_origlink")
                        if origlink and "news.google.com" not in origlink:
                            item["canonical_url"] = origlink
                        else:
                            # 方法2: guid字段有时就是真实URL
                            guid = entry.get("guid", entry.get("id", ""))
                            if guid and guid.startswith("http") and "news.google.com" not in guid:
                                item["canonical_url"] = guid
                        # v4.6: GNews <source>元素提取 — 原始来源名称+主页URL
                        source_elem = entry.get("source")
                        if source_elem:
                            source_detail = {}
                            if hasattr(source_elem, 'get'):
                                # feedparser返回的source是dict-like对象
                                source_detail["name"] = source_elem.get("title", source_elem.get("value", ""))
                                source_detail["url"] = source_elem.get("href", source_elem.get("url", ""))
                            elif isinstance(source_elem, dict):
                                source_detail["name"] = source_elem.get("title", source_elem.get("value", ""))
                                source_detail["url"] = source_elem.get("href", source_elem.get("url", ""))
                            elif isinstance(source_elem, str):
                                source_detail["name"] = source_elem
                            if source_detail.get("name"):
                                item["source_detail"] = source_detail
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


async def fetch_feed_concurrent_async(feeds, max_items=50):
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
def fetch_feed_concurrent(feeds, max_workers=15, max_items=50):
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
                    if t1 and t2:
                        # v4.6 fix: strip tzinfo to avoid naive-aware subtraction error
                        if t1.tzinfo is not None:
                            t1 = t1.replace(tzinfo=None)
                        if t2.tzinfo is not None:
                            t2 = t2.replace(tzinfo=None)
                        if abs((t1 - t2).total_seconds()) < hours * 3600:
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

    max_articles = config.get("max_articles", 800)
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


def gnews_url(query=None, topic=None, hl="en-US", gl="US", ceid="US:en", num=100, when="7d"):
    """
    生成 Google News RSS URL。v4.6 支持两种模式：
    
    1. 搜索模式（默认）：query非空 → /rss/search?q={query}
       - num: 返回文章数，最大100，默认100
       - when: 时间过滤，默认"7d"（7天窗口），可选"24h"/"1h"/None
       
    2. 专题模式：topic非空 → /rss/headlines/section/topic/{topic}
       - Topic是Google编辑精选，num上限30，不支持when
       - 已知Topic: WORLD / NATION / BUSINESS / TECHNOLOGY / ENTERTAINMENT / SCIENCE / SPORTS / HEALTH
    """
    import urllib.parse
    
    if topic:
        # 专题模式：编辑精选，不支持num/when
        base = f"https://news.google.com/rss/headlines/section/topic/{urllib.parse.quote(topic)}"
        return f"{base}?hl={hl}&gl={gl}&ceid={ceid}"
    else:
        # 搜索模式
        if not query:
            raise ValueError("gnews_url: either query or topic must be provided")
        # 拼接时间过滤运算符（字符串拼接避免urlencode编码冒号）
        q_full = f"{query} when:{when}" if when else query
        q_encoded = urllib.parse.quote(q_full, safe=':')
        return (f"https://news.google.com/rss/search?q={q_encoded}"
                f"&hl={hl}&gl={gl}&ceid={ceid}&num={min(num, 100)}")
