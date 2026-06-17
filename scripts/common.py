#!/usr/bin/env python3
"""
common.py v6.0 — 全球商业情报仪表盘共享工具库 (asyncio+aiohttp + RapidFuzz版)
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
v4.7.1: 从v4.7回滚+可观测性增强
  - 回滚v4.8/v4.8.1/v4.8.2的Playwright medium和full_text all改动
  - 新增phase_log()时间戳日志函数 + 关键print加flush=True
  - 解决tee缓冲导致Actions取消时进度日志丢失的问题
v4.7.3: 时间戳修复三合一
  - 未来日期过滤：run_module_async() age filter + global_dedup() 加前向截断(+3天容差)
  - 无pubDate回退：fetch_one()空published字段回退到抓取时间(北京时间)+[fallback]日志
  - 空标题跳过：fetch_one()空title条目跳过+[skip]日志
v6.0: 增量采集架构升级
  - gnews_url(): 支持环境变量 OVERSEAS_WHEN_DAYS/OVERSEAS_NUM 覆盖默认值
  - SeenIndex类: 持久化去重索引，2层同源去重(canonical_url + source|title)
  - normalize_title_for_dedup(): 去重用标题归一化
  - last_fetch_date/daily_stats: 补漏计算+采集统计
  - prune_old_entries(): 90天自动清理，防索引膨胀
v6.0.2: 进展豁免+不同来源保留
  - _extract_numbers(): 提取标题中的数字用于变化检测
  - _has_progress_keywords(): 中英文进展关键词匹配(中文子串+英文词边界)
  - _is_progress_update(): 进展判断(数字变化≥20% 或 新增进展关键词)
  - dedup_title_level(): 进展报道保留+标[进展], 不同来源保留+标[不同来源]
  - KEEP_DIFFERENT_SOURCE参数(ODH_KEEP_DIFFERENT_SOURCE, 默认1=保留)
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

# v4.7.1: 可观测性 — 强制flush的时间戳日志函数
import time as _time_mod
_phase_start = _time_mod.monotonic()

def phase_log(msg):
    """带时间戳+累计耗时的日志输出，强制flush确保tee可见"""
    elapsed = _time_mod.monotonic() - _phase_start
    print(f"[{_time_mod.strftime('%Y-%m-%d %H:%M:%S')}] [+{elapsed:.0f}s] {msg}", flush=True)

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

# v6.0.3: 条件诊断输出 — 仅ODH_DEBUG=1时打印
if os.environ.get("ODH_DEBUG"):
    import sys as _diag_sys
    print(f"[DIAG] common.py importing... PID={os.getpid()} Python={'.'.join(map(str,_diag_sys.version_info[:3]))}", flush=True)

feedparser.USER_AGENT = "Mozilla/5.0 (compatible; OverseasDataHub/1.0; +https://github.com/WOHO99/overseas-data-hub)"

RATE_LIMITED_DOMAINS = ["news.google.com"]

# 北京时间时区
BEIJING_TZ = timezone(timedelta(hours=8))


# ============================================================
# v6.0.1: 可配置参数 — 消除幻觉硬编码，所有参数附来源和合法范围
# 修改规则: 1) 仅通过 _env_param 定义 2) 附来源/source标注 3) 附合法范围[min,max]
# 环境变量前缀: ODH_ (Overseas Data Hub)
# ============================================================

def _env_param(name, default, typ=float, min_val=None, max_val=None, source="未标注", note=""):
    """
    从环境变量读取可配置参数，附范围校验和来源标注。
    超范围行为: WARNING + 降回默认值(不exit，由validate_params统一校验)。
    """
    raw = os.environ.get(name)
    val = default
    overridden = False

    if raw is not None:
        try:
            val = typ(raw)
            overridden = True
        except (ValueError, TypeError):
            print(f"  [CONFIG] {name}={raw} 无法转为{typ.__name__}，使用默认值{default}", flush=True)

    # 范围校验
    if min_val is not None and val < min_val:
        print(f"  [CONFIG] WARNING: {name}={val} < 下限{min_val}，降回默认值{default} "
              f"[来源:{source}]{f' ({note})' if note else ''}", flush=True)
        val = default
        overridden = False

    if max_val is not None and val > max_val:
        print(f"  [CONFIG] WARNING: {name}={val} > 上限{max_val}，降回默认值{default} "
              f"[来源:{source}]{f' ({note})' if note else ''}", flush=True)
        val = default
        overridden = False

    if overridden:
        print(f"  [CONFIG] {name}={val} (from env, default={default}) "
              f"[来源:{source}]{f' ({note})' if note else ''}", flush=True)

    return val


# --- 去重参数 ---
DEDUP_TITLE_THRESHOLD = _env_param(
    "ODH_DEDUP_THRESHOLD", 0.85, float, 0.5, 1.0,
    "通用参考值，未校准", "待30天真实数据离线校准误杀/漏杀率"
)
DEDUP_TITLE_HOURS = _env_param(
    "ODH_DEDUP_HOURS", 24, int, 1, 168,
    "估算未校准(产品决策)", "同一事件跟进报道去重时间窗口(小时)，需内容负责人拍板"
)
MAX_FUTURE_DAYS = _env_param(
    "ODH_MAX_FUTURE_DAYS", 3, int, 0, 7,
    "估算未校准", "超过此天数的未来日期文章视为异常并过滤"
)
PRUNE_AGE_DAYS = _env_param(
    "ODH_PRUNE_AGE_DAYS", 90, int, 14, 365,
    "估算未校准", "seen_index去重记忆保留天数，须>=本地数据保留期(当前30天)"
)

# --- 并发/网络参数 ---
SEMAPHORE_GNEWS = _env_param(
    "ODH_SEMAPHORE_GNEWS", 5, int, 1, 20,
    "估算未校准", "Google News并发限制，Google限速策略不透明"
)

# --- Playwright参数 ---
PLAYWRIGHT_TIMEOUT_SEC = _env_param(
    "ODH_PLAYWRIGHT_TIMEOUT", 15, int, 5, 60,
    "估算未校准", "Playwright页面加载超时(秒)"
)
PLAYWRIGHT_WAIT_MIN = _env_param(
    "ODH_PLAYWRIGHT_WAIT_MIN", 1.0, float, 0.5, 5.0,
    "估算未校准", "Playwright JS渲染最小等待(秒)"
)
PLAYWRIGHT_WAIT_MAX = _env_param(
    "ODH_PLAYWRIGHT_WAIT_MAX", 2.5, float, 1.0, 10.0,
    "估算未校准", "Playwright JS渲染最大等待(秒)"
)
# v6.0.8: Playwright早停参数（从硬编码迁移到_env_param）
PW_EARLY_STOP_WINDOW = _env_param(
    "ODH_PW_EARLY_STOP_WINDOW", 15, int, 5, 50,
    "v6.0.6 P0/v6.0.8迁移", "早停观测窗口K（近K篇成功率低于阈值则早停）"
)
PW_EARLY_STOP_THRESHOLD = _env_param(
    "ODH_PW_EARLY_STOP_THRESHOLD", 0.10, float, 0.01, 0.50,
    "v6.0.6 P0/v6.0.8迁移", "早停成功率阈值下限（动态阈值=前30篇基线×0.25与此值取大）"
)
PW_EARLY_STOP_MIN_REMAIN = _env_param(
    "ODH_PW_EARLY_STOP_MIN_REMAIN", 10, int, 1, 50,
    "v6.0.6 P0/v6.0.8迁移", "剩余队列少于此数不触发早停（防误杀）"
)
PW_EARLY_STOP_WARMUP = _env_param(
    "ODH_PW_EARLY_STOP_WARMUP", 5, int, 1, 20,
    "v6.0.6 P0/v6.0.8迁移", "Context重建后热身期（前N篇不检查早停）"
)
PW_BASELINE_SAMPLE_SIZE = _env_param(
    "ODH_PW_BASELINE_SAMPLE_SIZE", 30, int, 10, 100,
    "v6.0.8新增", "基线成功率采样量（前N篇文章累积成功率，跨Context重建保留）"
)

# --- 熔断/告警参数 ---
CIRCUIT_BREAKER_THRESHOLD = _env_param(
    "ODH_CIRCUIT_BREAKER", 3, int, 2, 7,
    "估算未校准", "连续零产出天数达此值触发熔断(天)，周末/假日可能误判"
)
SIGNAL_MIN_BASELINE = _env_param(
    "ODH_SIGNAL_MIN_BASELINE", 3, int, 1, 10,
    "估算未校准", "信号告警最低基线值，低频但重要信号可能永远不触发"
)

# --- 去重豁免参数 ---
KEEP_DIFFERENT_SOURCE = _env_param(
    "ODH_KEEP_DIFFERENT_SOURCE", 1, int, 0, 1,
    "产品决策(2026-06-14)", "同标题不同来源是否保留: 1=保留并标[不同来源], 0=不保留"
)

# --- DRY RUN模式 ---
DRY_RUN = _env_param(
    "OVERSEAS_DRY_RUN", 0, int, 0, 1,
    "v6.0.4新增", "1=跳过Playwright和full_text, 仅做dedup+index+统计; 0=正常运行"
)
# 进展关键词（含常见词形变体）：出现任一即视为跟进报道，强制保留并标[进展]
# 中文词直接子串匹配，英文词用\b词边界匹配
_PROGRESS_KEYWORDS_CN = ["遇难", "死亡", "确诊", "逮捕", "宣判", "预警", "辟谣"]
_PROGRESS_KEYWORDS_EN = [
    r"\bkills?\b", r"\bkilled\b", r"\bdead\b", r"\bdeath\b", r"\bdeaths\b",
    r"\bconfirmed\b", r"\barrest(s|ed)?\b", r"\bsentenced\b",
    r"\bwarning\b", r"\bdebunked?\b",
]
_PROGRESS_EN_PATTERN = re.compile("|".join(_PROGRESS_KEYWORDS_EN), re.IGNORECASE)


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

# 全局并发控制（SEMAPHORE_GNEWS 已通过 _env_param 定义，见上方参数区块）
SEMAPHORE_GLOBAL = 50
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


def load_source_tier_override(config_dir):
    """v6.0.8: 从source_tier_override.yaml加载domain→tier映射。
    返回 dict{domain_pattern: tier}，支持后缀匹配(.example.com匹配子域名)。
    """
    override_path = os.path.join(config_dir, "source_tier_override.yaml")
    if not os.path.exists(override_path):
        return {}
    try:
        with open(override_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("overrides", {}) or {}
    except (yaml.YAMLError, OSError) as e:
        phase_log(f"[CONFIG] Failed to load source_tier_override.yaml: {e}")
        return {}


def _lookup_tier_by_domain(url, tier_override):
    """v6.0.8: 根据URL的domain查找tier_override。
    优先精确匹配，后缀匹配(.example.com)次之。
    返回 tier 字符串或 None。
    """
    if not url or not tier_override:
        return None
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
    except Exception:
        return None
    if not domain:
        return None
    # 去掉 www.
    if domain.startswith("www."):
        domain = domain[4:]
    # 精确匹配
    if domain in tier_override:
        return tier_override[domain]
    # 后缀匹配: .example.com 匹配 sub.example.com
    parts = domain.split(".")
    for i in range(1, len(parts)):
        suffix = "." + ".".join(parts[i:])
        if suffix in tier_override:
            return tier_override[suffix]
    return None


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


def get_source_tier(source_tag, authority_map, tier_override=None, canonical_url=None):
    """v6.0.3/v6.0.8: 从源权威度系数派生A-E等级
    v6.0.8新增: 优先按 canonical_url domain 查找 tier_override
    回退: source tag + authority_map 系数
    A(>=1.5): 顶级官方/通讯社 | B(>=1.2): 主流大报 | C(==1.0, default): 一般媒体
    D(<1.0): 低可信度/博客 | E(无匹配且GNews): 未解析GNews
    """
    # v6.0.8: 优先 domain lookup
    if tier_override and canonical_url:
        domain_tier = _lookup_tier_by_domain(canonical_url, tier_override)
        if domain_tier:
            return domain_tier
    # 回退: 原有 source tag + authority_map 逻辑
    if not source_tag:
        return "E"
    # GNews未解析源：默认系数1.0且无单独配置 → E
    if source_tag.startswith("GNews") and "|" in source_tag:
        coeff = get_source_coefficient(source_tag, authority_map)
        if coeff == 1.0:
            return "E"  # GNews默认系数，未单独配置
    coeff = get_source_coefficient(source_tag, authority_map)
    if coeff >= 1.5:
        return "A"
    elif coeff >= 1.2:
        return "B"
    elif coeff >= 1.0:
        return "C"
    else:
        return "D"


# ============================================================
# v6.0.3: 正文清洗 + 安全页检测
# ============================================================

# 安全页检测模式(8种) — 检出则丢弃(full_text=None)
_SECURITY_PATTERNS = [
    r"(?i)cloudflare.*ray\s+id",                    # Cloudflare challenge
    r"(?i)access\s+denied",                          # 403/通配
    r"(?i)performing\s+security\s+verification",     # 通用安全验证页
    r"(?i)verify\s+(you\s+are|that\s+you)[\s'a]*human",  # reCAPTCHA/验证人类
    r"(?i)complete\s+(a\s+)?security\s+check",       # 安全检查
    r"(?i)member\s+login",                           # 付费墙登录
    r"(?i)subscribe\s+(to\s+continue|now|to\s+read)", # 付费墙订阅
    r"(?i)\b403\b.*forbidden",                       # 403 Forbidden
]


def is_security_page(text):
    """v6.0.3: 检测正文是否为安全页/反爬页/付费墙。
    输入: 正文文本(可为None)。返回 True=安全页(应丢弃)。
    判定规则: 正文前500字符匹配任一_SECURITY_PATTERNS。
    """
    if not text:
        return False
    check_block = text[:500].lower()
    for pat in _SECURITY_PATTERNS:
        if re.search(pat, check_block):
            return True
    return False


# v6.0.4: 安全页源级退化 — 连续3次安全页 → 自动跳过该源的full_text
_SECURITY_SKIP_THRESHOLD = _env_param("ODH_SECURITY_SKIP_THRESHOLD", 3, int, min_val=1, max_val=10)
_security_page_counts = {}   # {source_name: consecutive_count}
_auto_skip_fulltext_sources = set()  # 自动加入的源黑名单

def check_security_page_source(text, source_name=""):
    """v6.0.4: 安全页检测 + 源级退化追踪。
    返回 True=安全页(应丢弃)。
    副作用: 连续3次安全页 → source加入_auto_skip_fulltext_sources。
    成功提取则重置计数器。
    """
    if not text or not is_security_page(text):
        # 成功提取: 重置该源的计数器
        if source_name and source_name in _security_page_counts:
            _security_page_counts[source_name] = 0
        return False
    # 安全页: 累加计数
    if source_name:
        _security_page_counts[source_name] = _security_page_counts.get(source_name, 0) + 1
        if _security_page_counts[source_name] >= _SECURITY_SKIP_THRESHOLD:
            _auto_skip_fulltext_sources.add(source_name)
            phase_log(f"[SECURITY_DEGRADE] Source '{source_name}' auto-added to skip_fulltext "
                     f"(consecutive={_security_page_counts[source_name]})")
    return True

def should_skip_fulltext(source_name):
    """v6.0.4: 判断该源是否应跳过full_text (付费墙白名单 或 安全页退化)"""
    return source_name in _auto_skip_fulltext_sources


def clean_full_text(text, title=None, source_name=""):
    """v6.0.4.1: 确定性正文清洗 7 规则，在 full_text 赋值前调用。
    Rule 0: html.unescape() — 解码HTML实体
    Rule 1 (trafilatura #160): 首行==标题 → 删首行（放宽容差）
    Rule 2 (trafilatura #768): 连续重复段落 → 去重
    Rule 3: is_security_page → return None (丢弃)
    Rule 4 (v6.0.4): 源级退化追踪 — 连续3次安全页→自动跳过该源
    Rule 5: 超长单行 → 按句分割（trafilatura/Playwright有时输出无换行段落）
    Rule 6: 去除HTML标签残留（strip_tags保险）
    返回: 清洗后正文 或 None(安全页/无效)
    """
    import html as _html
    if not text:
        return None
    # Rule 0: HTML实体解码 (&nbsp; → 空格, &rsquo; → ', etc.)
    text = _html.unescape(text)
    # Rule 6: 去除残留HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    # Rule 1: 首行==标题 → 移除（放宽容差：首行是标题子串也移除）
    lines = text.split("\n")
    if title and lines:
        first_line = lines[0].strip()
        # 去标点后比较
        title_clean = re.sub(r'[^\w\s]', '', title.lower()).strip()
        first_clean = re.sub(r'[^\w\s]', '', first_line.lower()).strip()
        if title_clean and first_clean and (
            title_clean == first_clean
            or first_clean in title_clean
            or title_clean.startswith(first_clean[:30])  # 前30字符匹配也算
        ):
            lines = lines[1:]
    # Rule 5: 超长单行分割（>1500字符的行按句号分割）
    split_lines = []
    for line in lines:
        if len(line) > 1500:
            # 按英文句号+空格 或 中文句号 分割
            sentences = re.split(r'(?<=[.。！？])\s*', line)
            split_lines.extend(sentences)
        else:
            split_lines.append(line)
    lines = split_lines
    # Rule 2: 连续重复段落 → 去重
    if len(lines) > 2:
        deduped = [lines[0]]
        for i in range(1, len(lines)):
            if lines[i].strip() and lines[i].strip() == lines[i-1].strip():
                continue  # 跳过与前一行完全相同的非空行
            deduped.append(lines[i])
        lines = deduped
    result = "\n".join(lines).strip()
    if not result or len(result) < 50:
        return None
    # Rule 3+4: 安全页检测 + 源级退化追踪
    if check_security_page_source(result, source_name):
        return None
    return result[:10000]


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

def _extract_text_sync(html, url, include_tables=True):
    """v6.0.4: 同步函数：用trafilatura从HTML提取正文，favor_recall回退。
    策略: 先默认extract → 失败则favor_recall=True重试 → 仍失败返回None
    """
    try:
        import trafilatura
    except ImportError:
        return None
    # 第一次: 默认提取(favor_precision)
    text = trafilatura.extract(html, url=url, include_comments=False, include_tables=include_tables)
    if text and len(text) > 100:
        return text
    # 第二次: favor_recall + deduplicate 回退（trafilatura无--compat参数，这是正确替代方案）
    text2 = trafilatura.extract(html, url=url, include_comments=False,
                                include_tables=include_tables,
                                favor_recall=True, deduplicate=True)
    return text2


async def fetch_full_text_async(session, url, timeout=15, source_name=""):
    """
    在Actions端异步抓取单篇文章正文。
    使用trafilatura提取纯文本，自动处理重定向。
    v6.0.4: 增加source_name参数用于安全页源级退化追踪。
    返回: 正文文本(>100字符) 或 None
    """
    # v6.0.4: 源级退化 — 已被auto-skip的源直接返回None
    if source_name and should_skip_fulltext(source_name):
        return None
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
                    # v6.0.4: 清洗(标题残留+重复段落+安全页+源级退化)
                    text = clean_full_text(text, source_name=source_name)
                    if text:
                        return text[:10000]
                    return None  # 安全页或清洗后无效
    except Exception:
        pass
    return None


async def fetch_full_text_batch(articles_by_file, priority_filter="high", concurrency=10, timeout=15):
    """
    v4.4: 批量抓取文章正文（Actions端专用，在batch_resolve之后执行）。
    v4.7.1: 回滚v4.8改动，恢复v4.7逻辑(high+medium)，加flush日志。
    v6.0.4: DRY_RUN模式支持。
    
    articles_by_file: {filename: [article_dicts]} — 原地修改
    priority_filter: "high"=仅high(>=10分), "high+medium"=high+medium(>=3分)
    concurrency: 并发数
    timeout: 单篇超时秒数
    
    返回: (fetched_count, total_attempted, elapsed_seconds)
    """
    import time as _time
    start = _time.monotonic()
    
    # v6.0.4: DRY_RUN模式 — 跳过full_text批量抓取
    if DRY_RUN:
        phase_log("[FULL_TEXT] DRY_RUN mode: skipping full_text batch fetch")
        return 0, 0, 0.0
    
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
            # v6.0.4: 获取source_name用于安全页源级退化
            source_name = article.get("source", "")
            fetch_items.append((filename, idx, url, source_name))
    
    total = len(fetch_items)
    if not fetch_items:
        return 0, 0, 0.0
    
    phase_log(f"[FULL_TEXT] {total} articles to fetch (priority>={min_priority}, concurrency={concurrency})")
    
    sem = asyncio.Semaphore(concurrency)
    
    async with aiohttp.ClientSession() as session:
        async def _fetch_one(item):
            filename, idx, url, source_name = item
            async with sem:
                # 随机延迟，避免过于集中请求同一源
                await asyncio.sleep(random.uniform(0.1, 0.5))
                text = await fetch_full_text_async(session, url, timeout, source_name=source_name)
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
            phase_log(f"[FULL_TEXT] Progress: {batch_end}/{total} "
                  f"({fetched} fetched, {failed} failed, {elapsed:.1f}s elapsed)")
    
    elapsed = _time.monotonic() - start
    phase_log(f"[FULL_TEXT] Done: {fetched}/{total} fetched ({failed} failed, {elapsed:.1f}s)")
    return fetched, total, elapsed


# ============================================================
# v4.5: Playwright 无头浏览器解析 GNews canonical_url
# ============================================================

async def batch_resolve_gnews_with_browser(articles_by_file, priority_filter="high", max_items=0):
    """
    v4.9: max_items 参数限制最大解析数量，按优先级降序截取。
    防止 high+medium scope 下 2800+ 篇 GNews URL 超时。max_items=0 不限制。
    
    v4.5: 使用 Playwright 无头浏览器批量解析 GNews 跟踪 URL。
    只处理指定优先级的文章中的 GNews 链接（默认仅 high）。
    Google News 跟踪 URL 不是标准 HTTP 302，而是 JS 渲染后才跳转，
    纯 HTTP(batch_resolve_gnews_urls)覆盖率为 0%。
    Playwright 启动无头 Chromium，完整执行 JS 渲染，成功率预计 85-95%。
    
    v4.5优化：解析URL后直接从已加载的页面提取正文（trafilatura解析HTML），
    不需要后续fetch_full_text_batch再发第二次HTTP请求。
    v4.9: 每60篇冷却30s防止Google限速。
    v6.0.6 P0: 滑落成功率早停 + 每30篇重建Browser Context
      - 跟踪近K篇成功率，滑落到阈值以下→提前终止（剩余<M篇时不触发防误杀）
      - 每30篇重建context避免指纹累积导致成功率衰退
    
    articles_by_file: {filename: [article_dicts]} — 原地修改，补充 canonical_url + full_text
    priority_filter: "high"=仅high(>=10分), "high+medium"=high+medium(>=3分), "all"=全量(>=0)
    max_items: 最大解析数量，0=不限制
    
    返回: (resolved_count, total_attempted, elapsed_seconds)
    """
    import time as _time
    start = _time.monotonic()
    
    # v6.0.4: DRY_RUN模式 — 跳过Playwright
    if DRY_RUN:
        phase_log("[PLAYWRIGHT] DRY_RUN mode: skipping Playwright + full_text")
        return 0, 0, 0.0
    
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
            # v4.9: 已有正文但无canonical_url的也要解析（正文阅读器需要原文链接）
            if article.get("full_text") and article.get("canonical_url"):
                continue  # 两者都有，跳过
            # 优先级过滤
            if article.get("priority", 0) < min_priority:
                continue
            targets.append((filename, idx, article["link"], article.get("priority", 0)))
    
    # v4.9: 按优先级降序排序，截取前 max_items 篇
    targets.sort(key=lambda x: x[3], reverse=True)
    if max_items > 0 and len(targets) > max_items:
        phase_log(f"[PLAYWRIGHT] Trimming {len(targets)} targets to top {max_items} by priority")
        targets = targets[:max_items]
    # 去掉priority列
    targets = [(f, i, u) for f, i, u, _ in targets]
    
    total = len(targets)
    if not targets:
        phase_log("[PLAYWRIGHT] No high-priority GNews URLs to resolve, skipping")
        return 0, 0, 0.0
    
    phase_log(f"[PLAYWRIGHT] Resolving {total} GNews URLs with headless Chromium...")
    
    resolved = 0
    text_extracted = 0
    failed = 0
    # v6.0.8: 早停参数统一从 _env_param 读取
    _window = PW_EARLY_STOP_WINDOW
    _threshold_floor = PW_EARLY_STOP_THRESHOLD
    _min_remain = PW_EARLY_STOP_MIN_REMAIN
    _warmup = PW_EARLY_STOP_WARMUP
    _baseline_n = PW_BASELINE_SAMPLE_SIZE
    recent_results = []          # 滑动窗口: True=成功, False=失败
    early_stopped = False
    context_rebuild_at = 0       # 最近一次Context重建的文章序号
    # v6.0.8: 动态基线 — 前N篇累积成功率，跨Context重建保留
    baseline_success = 0         # 基线期内成功数
    baseline_total = 0           # 基线期内总处理数
    baseline_rate = None         # 基线成功率（前N篇处理完后计算）
    adaptive_threshold = _threshold_floor  # 初始=下限，基线建立后更新
    
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
        
        # v6.0.4: playwright_stealth — 规避反爬指纹检测
        try:
            from playwright_stealth import stealth_async
            await stealth_async(page)
        except ImportError:
            phase_log("[PLAYWRIGHT] playwright-stealth not installed, skipping stealth")
        
        for i, (filename, idx, gnews_url) in enumerate(targets, 1):
            # v6.0.6 P0: 每30篇重建Browser Context，避免指纹累积
            if i > 1 and (i - 1) % 30 == 0:
                try:
                    await context.close()
                except Exception:
                    pass
                context = await browser.new_context(
                    user_agent=_BROWSER_HEADERS.get("User-Agent", "Mozilla/5.0"),
                    viewport={"width": 1280, "height": 720},
                )
                page = await context.new_page()
                try:
                    from playwright_stealth import stealth_async
                    await stealth_async(page)
                except ImportError:
                    pass
                # v6.0.8: Context重建后重置滑动窗口（仅影响近K篇观测），基线不清空
                recent_results.clear()
                context_rebuild_at = i  # 记录重建位置，用于热身期
                phase_log(f"[PLAYWRIGHT] Context rebuilt at article {i} (anti-fingerprint, window reset, baseline preserved)")
            
            try:
                # 导航到 GNews 跟踪 URL，等待 JS 重定向完成
                # domcontentloaded 比 networkidle 更快，GNews redirect 不依赖完整网络加载
                await page.goto(gnews_url, wait_until="domcontentloaded", timeout=PLAYWRIGHT_TIMEOUT_SEC * 1000)
                
                # 额外等待 JS 重定向执行（GNews 有时需要 1-3 秒）
                await asyncio.sleep(random.uniform(PLAYWRIGHT_WAIT_MIN, PLAYWRIGHT_WAIT_MAX))
                
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
                                # v6.0.4: 清洗+源级退化
                                article_title = articles_by_file[filename][idx].get("title")
                                article_source = articles_by_file[filename][idx].get("source", "")
                                cleaned = clean_full_text(extracted_text, title=article_title, source_name=article_source)
                                if cleaned:
                                    articles_by_file[filename][idx]["full_text"] = cleaned[:10000]
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
            
            # v6.0.8: 更新滑动窗口 + 基线累积 + 动态阈值早停
            last_success = (i <= len(targets) and articles_by_file[filename][idx].get("canonical_url") 
                           and "news.google.com" not in articles_by_file[filename][idx].get("canonical_url", ""))
            recent_results.append(last_success)
            if len(recent_results) > _window:
                recent_results.pop(0)
            
            # 基线累积：前N篇文章跨Context重建保留
            if baseline_rate is None:
                baseline_total += 1
                if last_success:
                    baseline_success += 1
                if baseline_total >= _baseline_n:
                    baseline_rate = baseline_success / baseline_total
                    adaptive_threshold = max(_threshold_floor, baseline_rate * 0.25)
                    phase_log(f"[PLAYWRIGHT] Baseline established: {baseline_success}/{baseline_total} = "
                              f"{baseline_rate:.0%}, adaptive_threshold = {adaptive_threshold:.2f} "
                              f"(cap=max({_threshold_floor:.0%}, {baseline_rate:.0%}×0.25))")
            
            # 热身期：Context重建后前N篇不检查早停，给新context积累足够样本
            in_warmup = (context_rebuild_at > 0 and i <= context_rebuild_at + _warmup)
            if len(recent_results) >= _window and not early_stopped and not in_warmup:
                recent_rate = sum(recent_results) / len(recent_results)
                remaining = total - i
                if recent_rate < adaptive_threshold and remaining >= _min_remain:
                    elapsed = _time.monotonic() - start
                    phase_log(f"[PLAYWRIGHT] Early stop: recent {_window} success rate "
                          f"{recent_rate:.0%} < adaptive_threshold {adaptive_threshold:.0%} "
                          f"(baseline={baseline_rate:.0%}×0.25 cap={_threshold_floor:.0%}) "
                          f"({remaining} articles remaining, {resolved} resolved, {elapsed:.1f}s elapsed)")
                    early_stopped = True
                    # 标记所有未被处理的文章，让下一轮可以重新尝试
                    for skip_i in range(i, len(targets)):
                        sf, si, _ = targets[skip_i]
                        articles_by_file[sf][si]["pw_skipped_early_stop"] = True
                    break
            
            if not last_success:
                continue
            
            # 每20篇打印进度
            if i % 20 == 0:
                elapsed = _time.monotonic() - start
                phase_log(f"[PLAYWRIGHT] Progress: {i}/{total} "
                      f"({resolved} resolved, {text_extracted} text, {failed} failed, {elapsed:.1f}s elapsed)")
            
            # v6.0.4: 随机延迟2-5s，模拟人类行为（原0.5-1.2s太短易被反爬识别）
            await asyncio.sleep(random.uniform(2.0, 5.0))
            
            # v4.9: 每60篇冷却30s，防Google限速导致成功率暴跌
            # (v4.7.1实测: 前60篇83%成功率，之后34%)
            if i % 60 == 0 and i > 0:
                phase_log(f"[PLAYWRIGHT] Cooldown: 30s pause after {i} articles (anti-rate-limit)")
                await asyncio.sleep(30)
        
        await browser.close()
    
    elapsed = _time.monotonic() - start
    early_stop_note = " (early stopped)" if early_stopped else ""
    phase_log(f"[PLAYWRIGHT] Done{early_stop_note}: {resolved}/{total} resolved, {text_extracted} text extracted ({failed} failed, {elapsed:.1f}s)")
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

                    # FIX: v4.7.3 - 空标题条目跳过
                    if not title.strip():
                        print(f"  [skip] empty title, link={link[:80]}")
                        continue

                    published = entry.get("published", entry.get("updated", ""))
                    published_parsed = entry.get("published_parsed") or entry.get("updated_parsed")

                    # FIX: v4.7.3 - 无pubDate回退到抓取时间（北京时间）
                    if not published:
                        bj_tz = timezone(timedelta(hours=8))
                        fetch_time_bj = datetime.now(bj_tz).strftime("%Y-%m-%d %H:%M:%S +0800")
                        published = fetch_time_bj
                        print(f"  [fallback] no pubDate for '{title[:40]}', using fetch_time: {fetch_time_bj}")

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
                        # v6.0.4: 清洗(标题残留+重复段落+安全页+源级退化)
                        cleaned = clean_full_text(rss_full_text, title=title, source_name=tag)
                        if cleaned:
                            item["full_text"] = cleaned
                    
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


def dedup_title_level(items, threshold=None, hours=None):
    """v4.4: 核心实体词分桶 + RapidFuzz，解决前3字符分桶的假阴性问题
    v6.0.1: threshold/hours 默认值从参数区块读取（可通过ODH_DEDUP_THRESHOLD/ODH_DEDUP_HOURS覆盖）
    v6.0.2: 进展豁免 + 不同来源保留
      - 数字变化≥20% 或 进展关键词 → 保留并标[进展]
      - 不同来源(KEEP_DIFFERENT_SOURCE=1) → 保留并标[不同来源]
    """
    if threshold is None:
        threshold = DEDUP_TITLE_THRESHOLD
    if hours is None:
        hours = DEDUP_TITLE_HOURS
    if len(items) < 2:
        return items
    items_sorted = sorted(items, key=lambda x: x["priority"], reverse=True)

    buckets = {}
    for idx, item in enumerate(items_sorted):
        key = _bucket_key(item["title"])
        buckets.setdefault(key, []).append(idx)

    removed = set()
    progress_count = 0
    diff_source_count = 0
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
                            # v6.0.2: 进展豁免检查
                            is_pg, pg_reason = _is_progress_update(
                                items_sorted[i]["title"], items_sorted[j]["title"])
                            if is_pg:
                                # 进展报道：保留，标题加[进展]标签
                                items_sorted[j]["title"] = "[进展] " + items_sorted[j]["title"]
                                progress_count += 1
                                continue
                            # v6.0.2: 不同来源豁免检查
                            src_i = items_sorted[i].get("source", "")
                            src_j = items_sorted[j].get("source", "")
                            if KEEP_DIFFERENT_SOURCE and src_i and src_j and src_i != src_j:
                                # 不同来源：保留，标题加[不同来源]标签
                                items_sorted[j]["title"] = "[不同来源] " + items_sorted[j]["title"]
                                diff_source_count += 1
                                continue
                            removed.add(j)

    if progress_count:
        phase_log(f"[DEDUP] 进展豁免保留: {progress_count}篇")
    if diff_source_count:
        phase_log(f"[DEDUP] 不同来源保留: {diff_source_count}篇")
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

    # FIX: v4.7.3 - 未来日期过滤：published > now + max_future_days 的条目视为异常，跳过
    # v6.0.1: max_future_days 从参数区块读取（ODH_MAX_FUTURE_DAYS），默认3天
    max_future_days = MAX_FUTURE_DAYS
    future_cutoff = datetime.now(timezone.utc) + timedelta(days=max_future_days)
    before_future = len(unique_items)
    future_filtered = []
    for item in unique_items:
        pt = parse_published_time(item.get("published", ""))
        if pt is None:
            future_filtered.append(item)  # 无法解析时间的保守保留
        else:
            if pt.tzinfo is None:
                pt = pt.replace(tzinfo=timezone.utc)
            if pt <= future_cutoff:
                future_filtered.append(item)
    unique_items = future_filtered
    removed_by_future = before_future - len(unique_items)
    if removed_by_future > 0:
        print(f"  After future filter (+{max_future_days}d): {before_future} → {len(unique_items)} (-{removed_by_future})")

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
    v6.0: 环境变量覆盖 when/num — 支持 OVERSEAS_WHEN_DAYS / OVERSEAS_NUM
    
    1. 搜索模式（默认）：query非空 → /rss/search?q={query}
       - num: 返回文章数，最大100，默认100
       - when: 时间过滤，默认"7d"（7天窗口），可选"24h"/"1h"/None
       
    2. 专题模式：topic非空 → /rss/headlines/section/topic/{topic}
       - Topic是Google编辑精选，num上限30，不支持when
       - 已知Topic: WORLD / NATION / BUSINESS / TECHNOLOGY / ENTERTAINMENT / SCIENCE / SPORTS / HEALTH
    """
    import urllib.parse
    
    # v6.0: 环境变量覆盖（用于incremental/backfill模式动态调整采集窗口）
    env_when = os.environ.get("OVERSEAS_WHEN_DAYS")
    if env_when:
        when = env_when
    env_num = os.environ.get("OVERSEAS_NUM")
    if env_num:
        num = int(env_num)
    
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


# ============================================================
# v6.0: 持久化去重索引 (SeenIndex)
# ============================================================

def _extract_numbers(text):
    """从文本中提取所有数字（含小数），用于进展豁免的数字变化检测"""
    return [float(m) for m in re.findall(r'\d+\.?\d*', text)]


def _has_progress_keywords(title):
    """检查标题是否包含进展关键词（中文子串+英文词边界）"""
    t_lower = title.lower()
    for kw in _PROGRESS_KEYWORDS_CN:
        if kw in t_lower:
            return True
    if _PROGRESS_EN_PATTERN.search(title):
        return True
    return False


def _is_progress_update(title_old, title_new):
    """判断 title_new 是否为 title_old 的进展报道（而非重复）
    条件（满足任一即视为进展）:
      1. 数字变化 ≥20%：两标题提取数字，若新标题某数字相对旧标题对应数字变化≥20%
      2. 进展关键词：新标题包含进展关键词但旧标题不包含
    返回: (is_progress, reason) — reason用于日志/标签
    """
    # 条件2: 进展关键词
    if _has_progress_keywords(title_new) and not _has_progress_keywords(title_old):
        return True, "keyword"
    # 条件1: 数字变化 ≥20%
    nums_old = _extract_numbers(title_old)
    nums_new = _extract_numbers(title_new)
    if nums_old and nums_new:
        # 对每个新数字，检查是否相对旧数字变化≥20%
        for nv in nums_new:
            for ov in nums_old:
                if ov != 0 and abs(nv - ov) / abs(ov) >= 0.2:
                    return True, "number_change"
                elif ov == 0 and nv != 0:
                    return True, "number_change"
    return False, ""


def normalize_title_for_dedup(title):
    """去重用标题归一化：小写 + 去标点 + 压缩空格
    [校准待办] 实现未用真实数据验证误杀率/漏杀率，待backfill完成后用30天离线数据校准。
    可能的问题：短标题(<=3词)经归一化后容易误杀；某些标点有语义(如连字符)被误去。
    """
    if not title:
        return ""
    t = title.lower()
    t = re.sub(r'[^\w\s]', '', t)  # 去除标点
    t = re.sub(r'\s+', ' ', t).strip()  # 压缩空格
    return t


class SeenIndex:
    """
    持久化去重索引 — 支持跨run去重和补漏。
    
    去重策略（2层，仅同源去重，跨源不去重）：
      Layer 1: canonical_url hash — 同源同文重发
      Layer 2: source + normalized_title hash — 同源改题重发
    
    存储格式 (seen_index.json):
      {
        "version": 1,
        "last_fetch_date": "2026-06-14",
        "daily_stats": {"2026-06-14": {"added": 823, "deduped": 312}},
        "entries": {"<hash>": {"first_seen": "2026-06-01", "source": "reuters"}, ...}
      }
    """
    
    # ── 冷备份配置 ──
    _BACKUP_DIR_NAME = "backup"   # 相对于 seen_index.json 所在目录
    _BACKUP_FILENAME = "seen_index_backup.json"
    _MIN_HEALTHY_ENTRIES = 1000   # 成熟索引条目下限（正常≥30K）
    
    def __init__(self):
        self.version = 1
        self.last_fetch_date = None
        self.daily_stats = {}
        self.entries = {}
    
    # ── 冷备份路径 ──
    @staticmethod
    def _backup_path(main_path):
        """返回备份文件路径：scripts/backup/seen_index_backup.json"""
        backup_dir = os.path.join(os.path.dirname(main_path), SeenIndex._BACKUP_DIR_NAME)
        os.makedirs(backup_dir, exist_ok=True)
        return os.path.join(backup_dir, SeenIndex._BACKUP_FILENAME)
    
    # ── 校验索引健康度 ──
    def _validate(self, label=""):
        """校验索引数据完整性，返回 (ok, reason)"""
        n = len(self.entries)
        if n < self._MIN_HEALTHY_ENTRIES:
            return False, f"entries={n} < {self._MIN_HEALTHY_ENTRIES}"
        if not isinstance(self.entries, dict):
            return False, "entries is not dict"
        return True, ""
    
    @classmethod
    def load(cls, path):
        """从JSON文件加载索引，带校验+冷备份恢复"""
        idx = cls._load_raw(path)
        if idx is None:
            # 主文件不可用 → 尝试备份恢复
            bk_path = cls._backup_path(path)
            phase_log(f"[SEEN_INDEX] Main file unavailable, trying backup: {bk_path}")
            idx = cls._load_raw(bk_path)
            if idx is not None:
                phase_log(f"[SEEN_INDEX] Recovered from backup: {len(idx.entries)} entries")
            else:
                phase_log(f"[SEEN_INDEX] No backup available, starting fresh")
                return cls()
        
        # 健康度校验
        ok, reason = idx._validate("main")
        if ok:
            phase_log(f"[SEEN_INDEX] Loaded: {len(idx.entries)} entries, last_fetch={idx.last_fetch_date}")
            return idx
        
        phase_log(f"[SEEN_INDEX] Main index unhealthy ({reason}), trying backup")
        bk_path = cls._backup_path(path)
        bk_idx = cls._load_raw(bk_path)
        if bk_idx is not None:
            bk_ok, bk_reason = bk_idx._validate("backup")
            if bk_ok:
                phase_log(f"[SEEN_INDEX] Recovered from backup: {len(bk_idx.entries)} entries")
                return bk_idx
            else:
                phase_log(f"[SEEN_INDEX] Backup also unhealthy ({bk_reason})")
        
        # 主+备都不可用 → 返回空索引用户将感知增量退化为全量
        phase_log(f"[SEEN_INDEX] WARNING: Both main and backup failed validation, starting fresh (incremental→full mode)")
        return cls()
    
    @classmethod
    def _load_raw(cls, path):
        """原始加载，不校验，返回 cls() 实例或 None"""
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            idx = cls()
            idx.version = data.get("version", 1)
            idx.last_fetch_date = data.get("last_fetch_date")
            idx.daily_stats = data.get("daily_stats", {})
            idx.entries = data.get("entries", {})
            return idx
        except (json.JSONDecodeError, OSError) as e:
            phase_log(f"[SEEN_INDEX] Raw load failed ({path}): {e}")
            return None
    
    def save(self, path):
        """保存索引到JSON文件，同时写冷备份"""
        data = {
            "version": self.version,
            "last_fetch_date": self.last_fetch_date,
            "daily_stats": self.daily_stats,
            "entries": self.entries,
        }
        # 原子写入主文件
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp_path, path)
        phase_log(f"[SEEN_INDEX] Saved: {len(self.entries)} entries, last_fetch={self.last_fetch_date}")
        
        # 写冷备份（覆盖式，保留1份）
        try:
            bk_path = self._backup_path(path)
            bk_tmp = bk_path + ".tmp"
            with open(bk_tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(bk_tmp, bk_path)
            phase_log(f"[SEEN_INDEX] Backup saved: {bk_path}")
        except OSError as e:
            phase_log(f"[SEEN_INDEX] Backup save failed (non-fatal): {e}")
    
    def _make_key_url(self, article):
        """Layer 1: URL hash — canonical_url优先，否则link"""
        url = article.get("canonical_url") or article.get("link", "")
        if not url:
            return None
        return hashlib.md5(url.encode()).hexdigest()
    
    def _make_key_title(self, article):
        """Layer 2: source + normalized_title hash"""
        source = article.get("source", "unknown")
        title = normalize_title_for_dedup(article.get("title", ""))
        if not title:
            return None
        raw = f"{source}|{title}"
        return hashlib.md5(raw.encode()).hexdigest()
    
    def is_seen(self, article):
        """检查文章是否已在索引中（2层检查）"""
        key1 = self._make_key_url(article)
        if key1 and key1 in self.entries:
            return True
        key2 = self._make_key_title(article)
        if key2 and key2 in self.entries:
            return True
        return False
    
    def add(self, article, date_str=None):
        """将文章加入索引（同时写入2个key）"""
        if date_str is None:
            date_str = self.last_fetch_date or datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
        source = article.get("source", "unknown")
        key1 = self._make_key_url(article)
        if key1 and key1 not in self.entries:
            self.entries[key1] = {"first_seen": date_str, "source": source}
        key2 = self._make_key_title(article)
        if key2 and key2 not in self.entries:
            self.entries[key2] = {"first_seen": date_str, "source": source}
    
    def update_stats(self, date_str, added, deduped):
        """更新每日统计和last_fetch_date"""
        self.daily_stats[date_str] = {"added": added, "deduped": deduped}
        self.last_fetch_date = date_str
    
    def calc_when_days(self):
        """计算应采集的天数窗口（基于last_fetch_date补漏）"""
        if not self.last_fetch_date:
            return 30  # 首次运行：回填30天
        try:
            last = datetime.strptime(self.last_fetch_date, "%Y-%m-%d")
            today = datetime.now(BEIJING_TZ).date()
            gap = (today - last.date()).days
            return max(1, gap + 1)  # 至少1天，+1包含今天
        except ValueError:
            return 30
    
    def prune_old_entries(self, max_age_days=None):
        """清理超过max_age_days的旧条目，防止索引无限膨胀
        v6.0.1: 默认值从参数区块读取（ODH_PRUNE_AGE_DAYS），须>=本地数据保留期
        """
        if max_age_days is None:
            max_age_days = PRUNE_AGE_DAYS
        cutoff = (datetime.now(BEIJING_TZ) - timedelta(days=max_age_days)).strftime("%Y-%m-%d")
        to_remove = [k for k, v in self.entries.items() if v.get("first_seen", "") < cutoff]
        for k in to_remove:
            del self.entries[k]
        if to_remove:
            phase_log(f"[SEEN_INDEX] Pruned {len(to_remove)} entries older than {max_age_days} days")
        return len(to_remove)
