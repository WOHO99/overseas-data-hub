#!/usr/bin/env python3
"""
fetch_all.py v6.0 — 增量采集架构 (手动触发 + 补漏 + 去重优先)
v4.7.1: 回滚+可观测性增强
v4.7.2: Playwright medium采样测试 → 数据证明medium全量需122min
v5.0: Split-Job架构 — 将pipeline拆为4个独立Job:
  - collect: 18模块RSS采集+去重
  - pw-high: Playwright HIGH only (~12min)
  - pw-medium: Playwright MEDIUM only (~122min, 与pw-high并行)
  - finalize: 合并PW结果+full_text+beijing+dedup+index
v6.0: 增量采集架构 — 手动触发+补漏+SeenIndex去重
  - incremental: 补漏模式，根据last_fetch_date自动计算when_days
  - backfill: 首次回填，30天窗口
  - 核心变更: dedup vs seen_index → 仅对新增条目做Playwright+full_text
  - 保留 full/collect/pw-high/pw-medium/finalize 作为兼容回退

用法: python fetch_all.py [--mode incremental|backfill|full|collect|pw-high|pw-medium|finalize]
  incremental = 日常补漏（默认）
  backfill = 首次历史回填
  full = v4.7.1单Job模式(兼容回退)
"""

import json
import os
import sys
import asyncio
import time
import re
import hashlib
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 确保common.py可导入
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(SCRIPT_DIR, "modules"))

# v4.7.1: 可观测性 — 从common导入phase_log
from common import phase_log

# v6.0.1: 从common导入可配置参数（消除幻觉硬编码）
from common import (
    CIRCUIT_BREAKER_THRESHOLD,
    DEDUP_TITLE_THRESHOLD,
    DEDUP_TITLE_HOURS,
    MAX_FUTURE_DAYS,
    PRUNE_AGE_DAYS,
    SIGNAL_MIN_BASELINE,
    PLAYWRIGHT_WAIT_MIN,
    PLAYWRIGHT_WAIT_MAX,
    get_source_tier,
    get_source_coefficient,
    should_skip_fulltext,
)

# v6.0: 北京时间时区
BEIJING_TZ = timezone(timedelta(hours=8))

# v6.0.3: 辅助函数
def _is_gnews_link(link):
    """判定URL是否为Google News链接"""
    return bool(link and "news.google.com" in link)

# v6.0.4: 付费墙源白名单 — 这些源full_text成功率为0%，直接标记unavailable避免无效请求
# 分类: 硬付费墙(paywall) / 反爬拦截(anti-bot) / 需登录(login-required)
PAYWALL_SOURCES = frozenset([
    # --- 原6个 (v6.0.3) ---
    "WSJ World", "FT Home", "Le Monde",
    "SCMP Tech", "SCMP Economy", "CNN Business",
    # --- v6.0.4新增: 硬付费墙 ---
    "WSJ Markets", "WSJ Tech", "WSJ Opinion",              # Dow Jones全系
    "FT Alphaville", "FT Markets",                          # Financial Times全系
    "Bloomberg Markets Direct", "Bloomberg Markets",        # Bloomberg
    "Economist Business",                                   # The Economist
    "The Atlantic",                                         # metered paywall
    "Nikkei Asia",                                          # hard paywall
    "Foreign Affairs",                                      # paywall
    # --- v6.0.4新增: 反爬/需登录 ---
    "NYT Business", "NYT World",                            # NYT metered+anti-bot
    "WaPo World",                                           # WaPo metered
    "SCMP Economy",  # 已在上面, 保留去重安全
    # --- v6.0.4新增: GNews解析后付费墙(0%成功率源) ---
    "South China Morning Post",
    "Haaretz",
    "Carbon Pulse",
])

MODULE_REGISTRY = [
    {"module": "global_business", "output": "global_business.json", "core": True},
    {"module": "finance_global", "output": "finance_global.json", "core": False},
    {"module": "tech_industry", "output": "tech_industry.json", "core": False},
    {"module": "energy_commodities", "output": "energy_commodities.json", "core": False},
    {"module": "geopolitics_risk", "output": "geopolitics_risk.json", "core": False},
    {"module": "esg_sustainability", "output": "esg_sustainability.json", "core": False},
    {"module": "region_se_asia", "output": "se_asia.json", "core": False},
    {"module": "region_south_asia", "output": "south_asia.json", "core": False},
    {"module": "region_middle_east", "output": "middle_east.json", "core": False},
    {"module": "region_latin_america", "output": "latam.json", "core": False},
    {"module": "region_africa", "output": "africa.json", "core": False},
    {"module": "region_europe", "output": "europe.json", "core": False},
    {"module": "region_cis", "output": "cis.json", "core": False},
    {"module": "region_east_asia", "output": "east_asia.json", "core": False},
    {"module": "cross_border_ecommerce", "output": "cross_border_ecommerce.json", "core": False},
    {"module": "trade_import_export", "output": "trade_import_export.json", "core": False},
    {"module": "global_risk", "output": "global_risk.json", "core": False},
    {"module": "chinese_firms_overseas", "output": "chinese_firms_overseas.json", "core": False},
]

MAX_CONCURRENT = 3
MODULE_TIMEOUT = 120  # 2分钟硬超时（v4.4: 从300s缩短，避免超时模块拖垮整体）
MAX_RETRIES = 1       # 失败重试1次


async def run_module_subprocess(mod_name, output_file, is_core, timeout=MODULE_TIMEOUT):
    """以subprocess运行单个模块，硬超时SIGKILL"""
    script_path = os.path.join(SCRIPT_DIR, "modules", f"{mod_name}.py")
    start = time.time()
    
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-u", script_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=SCRIPT_DIR,
    )
    
    try:
        stdout_data, stderr_data = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        elapsed = time.time() - start
        success = proc.returncode == 0 and os.path.exists(os.path.join(SCRIPT_DIR, output_file))
        
        # 打印模块输出（截断防刷屏）
        if stdout_data:
            out_text = stdout_data.decode("utf-8", errors="replace")
            # 只打印关键行（MODULE DONE / FAIL / RATE_LIMITED 等）
            for line in out_text.splitlines():
                if any(kw in line for kw in ["MODULE DONE", "MODULE:", "After link", "After title",
                                               "RATE_LIMITED", "FAIL", "Category:", "Elapsed",
                                               "DIAG", "Error", "Traceback", "import"]):
                    print(f"  {line}")
        
        # v6.0.3: 始终打印stderr（调试超时问题）
        if stderr_data:
            err_text = stderr_data.decode("utf-8", errors="replace")[-1000:]
            print(f"  [STDERR] {err_text}")
        
        return {
            "module": mod_name,
            "output": output_file,
            "success": success,
            "elapsed": round(elapsed, 1),
            "timed_out": False,
            "is_core": is_core,
        }
        
    except asyncio.TimeoutError:
        # OS级别杀进程
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        await proc.wait()
        elapsed = time.time() - start
        print(f"  [TIMEOUT] {mod_name} killed after {timeout}s (SIGKILL)")
        
        return {
            "module": mod_name,
            "output": output_file,
            "success": False,
            "elapsed": round(elapsed, 1),
            "timed_out": True,
            "is_core": is_core,
        }
    except Exception as e:
        elapsed = time.time() - start
        print(f"  [ERROR] {mod_name}: {e}")
        
        return {
            "module": mod_name,
            "output": output_file,
            "success": False,
            "elapsed": round(elapsed, 1),
            "timed_out": False,
            "is_core": is_core,
        }


async def run_all_modules_concurrent():
    """3个模块并发执行，失败重试1次"""
    start_all = time.time()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    results = {}
    fail_counts = load_fail_counts()
    new_fail_counts = {}
    
    async def _run_with_sem(entry, attempt=0):
        mod_name = entry["module"]
        async with semaphore:
            suffix = f" (retry {attempt})" if attempt > 0 else ""
            total_so_far = time.time() - start_all
            print(f"\n{'#'*70}")
            print(f"# Module: {mod_name}{' [CORE]' if entry.get('core') else ''}{suffix}")
            print(f"# Elapsed: {total_so_far:.0f}s ({total_so_far/60:.1f}min)")
            print(f"{'#'*70}")
            
            result = await run_module_subprocess(
                mod_name, entry["output"], entry.get("core", False)
            )
            
            if result["success"]:
                print(f"[OK] {mod_name} -> {entry['output']} ({result['elapsed']}s)")
            else:
                reason = "TIMEOUT" if result["timed_out"] else "FAIL"
                print(f"[{reason}] {mod_name} ({result['elapsed']}s)")
            
            return result
    
    # 第一轮：所有模块
    tasks = [_run_with_sem(entry) for entry in MODULE_REGISTRY]
    first_results = await asyncio.gather(*tasks)
    
    # 重试失败模块
    failed = [r for r in first_results if not r["success"]]
    if failed:
        print(f"\n{'='*70}")
        print(f"Retrying {len(failed)} failed modules...")
        print(f"{'='*70}")
        retry_tasks = []
        for r in failed:
            entry = next(e for e in MODULE_REGISTRY if e["module"] == r["module"])
            retry_tasks.append(_run_with_sem(entry, attempt=1))
        retry_results = await asyncio.gather(*retry_tasks)
    else:
        retry_results = []
    
    # 汇总结果
    all_results = {}
    for r in first_results:
        all_results[r["module"]] = r
    
    for r in retry_results:
        # 重试成功则覆盖
        if r["success"]:
            all_results[r["module"]] = r
    
    # 统计
    for entry in MODULE_REGISTRY:
        mod_name = entry["module"]
        r = all_results[mod_name]
        if r["success"]:
            new_fail_counts[mod_name] = 0
        else:
            prev = fail_counts.get(mod_name, 0)
            new_fail_counts[mod_name] = prev + 1
            consecutive = new_fail_counts[mod_name]
            if entry.get("core") and consecutive >= 3:
                print(f"\n{'!'*70}")
                print(f"!!! CRITICAL: Core module {mod_name} failed {consecutive} days in a row!")
                print(f"{'!'*70}")
    
    save_fail_counts(new_fail_counts)
    
    # 打印汇总表
    elapsed = time.time() - start_all
    print(f"\n{'='*70}")
    print(f"ALL MODULES DONE in {elapsed:.0f}s ({elapsed/60:.1f}min)")
    print(f"{'='*70}")
    ok_count = sum(1 for r in all_results.values() if r["success"])
    fail_count = len(all_results) - ok_count
    timeout_count = sum(1 for r in all_results.values() if r.get("timed_out"))
    print(f"  OK: {ok_count}/{len(all_results)}, FAIL: {fail_count}, TIMEOUT: {timeout_count}")
    for r in all_results.values():
        status = "OK" if r["success"] else ("TIMEOUT" if r.get("timed_out") else "FAIL")
        print(f"  {r['module']}: {status} ({r['elapsed']}s)")
    
    results = {r["output"]: r["success"] for r in all_results.values()}
    return results


def load_fail_counts():
    path = os.path.join(SCRIPT_DIR, "fail_counts.json")
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_fail_counts(counts):
    path = os.path.join(SCRIPT_DIR, "fail_counts.json")
    with open(path, "w") as f:
        json.dump(counts, f)


# ============================================================================
# v5.0: Split-Job辅助函数
# ============================================================================

def load_articles_from_modules():
    """从per-module JSON文件加载所有文章，返回 {filename: [article_dicts]}"""
    articles_by_file = {}
    for entry in MODULE_REGISTRY:
        output_file = entry["output"]
        full_path = os.path.join(SCRIPT_DIR, output_file)
        if not os.path.exists(full_path):
            continue
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            articles_by_file[output_file] = data.get("articles", [])
        except json.JSONDecodeError:
            continue
    total = sum(len(v) for v in articles_by_file.values())
    phase_log(f"  Loaded {total} articles from {len(articles_by_file)} module files")
    return articles_by_file


def save_pw_map(articles_by_file, pw_map_path):
    """将Playwright解析结果保存为 link→{canonical_url, full_text} 映射"""
    from common import atomic_write_json
    pw_map = {}
    for filename, articles in articles_by_file.items():
        for article in articles:
            updates = {}
            if article.get("canonical_url"):
                updates["canonical_url"] = article["canonical_url"]
            if article.get("full_text"):
                updates["full_text"] = article["full_text"]
            if updates:
                pw_map[article["link"]] = updates
    atomic_write_json(pw_map, pw_map_path)
    phase_log(f"  Saved PW map: {len(pw_map)} entries to {os.path.basename(pw_map_path)}")
    return len(pw_map)


def apply_pw_map(articles_by_file, *pw_map_paths):
    """将PW映射应用到文章列表(原地修改)"""
    from common import atomic_write_json
    combined_map = {}
    for path in pw_map_paths:
        if not os.path.exists(path):
            phase_log(f"  [WARN] PW map not found: {path}")
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                pw_map = json.load(f)
            combined_map.update(pw_map)
        except (json.JSONDecodeError, OSError) as e:
            phase_log(f"  [WARN] Failed to load PW map {path}: {e}")

    applied = 0
    for filename, articles in articles_by_file.items():
        for article in articles:
            link = article.get("link", "")
            if link in combined_map:
                updates = combined_map[link]
                if "canonical_url" in updates and not article.get("canonical_url"):
                    article["canonical_url"] = updates["canonical_url"]
                if "full_text" in updates and not article.get("full_text"):
                    article["full_text"] = updates["full_text"]
                applied += 1

    phase_log(f"  Applied {applied} PW map updates from {len(combined_map)} map entries")
    return applied


def write_back_articles(articles_by_file):
    """将修改后的文章写回per-module JSON文件"""
    from common import atomic_write_json
    written = 0
    for entry in MODULE_REGISTRY:
        output_file = entry["output"]
        if output_file not in articles_by_file:
            continue
        full_path = os.path.join(SCRIPT_DIR, output_file)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["articles"] = articles_by_file[output_file]
            atomic_write_json(data, full_path)
            written += 1
        except (json.JSONDecodeError, OSError) as e:
            phase_log(f"  [WARN] Failed to update {output_file}: {e}")
    phase_log(f"  Written back to {written} module files")


def global_dedup():
    """v4.2: Bucket分桶 + RapidFuzz 去重，替代 O(n²) difflib
    v4.3: P4-7 增量状态标记 — 对去重后文章标记 new/continuing
    """
    from common import link_hash, title_similarity, parse_published_time, load_last_state, save_last_state, tag_incremental

    # 加载上一轮增量状态
    prev_state = load_last_state(SCRIPT_DIR)

    seen = {}
    module_outputs = {}
    for entry in MODULE_REGISTRY:
        output_file = entry["output"]
        full_path = os.path.join(SCRIPT_DIR, output_file)
        if not os.path.exists(full_path):
            continue
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            continue
        module_outputs[output_file] = data
        for article in data.get("articles", []):
            h = link_hash(article["link"])
            if h in seen:
                existing = seen[h]
                if article["priority"] > existing["item"]["priority"]:
                    existing["item"] = article
                if data["module"] not in existing["modules"]:
                    existing["modules"].append(data["module"])
            else:
                seen[h] = {"item": article, "modules": [data["module"]]}

    items_list = list(seen.values())
    items_list.sort(key=lambda x: x["item"]["priority"], reverse=True)

    # v4.4: 核心实体词分桶 — 替代"前3字符"，解决快讯前缀/冠词导致的假阴性
    from common import _bucket_key

    buckets = {}
    for idx, entry in enumerate(items_list):
        key = _bucket_key(entry["item"]["title"])
        buckets.setdefault(key, []).append(idx)

    total_comparisons = 0
    removed_indices = set()
    for bucket_indices in buckets.values():
        for i_pos in range(len(bucket_indices)):
            i = bucket_indices[i_pos]
            if i in removed_indices:
                continue
            for j_pos in range(i_pos + 1, len(bucket_indices)):
                j = bucket_indices[j_pos]
                if j in removed_indices:
                    continue
                total_comparisons += 1
                sim = title_similarity(items_list[i]["item"]["title"],
                                       items_list[j]["item"]["title"])
                if sim >= 0.85:
                    t1 = parse_published_time(items_list[i]["item"]["published"])
                    t2 = parse_published_time(items_list[j]["item"]["published"])
                    # Normalize both to UTC naive to avoid offset-aware/naive mismatch
                    if t1 and t1.tzinfo is not None:
                        t1 = t1.astimezone(timezone.utc).replace(tzinfo=None)
                    if t2 and t2.tzinfo is not None:
                        t2 = t2.astimezone(timezone.utc).replace(tzinfo=None)
                    if t1 and t2 and abs((t1 - t2).total_seconds()) < 86400:
                        removed_indices.add(j)

    kept = [items_list[i] for i in range(len(items_list)) if i not in removed_indices]
    print(f"  Global dedup: {len(items_list)} -> {len(kept)} (removed {len(removed_indices)}, "
          f"comparisons: {total_comparisons} vs n²/2={len(items_list)*(len(items_list)-1)//2})")

    # FIX: v4.7.3 - 未来日期过滤：published > now + max_future_days 的条目视为异常，跳过
    # v6.0.1: max_future_days 从参数区块读取（ODH_MAX_FUTURE_DAYS）
    max_future_days = MAX_FUTURE_DAYS
    future_cutoff = datetime.now(timezone.utc) + timedelta(days=max_future_days)
    before_future = len(kept)
    kept_future = []
    for entry in kept:
        pt = parse_published_time(entry["item"].get("published", ""))
        if pt is None:
            kept_future.append(entry)  # 无法解析时间的保守保留
        else:
            if pt.tzinfo is None:
                pt = pt.replace(tzinfo=timezone.utc)
            if pt <= future_cutoff:
                kept_future.append(entry)
    kept = kept_future
    removed_by_future = before_future - len(kept)
    if removed_by_future > 0:
        print(f"  Future date filter (+{max_future_days}d): {before_future} → {len(kept)} (-{removed_by_future})")

    final_seen = {}
    for entry in kept:
        h = link_hash(entry["item"]["link"])
        final_seen[h] = entry

    # P4-7: 增量标记 — 对全局去重后的文章标记 new/continuing
    all_hashes_prev = set()
    for mod_name, hash_list in prev_state.items():
        if isinstance(hash_list, list):
            all_hashes_prev.update(hash_list)
        # 兼容旧格式（dict with hash:status）
        elif isinstance(hash_list, dict):
            all_hashes_prev.update(hash_list.keys())

    new_count = 0
    cont_count = 0
    for h, entry in final_seen.items():
        if h in all_hashes_prev:
            entry["item"]["_incremental"] = "continuing"
            cont_count += 1
        else:
            entry["item"]["_incremental"] = "new"
            new_count += 1
    print(f"  Incremental: {new_count} new, {cont_count} continuing")

    # 保存新一轮增量状态
    new_state = {}
    for entry in MODULE_REGISTRY:
        mod_name = entry["module"]
        output_file = entry["output"]
        if output_file in module_outputs:
            mod_hashes = []
            for article in module_outputs[output_file].get("articles", []):
                mod_hashes.append(link_hash(article["link"]))
            new_state[mod_name] = mod_hashes
    save_last_state(SCRIPT_DIR, new_state)
    print(f"  Saved last_state.json ({len(new_state)} modules)")

    # v6.0.4.1: 跨模块link去重 — 从module_outputs中移除不在final_seen中的文章
    # 根因: 同一篇文章(同一link)出现在多个模块时, global_dedup的seen只保留1份,
    # 但module_outputs各模块仍保留原稿, 导致模块JSON之间有重复
    final_links = set(final_seen.keys())
    deduped_modules = 0
    deduped_articles = 0
    for output_file, data in module_outputs.items():
        if "articles" not in data:
            continue
        before = len(data["articles"])
        data["articles"] = [
            a for a in data["articles"]
            if link_hash(a["link"]) in final_links
        ]
        removed = before - len(data["articles"])
        if removed > 0:
            deduped_modules += 1
            deduped_articles += removed
    if deduped_articles > 0:
        print(f"  Cross-module dedup: removed {deduped_articles} duplicate articles from {deduped_modules} modules")

    return final_seen, module_outputs


def build_index(seen, module_outputs):
    from common import atomic_write_json, link_hash, load_source_authority, load_source_tier_override

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    all_articles = list(seen.values())
    total_global = len(all_articles)
    high_global = len([a for a in all_articles if a["item"]["relevance"] == "high"])
    medium_global = len([a for a in all_articles if a["item"]["relevance"] == "medium"])
    
    # v6.0.3: 加载权威度映射(用于source_tier)
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    authority_map = load_source_authority(config_dir)
    # v6.0.8: 加载domain→tier override映射
    tier_override = load_source_tier_override(config_dir)

    # P4-1: 源指纹计算 — 只从24h窗口文章计算
    from common import parse_published_time
    cutoff_24h = now - timedelta(hours=24)
    source_fingerprint = {}
    for output_file, data in module_outputs.items():
        mod_name = data.get("module", output_file)
        source_articles = {}  # tag -> [link_hashes]
        for article in data.get("articles", []):
            pt = parse_published_time(article.get("published", ""))
            if pt is not None:
                if pt.tzinfo is None:
                    pt = pt.replace(tzinfo=timezone.utc)
                if pt < cutoff_24h:
                    continue  # 仅24h窗口
            tag = article.get("source", "unknown")
            h = link_hash(article["link"])
            source_articles.setdefault(tag, []).append(h)
        for tag, hashes in source_articles.items():
            hashes.sort()
            fp = hashlib.md5(",".join(hashes).encode()).hexdigest()[:12]
            source_fingerprint[tag] = {
                "fingerprint": fp,
                "article_count": len(hashes),
                "module": mod_name,
            }

    # 对比上一轮指纹
    prev_fp_path = os.path.join(SCRIPT_DIR, "source_fingerprint.json")
    prev_fingerprints = {}
    if os.path.exists(prev_fp_path):
        try:
            with open(prev_fp_path, "r", encoding="utf-8") as f:
                prev_fp_data = json.load(f)
                for tag, info in prev_fp_data.get("sources", {}).items():
                    prev_fingerprints[tag] = info.get("fingerprint", "")
        except (json.JSONDecodeError, OSError):
            pass

    fp_changes = {"unchanged": 0, "changed": 0, "new_source": 0}
    for tag, info in source_fingerprint.items():
        if tag in prev_fingerprints:
            if info["fingerprint"] == prev_fingerprints[tag]:
                info["status"] = "unchanged"
                fp_changes["unchanged"] += 1
            else:
                info["status"] = "changed"
                fp_changes["changed"] += 1
        else:
            info["status"] = "new_source"
            fp_changes["new_source"] += 1

    # 保存本轮指纹
    fp_output = {
        "version": "1.0",
        "updated": now.isoformat(),
        "fetch_date_utc": now.strftime("%Y-%m-%d"),
        "window": "24h",
        "summary": fp_changes,
        "sources": source_fingerprint,
    }
    atomic_write_json(fp_output, prev_fp_path)
    print(f"  Source fingerprint: {fp_changes['unchanged']} unchanged, "
          f"{fp_changes['changed']} changed, {fp_changes['new_source']} new")

    # P4-8: 死源熔断器 — 连续X天零产出（排除rate_limited源）
    # v6.0.3: 运行次数退避替代时间退避
    #   - Pipeline是手动触发(workflow_dispatch)，非cron/daemon，时间退避无意义
    #   - 运行次数退避: 0→1→2→3→5次跳过，即连续0产出后第1次仍运行，之后递增跳过
    #   - 人工编辑sources_dead.json仍优先
    CIRCUIT_BREAKER_BACKOFF_RUNS = [0, 1, 2, 3, 5]  # 对应fail_count 1-5的跳过次数

    circuit_breaker_path = os.path.join(SCRIPT_DIR, "sources_dead.json")
    dead_history = {}
    if os.path.exists(circuit_breaker_path):
        try:
            with open(circuit_breaker_path, "r", encoding="utf-8") as f:
                dead_history = json.load(f)
        except (json.JSONDecodeError, OSError):
            dead_history = {}

    # 本轮各源产出计数
    source_output_count = {}
    for output_file, data in module_outputs.items():
        for article in data.get("articles", []):
            tag = article.get("source", "unknown")
            source_output_count[tag] = source_output_count.get(tag, 0) + 1

    # rate_limited源集合（本轮被429/503的源不算死源）
    rate_limited_sources = set()
    for output_file, data in module_outputs.items():
        if data.get("rate_limited_feeds", 0) > 0:
            # 从stats_by_category提取rate_limited源名
            for cat, cat_stats in data.get("stats_by_category", {}).items():
                rate_limited_sources.add(cat)

    # 更新死亡历史（含指数退避恢复）
    # v6.0.1: 从参数区块读取（ODH_CIRCUIT_BREAKER），默认3天
    CIRCUIT_BREAKER_THRESHOLD_VAL = CIRCUIT_BREAKER_THRESHOLD
    updated_dead = {}
    circuit_broken_sources = []
    recovered_sources = []
    all_tags = set(list(source_output_count.keys()) + list(dead_history.keys()))
    for tag in all_tags:
        count = source_output_count.get(tag, 0)
        prev = dead_history.get(tag, {})
        consecutive_zeros = prev.get("consecutive_zeros", 0)
        fail_count = prev.get("fail_count", 0)
        is_rate_limited = tag in rate_limited_sources
        status = "active"

        if count > 0:
            # 有产出：恢复 → 重置
            if consecutive_zeros >= CIRCUIT_BREAKER_THRESHOLD_VAL:
                # 从熔断状态恢复
                recovered_sources.append(tag)
                phase_log(f"[CIRCUIT_BREAKER] {tag} recovered after {fail_count} retries")
            consecutive_zeros = 0
            fail_count = 0
        elif not is_rate_limited:
            consecutive_zeros += 1
        # else: rate_limited源不累积consecutive_zeros

        if consecutive_zeros >= CIRCUIT_BREAKER_THRESHOLD_VAL:
            status = "circuit_breaker"
            circuit_broken_sources.append(tag)

            # v6.0.3: 运行次数退避
            fail_count += 1  # 每次熔断+1
            backoff_idx = min(fail_count - 1, len(CIRCUIT_BREAKER_BACKOFF_RUNS) - 1)
            next_retry_skip = CIRCUIT_BREAKER_BACKOFF_RUNS[backoff_idx]

            # 联动source_fingerprint：标记熔断状态
            if tag in source_fingerprint:
                source_fingerprint[tag]["status"] = "circuit_breaker"

        updated_dead[tag] = {
            "consecutive_zeros": consecutive_zeros,
            "status": status,
            "last_output_date": today_str if count > 0 else prev.get("last_output_date", ""),
            "fail_count": fail_count,
            "next_retry_skip": next_retry_skip if consecutive_zeros >= CIRCUIT_BREAKER_THRESHOLD_VAL else 0,
        }

    atomic_write_json(updated_dead, circuit_breaker_path)
    if circuit_broken_sources:
        print(f"  Circuit breaker: {len(circuit_broken_sources)} sources dead "
              f"(>= {CIRCUIT_BREAKER_THRESHOLD_VAL} days zero output)")
        for src in circuit_broken_sources[:10]:
            info = updated_dead[src]
            print(f"    - {src}: {info['consecutive_zeros']}d zero, fail_count={info['fail_count']}, "
                  f"skip_next={info.get('next_retry_skip', 0)} runs, last: {info.get('last_output_date', 'never')}")
    if recovered_sources:
        print(f"  Circuit breaker recovered: {len(recovered_sources)} sources")
        for src in recovered_sources[:10]:
            print(f"    + {src}")

    module_stats = {}
    for entry in MODULE_REGISTRY:
        output_file = entry["output"]
        if output_file in module_outputs:
            d = module_outputs[output_file]
            module_stats[entry["module"]] = {
                "output_file": output_file,
                "total": d["total"],
                "high": d["high_priority"],
                "medium": d["medium_priority"],
                "fail_feeds": d.get("fail_feeds", 0),
                "signal_alerts": d.get("signal_alerts", {}),
                "rate_limited_feeds": d.get("rate_limited_feeds", 0),
            }

    high_articles = []
    new_count_global = 0
    cont_count_global = 0
    # v6.0.3: content_status/fetch_capability/source_tier 统计
    content_status_counts = {"has_fulltext": 0, "fulltext_needs_retry": 0, "fulltext_unavailable": 0}
    fetch_capability_counts = {"direct_fetchable": 0, "gnews_resolved": 0, "gnews_unresolved": 0}
    tier_counts = {}
    for a in all_articles:
        item = a["item"]
        # --- v6.0.3: content_status ---
        full_text = item.get("full_text")
        is_gnews = _is_gnews_link(item.get("link", ""))
        has_canonical = bool(item.get("canonical_url"))
        source_name = item.get("source", "")
        if full_text:
            item["content_status"] = "has_fulltext"
            content_status_counts["has_fulltext"] += 1
        elif source_name in PAYWALL_SOURCES or should_skip_fulltext(source_name):
            item["content_status"] = "fulltext_unavailable"
            content_status_counts["fulltext_unavailable"] += 1
        elif is_gnews and has_canonical:
            item["content_status"] = "fulltext_needs_retry"
            content_status_counts["fulltext_needs_retry"] += 1
        else:
            item["content_status"] = "fulltext_unavailable"
            content_status_counts["fulltext_unavailable"] += 1
        # --- v6.0.3: fetch_capability ---
        if not is_gnews:
            item["fetch_capability"] = "direct_fetchable"
            fetch_capability_counts["direct_fetchable"] += 1
        elif has_canonical:
            item["fetch_capability"] = "gnews_resolved"
            fetch_capability_counts["gnews_resolved"] += 1
        else:
            item["fetch_capability"] = "gnews_unresolved"
            fetch_capability_counts["gnews_unresolved"] += 1
        # --- v6.0.3/v6.0.8: source_tier (优先domain lookup) ---
        tier = get_source_tier(item.get("source", ""), authority_map, tier_override, item.get("canonical_url"))
        item["source_tier"] = tier
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        # --- v6.0.3: auto_tags (可检索标签) ---
        tags = []
        cat = item.get("category", "")
        if cat:
            # 按+号拆分中文分类为独立标签
            for part in re.split(r'[+]', cat):
                part = part.strip()
                if part:
                    tags.append(part)
        tags.append(f"tier:{tier}")
        fc = item.get("fetch_capability", "")
        if fc:
            tags.append(f"fetch:{fc}")
        inc = item.get("_incremental", "")
        if inc:
            tags.append(f"status:{inc}")
        for sk in item.get("signal_keywords", []):
            tags.append(f"signal:{sk}")
        item["auto_tags"] = tags
        # --- high articles / incremental ---
        if item["relevance"] == "high":
            art = item.copy()
            art["matched_modules"] = a["modules"]
            high_articles.append(art)
        inc = item.get("_incremental", "")
        if inc == "new":
            new_count_global += 1
        elif inc == "continuing":
            cont_count_global += 1
    high_articles.sort(key=lambda x: x["priority"], reverse=True)

    global_signal_counts = {}
    for a in all_articles:
        for sk in a["item"].get("signal_keywords", []):
            global_signal_counts[sk] = global_signal_counts.get(sk, 0) + 1

    # P4-5: 信号动态基线 — max(7d_high, 3) 替代固定 >=5
    signal_baseline_path = os.path.join(SCRIPT_DIR, "signal_baseline.json")
    signal_history = {}
    if os.path.exists(signal_baseline_path):
        try:
            with open(signal_baseline_path, "r", encoding="utf-8") as f:
                signal_history = json.load(f)
        except (json.JSONDecodeError, OSError):
            signal_history = {}

    # 更新历史：保留最近7天
    for kw, count in global_signal_counts.items():
        if kw not in signal_history:
            signal_history[kw] = {}
        signal_history[kw][today_str] = count
    # 清理8天前数据
    cutoff_date = (now - timedelta(days=8)).strftime("%Y-%m-%d")
    for kw in list(signal_history.keys()):
        for d in list(signal_history[kw].keys()):
            if d < cutoff_date:
                del signal_history[kw][d]
        if not signal_history[kw]:
            del signal_history[kw]

    # 计算基线和告警（P1: 持续告警条件，防止"第一天告警后基线上移，后续天不再触发"）
    signal_summary_list = []
    signal_alerts = {}
    for kw, count in global_signal_counts.items():
        history = signal_history.get(kw, {})
        day_counts = [v for k, v in sorted(history.items()) if k != today_str]
        high_7d = max(day_counts) if day_counts else 0
        mean_7d = round(sum(day_counts) / len(day_counts), 1) if day_counts else 0
        baseline = max(high_7d, SIGNAL_MIN_BASELINE)

        # P1: 计算连续告警天数
        consecutive_alert_days = 0
        for d_str in sorted(history.keys(), reverse=True):
            if d_str == today_str:
                continue
            d_count = history[d_str]
            d_baseline = SIGNAL_MIN_BASELINE  # 历史天无法重算baseline，用参数区块最低基线
            if d_count >= d_baseline:
                consecutive_alert_days += 1
            else:
                break

        # P1: 触发条件 = 超基线 OR (持续告警条件: count>=3 AND 连续告警>=1 AND count >= 7d均值×1.5)
        spike_triggered = count > baseline
        sustained_triggered = (count >= SIGNAL_MIN_BASELINE and consecutive_alert_days >= 1 and count >= mean_7d * 1.5) if mean_7d > 0 else False
        triggered = spike_triggered or sustained_triggered
        status = "sustained" if (sustained_triggered and not spike_triggered) else ("spike" if spike_triggered else "normal")

        entry = {
            "keyword": kw,
            "today_count": count,
            "baseline": baseline,
            "high_7d": high_7d,
            "mean_7d": mean_7d,
            "consecutive_alert_days": consecutive_alert_days,
            "triggered": triggered,
            "status": status,
            "baseline_note": f"max(7d_high={high_7d}, {SIGNAL_MIN_BASELINE})={baseline}",
        }
        signal_summary_list.append(entry)
        if triggered:
            signal_alerts[kw] = count

    # 按today_count降序
    signal_summary_list.sort(key=lambda x: x["today_count"], reverse=True)

    # 保存历史
    atomic_write_json(signal_history, signal_baseline_path)

    # 保存signal_summary.json（推送到CDN）
    signal_summary_output = {
        "version": "1.1",
        "updated": now.isoformat(),
        "fetch_date_utc": today_str,
        "method": f"max(7d_high, {SIGNAL_MIN_BASELINE}) + sustained(mean_7d*1.5)",
        "signals": signal_summary_list,
    }
    from common import atomic_write_json as _awj  # already imported above
    _awj(signal_summary_output, os.path.join(SCRIPT_DIR, "signal_summary.json"))
    triggered_count = len(signal_alerts)
    print(f"  Signal baseline: {triggered_count} triggered, {len(global_signal_counts)} total signals")

    # v6.0.4: 源成功率排名 (full_text成功率 per source)
    source_ft_stats = {}  # {source: {total, has_fulltext}}
    for a in all_articles:
        src = a["item"].get("source", "unknown")
        if src not in source_ft_stats:
            source_ft_stats[src] = {"total": 0, "has_fulltext": 0}
        source_ft_stats[src]["total"] += 1
        if a["item"].get("full_text"):
            source_ft_stats[src]["has_fulltext"] += 1
    source_success_ranking = []
    for src, stats in sorted(source_ft_stats.items(), key=lambda x: x[1]["total"], reverse=True)[:30]:
        rate = stats["has_fulltext"] / stats["total"] if stats["total"] > 0 else 0
        source_success_ranking.append({
            "source": src, "total": stats["total"],
            "has_fulltext": stats["has_fulltext"], "success_rate": round(rate, 3)
        })
    # v6.0.4: 连续零产出源告警 (有文章但0% full_text且非付费墙)
    zero_ft_sources = [
        s for s in source_success_ranking
        if s["success_rate"] == 0 and s["total"] >= 5 and s["source"] not in PAYWALL_SOURCES
    ]

    # v6.0.8: Health check — 对比上轮数据，生成运行健康摘要
    prev_index_path = os.path.join(SCRIPT_DIR, "index.json")
    prev_index = {}
    if os.path.exists(prev_index_path):
        try:
            with open(prev_index_path, "r", encoding="utf-8") as f:
                prev_index = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    health_check = {
        "timestamp": now.isoformat(),
        "total_articles": total_global,
        "high_priority": high_global,
        "ft_success_rate": round(content_status_counts["has_fulltext"] / total_global, 3) if total_global > 0 else 0,
        "content_status": content_status_counts,
        "fetch_capability": fetch_capability_counts,
        "source_tier": tier_counts,
        "circuit_broken_count": len(circuit_broken_sources),
        "zero_ft_sources_count": len(zero_ft_sources),
    }
    # 对比上轮
    prev_total = prev_index.get("global_total", 0)
    prev_ft_rate = None
    prev_cs = prev_index.get("content_status_counts", {})
    prev_sum = sum(prev_cs.values())
    if prev_sum > 0:
        prev_ft_rate = prev_cs.get("has_fulltext", 0) / prev_sum
    health_check["prev_total_articles"] = prev_total
    health_check["delta_articles"] = total_global - prev_total if prev_total > 0 else None
    health_check["prev_ft_success_rate"] = round(prev_ft_rate, 3) if prev_ft_rate is not None else None
    # 模块级对比
    prev_modules = prev_index.get("modules", {})
    module_health = []
    for mod_name, mstat in module_stats.items():
        prev_mcount = prev_modules.get(mod_name, {}).get("article_count", 0)
        delta = mstat.get("article_count", 0) - prev_mcount
        module_health.append({
            "module": mod_name,
            "articles": mstat.get("article_count", 0),
            "prev_articles": prev_mcount,
            "delta": delta,
        })
    health_check["modules"] = module_health

    index = {
        "version": "6.0.8",
        "updated": now.isoformat(),
        "fetch_date_utc": now.strftime("%Y-%m-%d"),
        "global_total": total_global,
        "global_high": high_global,
        "global_medium": medium_global,
        "global_new": new_count_global,
        "global_continuing": cont_count_global,
        "global_signal_alerts": signal_alerts,
        "signal_baselines": {s["keyword"]: s["baseline"] for s in signal_summary_list[:20]},
        "source_fingerprint_summary": fp_changes,
        "circuit_breaker_count": len(circuit_broken_sources),
        "circuit_broken_sources": circuit_broken_sources[:20],
        "content_status_counts": content_status_counts,
        "fetch_capability_counts": fetch_capability_counts,
        "source_tier_counts": tier_counts,
        "source_success_ranking": source_success_ranking,
        "zero_fulltext_sources": zero_ft_sources,
        "health_check": health_check,
        "modules": module_stats,
        "high_priority_articles": high_articles[:100],
    }
    atomic_write_json(index, os.path.join(SCRIPT_DIR, "index.json"))
    return index


async def main_async():
    """v4.7.1单Job模式 — 保留作为full模式的兼容回退"""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting daily global fetch v4.7.1 (full mode)", flush=True)
    print(f"  Concurrency: {MAX_CONCURRENT} modules at a time", flush=True)
    print(f"  Module timeout: {MODULE_TIMEOUT}s ({MODULE_TIMEOUT//60}min)", flush=True)
    print(f"  Retry: {MAX_RETRIES}x on failure", flush=True)

    results = await run_all_modules_concurrent()

    # v4.3: Batch resolve GNews redirect URLs — 所有模块完成后专用步骤
    # v4.7: SKIP HTTP batch_resolve — 生产验证6231个GNews URL全部0%解析(HTTP无法解析JS重定向)
    # 非GNews源(feedburner_origlink/guid)已在fetch_one中本地回退处理
    # 保留代码结构以便未来复用，但当前跳过此步骤节省10+分钟
    phase_log("=" * 70)
    phase_log("PHASE: HTTP batch_resolve GNews canonical URLs")
    phase_log("  [SKIP] HTTP batch_resolve disabled (0% GNews coverage, wastes 10+ min)")
    phase_log("  Non-GNews sources already handled by feedburner_origlink/guid fallback in fetch_one()")

    resolved = 0  # skipped
    resolve_elapsed = 0

    # v4.5/v4.7: Playwright 无头浏览器解析 GNews canonical_url — 仅high优先级
    # 纯HTTP batch_resolve对GNews覆盖率为0%，需JS渲染
    phase_log("=" * 70)
    phase_log("PHASE: Playwright GNews resolve (high priority only)")
    from common import batch_resolve_gnews_with_browser, atomic_write_json

    # 重新加载文章
    articles_by_file_pw = {}
    for entry in MODULE_REGISTRY:
        output_file = entry["output"]
        full_path = os.path.join(SCRIPT_DIR, output_file)
        if not os.path.exists(full_path):
            continue
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            articles_by_file_pw[output_file] = data.get("articles", [])
        except json.JSONDecodeError:
            continue

    # v4.9: 扩大到high+medium(>=3)，max_items=500防止2800+篇超时
    pw_resolved, pw_total, pw_elapsed = await batch_resolve_gnews_with_browser(
        articles_by_file_pw, priority_filter="high+medium", max_items=500
    )
    phase_log(f"PHASE DONE: Playwright — {pw_resolved}/{pw_total} resolved ({pw_elapsed:.1f}s)")

    # 将Playwright解析结果写回模块JSON文件
    if pw_resolved > 0:
        for entry in MODULE_REGISTRY:
            output_file = entry["output"]
            full_path = os.path.join(SCRIPT_DIR, output_file)
            if output_file not in articles_by_file_pw:
                continue
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["articles"] = articles_by_file_pw[output_file]
                atomic_write_json(data, full_path)
            except (json.JSONDecodeError, OSError) as e:
                phase_log(f"  [WARN] Failed to update {output_file}: {e}")
        phase_log(f"  Updated {pw_resolved} Playwright-resolved canonical_urls written to module files")

    # v4.4/v4.7: Batch fetch full text — high+medium优先级正文抓取
    phase_log("=" * 70)
    phase_log("PHASE: Full text fetch (high+medium priority)")
    from common import fetch_full_text_batch

    # 重新加载文章（可能已被Playwright更新了canonical_url）
    articles_by_file_ft = {}
    for entry in MODULE_REGISTRY:
        output_file = entry["output"]
        full_path = os.path.join(SCRIPT_DIR, output_file)
        if not os.path.exists(full_path):
            continue
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            articles_by_file_ft[output_file] = data.get("articles", [])
        except json.JSONDecodeError:
            continue

    # v4.9: priority_filter="all" — 抓取所有有canonical_url或非GNews链接的文章正文
    fetched, total_ft, ft_elapsed = await fetch_full_text_batch(
        articles_by_file_ft, priority_filter="all", concurrency=8, timeout=15
    )
    phase_log(f"PHASE DONE: Full text — {fetched}/{total_ft} fetched ({ft_elapsed:.1f}s)")

    # v4.4: published_beijing 回填 — 对所有缺少的文章补填北京时间
    phase_log("PHASE: Beijing time backfill")
    from common import normalize_to_beijing_time
    bj_filled = 0
    for filename, articles in articles_by_file_ft.items():
        for article in articles:
            if not article.get("published_beijing") and article.get("published"):
                beijing = normalize_to_beijing_time(article["published"])
                if beijing:
                    article["published_beijing"] = beijing
                    bj_filled += 1
    if bj_filled > 0:
        phase_log(f"  Filled {bj_filled} articles with published_beijing")

    # 将正文+时间结果写回模块JSON文件
    if fetched > 0 or bj_filled > 0:
        for entry in MODULE_REGISTRY:
            output_file = entry["output"]
            full_path = os.path.join(SCRIPT_DIR, output_file)
            if output_file not in articles_by_file_ft:
                continue
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["articles"] = articles_by_file_ft[output_file]
                atomic_write_json(data, full_path)
            except (json.JSONDecodeError, OSError) as e:
                phase_log(f"  [WARN] Failed to update {output_file}: {e}")
        phase_log(f"  Updated {fetched} full_texts + {bj_filled} beijing_times written to module files")

    print(f"\n{'='*70}")
    print("Building global index...")
    seen, module_outputs = global_dedup()
    index = build_index(seen, module_outputs)

    print(f"\n{'='*70}")
    print(f"INDEX DONE.")
    print(f"  Global total: {index['global_total']}")
    print(f"  Global high: {index['global_high']}")
    print(f"  Global medium: {index['global_medium']}")
    print(f"  Global new: {index['global_new']}, continuing: {index['global_continuing']}")
    for mod, stat in index["modules"].items():
        rl = stat.get('rate_limited_feeds', 0)
        rl_tag = f" (rate_limited: {rl})" if rl else ""
        print(f"    {mod}: {stat['total']} articles ({stat['high']} high){rl_tag}")
    print(f"  Failed modules: {sum(1 for v in results.values() if not v)}/{len(results)}")
    print(f"{'='*70}")

    if all(not v for v in results.values()):
        sys.exit(1)


# ============================================================================
# v5.0: Split-Job Mode入口
# ============================================================================

async def collect_mode():
    """Job 1: RSS采集 — 18模块并发执行，产出per-module JSON文件"""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting collect mode v5.0", flush=True)
    print(f"  Concurrency: {MAX_CONCURRENT} modules at a time", flush=True)
    print(f"  Module timeout: {MODULE_TIMEOUT}s ({MODULE_TIMEOUT//60}min)", flush=True)

    results = await run_all_modules_concurrent()

    if all(not v for v in results.values()):
        phase_log("ALL MODULES FAILED — aborting")
        sys.exit(1)

    phase_log("COLLECT DONE: Module JSON files ready for artifact upload")


async def pw_high_mode():
    """Job 2: Playwright HIGH — 解析high+medium priority GNews URL，产出一个映射文件"""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting pw-high mode v4.9", flush=True)

    articles_by_file = load_articles_from_modules()
    from common import batch_resolve_gnews_with_browser

    phase_log("=" * 70)
    phase_log("PHASE: Playwright GNews resolve (high+medium priority)")
    # v4.9: high+medium + max_items=500
    pw_resolved, pw_total, pw_elapsed = await batch_resolve_gnews_with_browser(
        articles_by_file, priority_filter="high+medium", max_items=500
    )
    phase_log(f"PHASE DONE: Playwright(high+medium) — {pw_resolved}/{pw_total} resolved ({pw_elapsed:.1f}s)")

    # 保存映射文件
    save_pw_map(articles_by_file, os.path.join(SCRIPT_DIR, "_pw_high_map.json"))
    phase_log("PW-HIGH DONE: _pw_high_map.json ready for artifact upload")


async def pw_medium_mode():
    """Job 3: Playwright MEDIUM — 解析medium priority GNews URL，产出一个映射文件"""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting pw-medium mode v5.0", flush=True)

    articles_by_file = load_articles_from_modules()

    # 预过滤: 仅medium priority (>=3, <10) 的GNews URL
    from common import _is_gnews_url
    articles_by_file_medium = {}
    total_medium_gnews = 0
    for filename, articles in articles_by_file.items():
        medium = [a for a in articles
                  if a.get("priority", 0) >= 3
                  and a.get("priority", 0) < 10
                  and _is_gnews_url(a.get("link", ""))
                  and not a.get("canonical_url")]
        if medium:
            articles_by_file_medium[filename] = medium
            total_medium_gnews += len(medium)

    phase_log(f"  Pre-filtered: {total_medium_gnews} medium GNews URLs across {len(articles_by_file_medium)} files")

    if total_medium_gnews == 0:
        phase_log("  No medium GNews URLs to process — saving empty map")
        save_pw_map({}, os.path.join(SCRIPT_DIR, "_pw_medium_map.json"))
        phase_log("PW-MEDIUM DONE: _pw_medium_map.json (empty)")
        return

    from common import batch_resolve_gnews_with_browser

    phase_log("=" * 70)
    phase_log("PHASE: Playwright GNews resolve (medium priority only)")
    # 使用high+medium滤器(>=3) + 预过滤列表(已排除high), max_items=500
    pw_resolved, pw_total, pw_elapsed = await batch_resolve_gnews_with_browser(
        articles_by_file_medium, priority_filter="high+medium", max_items=500
    )
    phase_log(f"PHASE DONE: Playwright(medium) — {pw_resolved}/{pw_total} resolved ({pw_elapsed:.1f}s)")

    # 保存映射文件
    save_pw_map(articles_by_file_medium, os.path.join(SCRIPT_DIR, "_pw_medium_map.json"))
    phase_log("PW-MEDIUM DONE: _pw_medium_map.json ready for artifact upload")


async def finalize_mode():
    """Job 4: 合并PW结果 + full_text + beijing + dedup + index"""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting finalize mode v5.0", flush=True)

    # 1. 加载原始文章 + 应用PW映射
    articles_by_file = load_articles_from_modules()

    phase_log("=" * 70)
    phase_log("PHASE: Apply Playwright results")
    high_map = os.path.join(SCRIPT_DIR, "_pw_high_map.json")
    medium_map = os.path.join(SCRIPT_DIR, "_pw_medium_map.json")
    applied = apply_pw_map(articles_by_file, high_map, medium_map)

    # 统计映射文件内容
    for map_name, map_path in [("HIGH", high_map), ("MEDIUM", medium_map)]:
        if os.path.exists(map_path):
            try:
                with open(map_path, "r", encoding="utf-8") as f:
                    pw_data = json.load(f)
                phase_log(f"  PW-{map_name} map: {len(pw_data)} entries")
            except (json.JSONDecodeError, OSError):
                phase_log(f"  PW-{map_name} map: FAILED to load")
        else:
            phase_log(f"  PW-{map_name} map: NOT FOUND (non-fatal)")

    # 2. 写回模块JSON
    write_back_articles(articles_by_file)

    # 3. Full text抓取 — v4.9: all priority，只抓有canonical_url/非GNews链接的
    phase_log("=" * 70)
    phase_log("PHASE: Full text fetch (all priority, canonical_url or direct link)")
    from common import fetch_full_text_batch

    articles_by_file_ft = load_articles_from_modules()
    fetched, total_ft, ft_elapsed = await fetch_full_text_batch(
        articles_by_file_ft, priority_filter="all", concurrency=8, timeout=15
    )
    phase_log(f"PHASE DONE: Full text — {fetched}/{total_ft} fetched ({ft_elapsed:.1f}s)")

    # 4. Beijing time回填
    phase_log("PHASE: Beijing time backfill")
    from common import normalize_to_beijing_time
    bj_filled = 0
    for filename, articles in articles_by_file_ft.items():
        for article in articles:
            if not article.get("published_beijing") and article.get("published"):
                beijing = normalize_to_beijing_time(article["published"])
                if beijing:
                    article["published_beijing"] = beijing
                    bj_filled += 1
    if bj_filled > 0:
        phase_log(f"  Filled {bj_filled} articles with published_beijing")

    # 5. 写回正文+时间
    if fetched > 0 or bj_filled > 0:
        write_back_articles(articles_by_file_ft)

    # 6. Dedup + Index
    phase_log("=" * 70)
    phase_log("PHASE: Global dedup + Build index")
    seen, module_outputs = global_dedup()
    index = build_index(seen, module_outputs)

    print(f"\n{'='*70}")
    print(f"FINALIZE DONE.")
    print(f"  PW applied: {applied}")
    print(f"  Full text: {fetched}/{total_ft}")
    print(f"  Global total: {index['global_total']}")
    print(f"  Global high: {index['global_high']}")
    print(f"  Global medium: {index['global_medium']}")
    print(f"  Global new: {index['global_new']}, continuing: {index['global_continuing']}")
    print(f"{'='*70}")


def validate_params():
    """v6.0.1: 启动时校验关键参数间的逻辑一致性，防止配置冲突"""
    errors = []
    # PRUNE_AGE_DAYS 必须 >= 2× RETENTION_DAYS(30) 才能确保去重记忆覆盖数据保留期
    if PRUNE_AGE_DAYS < 60:
        errors.append(f"PRUNE_AGE_DAYS={PRUNE_AGE_DAYS} < 60，seen_index记忆可能不足以覆盖30天数据保留期，导致重复入库")
    # PLAYWRIGHT_WAIT_MAX 必须 > PLAYWRIGHT_WAIT_MIN
    if PLAYWRIGHT_WAIT_MAX <= PLAYWRIGHT_WAIT_MIN:
        errors.append(f"PLAYWRIGHT_WAIT_MAX={PLAYWRIGHT_WAIT_MAX} <= PLAYWRIGHT_WAIT_MIN={PLAYWRIGHT_WAIT_MIN}，等待范围无效")
    # DEDUP_TITLE_THRESHOLD 范围合理性
    if DEDUP_TITLE_THRESHOLD > 0.95:
        errors.append(f"DEDUP_TITLE_THRESHOLD={DEDUP_TITLE_THRESHOLD} > 0.95，去重极松，大量重复文章可能涌入")

    if errors:
        phase_log("[VALIDATE] 参数校验失败:")
        for e in errors:
            phase_log(f"  !! {e}")
        sys.exit(1)
    phase_log("[VALIDATE] 参数校验通过")


def main():
    validate_params()  # v6.0.1: 启动校验
    mode = sys.argv[1] if len(sys.argv) > 1 else "incremental"
    modes = {
        "collect": collect_mode,
        "pw-high": pw_high_mode,
        "pw-medium": pw_medium_mode,
        "finalize": finalize_mode,
        "full": main_async,
        "incremental": incremental_mode,
        "backfill": backfill_mode,
        "pw-backfill": pw_backfill_mode,
    }
    if mode not in modes:
        print(f"Unknown mode: {mode}. Available: {', '.join(modes.keys())}")
        sys.exit(1)
    asyncio.run(modes[mode]())


# ============================================================================
# v6.0: 增量采集模式
# ============================================================================

async def incremental_mode(forced_when_days=None):
    """
    v6.0 增量采集模式 — 补漏 + SeenIndex去重 + 仅对新增条目做full_text
    v6.0.6: P1 fulltext增量重试 — 从上一轮articles中提取fulltext_needs_retry，
            重试抓取（max_retry=2），避免有canonical_url的文章永远丢失FT机会。
    
    流程:
      1. 加载seen_index → 计算when_days（补漏天数）
      2. 设置环境变量OVERSEAS_WHEN_DAYS → 模块自动使用
      3. 运行18模块采集
      4. 加载articles → vs seen_index过滤（在full_text之前！）
      4.5 P1: 从上一轮articles提取fulltext_needs_retry，加入FT重试队列
      5. 仅对新增articles: Playwright + full_text + beijing
      6. 全局去重（within-run）
      7. 更新seen_index → 保存
      8. 构建index → 输出
    """
    from common import SeenIndex, atomic_write_json
    
    seen_index_path = os.path.join(SCRIPT_DIR, "seen_index.json")
    
    # 1. 加载seen_index
    phase_log("=" * 70)
    phase_log("PHASE: Load SeenIndex + Calculate when_days")
    seen_idx = SeenIndex.load(seen_index_path)
    
    if forced_when_days is not None:
        when_days = forced_when_days
    else:
        when_days = seen_idx.calc_when_days()
    
    when_str = f"{when_days}d"
    phase_log(f"  when_days={when_days} (when={when_str}), last_fetch={seen_idx.last_fetch_date}")
    
    # 2. 设置环境变量（模块中的gnews_url()会读取）
    os.environ["OVERSEAS_WHEN_DAYS"] = when_str
    
    # 3. 运行模块采集
    phase_log("=" * 70)
    phase_log(f"PHASE: Run 18 modules (when={when_str})")
    results = await run_all_modules_concurrent()
    
    if all(not v for v in results.values()):
        phase_log("ALL MODULES FAILED — aborting")
        sys.exit(1)
    
    # 4. 加载articles → 过滤seen_index（在full_text之前）
    phase_log("=" * 70)
    phase_log("PHASE: SeenIndex dedup (before Playwright/full_text)")
    articles_by_file = load_articles_from_modules()
    
    # 4a. P1: 在写回之前，先从全量articles中收集fulltext_needs_retry
    #     此时articles_by_file包含上一轮所有文章（含retry候选）
    #     写回后只有new articles，retry候选就丢失了
    MAX_FT_RETRY = 2       # 最多重试2次（加上首次共3次机会）
    MAX_RETRY_PER_RUN = 10 # 每次增量运行最多重试10篇，避免FT阶段耗时过长
    RETRY_MIN_GAP_HOURS = 24  # v6.0.8: 第2次重试间隔最低24h
    today_retry_str = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
    retry_articles_by_file = {}
    retry_count = 0
    retry_skipped = 0
    retry_time_skipped = 0  # v6.0.8: 时间退避跳过的数量
    all_retry_candidates = []  # BUG3 FIX: 收集所有候选再统一排序
    for filename, articles in articles_by_file.items():
        for a in articles:
            if a.get("content_status") != "fulltext_needs_retry":
                continue
            retry_num = a.get("fulltext_retry_count", 0)
            if retry_num >= MAX_FT_RETRY:
                retry_skipped += 1
                a["content_status"] = "fulltext_unavailable"
                continue
            # 需要有canonical_url才值得重试
            if not (a.get("canonical_url") and not _is_gnews_link(a["canonical_url"])):
                continue
            # v6.0.8: 记录首次尝试日期（仅首次）
            if not a.get("fulltext_first_try_date"):
                a["fulltext_first_try_date"] = today_retry_str
            # v6.0.8: 第2次重试时间退避 — 距首次尝试不足24h则延迟
            if retry_num == 1:
                first_date_str = a.get("fulltext_first_try_date", "")
                if first_date_str:
                    try:
                        first_date = datetime.strptime(first_date_str, "%Y-%m-%d").date()
                        gap_hours = (datetime.now(BEIJING_TZ).date() - first_date).days * 24
                        if gap_hours < RETRY_MIN_GAP_HOURS:
                            retry_time_skipped += 1
                            continue
                    except ValueError:
                        pass  # 日期格式异常，不阻拦重试
            a["fulltext_retry_count"] = retry_num + 1
            all_retry_candidates.append((filename, a))
    # BUG3 FIX: 按fulltext_retry_count升序排序，优先重试次数最少的
    all_retry_candidates.sort(key=lambda x: x[1].get("fulltext_retry_count", 0))
    for filename, a in all_retry_candidates:
        if retry_count >= MAX_RETRY_PER_RUN:
            break
        retry_articles_by_file.setdefault(filename, []).append(a)
        retry_count += 1
    if retry_count > 0:
        time_note = f", {retry_time_skipped} time-backoff deferred" if retry_time_skipped > 0 else ""
        phase_log(f"P1 FT RETRY: {retry_count} articles to retry (skipped {retry_skipped} max-retry exceeded{time_note})")
    elif retry_skipped > 0 or retry_time_skipped > 0:
        phase_log(f"P1 FT RETRY: {retry_skipped} max-retry exceeded, {retry_time_skipped} time-backoff deferred")
    
    # BUG1 FIX: 构建 retry_id_set，防止retry文章同时出现在new_articles中
    retry_id_set = set()
    for retry_list in retry_articles_by_file.values():
        for a in retry_list:
            rid = a.get("canonical_url") or a.get("link", "")
            if rid:
                retry_id_set.add(rid)

    # 4b. SeenIndex过滤（全量 → 仅新增）
    total_raw = 0
    total_new = 0
    total_seen = 0
    total_retry_deduped = 0
    for filename in list(articles_by_file.keys()):
        articles = articles_by_file[filename]
        total_raw += len(articles)
        new_articles = []
        for a in articles:
            if seen_idx.is_seen(a):
                total_seen += 1
            else:
                # BUG1 FIX: 排除retry文章，避免双重处理
                a_id = a.get("canonical_url") or a.get("link", "")
                if a_id and a_id in retry_id_set:
                    total_retry_deduped += 1
                    continue
                new_articles.append(a)
                total_new += 1
        articles_by_file[filename] = new_articles
    
    phase_log(f"  SeenIndex dedup: {total_raw} raw → {total_new} new ({total_seen} already seen, {total_retry_deduped} retry-deduped, skipped)")
    
    # 将过滤后的articles写回模块JSON（后续Playwright/full_text只处理新的）
    for entry in MODULE_REGISTRY:
        output_file = entry["output"]
        if output_file not in articles_by_file:
            continue
        full_path = os.path.join(SCRIPT_DIR, output_file)
        if not os.path.exists(full_path):
            continue
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["articles"] = articles_by_file[output_file]
            atomic_write_json(data, full_path)
        except (json.JSONDecodeError, OSError) as e:
            phase_log(f"  [WARN] Failed to update {output_file}: {e}")
    
    if total_new == 0 and retry_count == 0:
        phase_log("No new articles and no FT retries — skipping Playwright/full_text")
        # 仍然更新seen_index的last_fetch_date
        today_str = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
        seen_idx.update_stats(today_str, 0, total_seen)
        seen_idx.save(seen_index_path)
        phase_log("INCREMENTAL DONE: 0 new articles, 0 retries")
        return
    
    # total_new==0但有retry时，跳过Playwright和新增FT，直接做retry
    pw_resolved = 0; pw_total = 0; pw_elapsed = 0.0
    fetched = 0; total_ft = 0; ft_elapsed = 0.0
    
    if total_new > 0:
        # 5. Playwright（仅处理新增articles）
        phase_log("=" * 70)
        phase_log("PHASE: Playwright GNews resolve (new articles only, high+medium)")
        from common import batch_resolve_gnews_with_browser
        
        articles_by_file_pw = load_articles_from_modules()
        # v6.0.8.1: Playwright容错 — 浏览器崩溃不杀整个pipeline
        try:
            pw_resolved, pw_total, pw_elapsed = await batch_resolve_gnews_with_browser(
                articles_by_file_pw, priority_filter="high+medium", max_items=500
            )
        except Exception as pw_err:
            phase_log(f"[PLAYWRIGHT] CRASHED: {type(pw_err).__name__}: {str(pw_err)[:200]}")
            phase_log("[PLAYWRIGHT] Continuing pipeline without Playwright results")
            pw_resolved, pw_total, pw_elapsed = 0, 0, 0.0
        phase_log(f"PHASE DONE: Playwright — {pw_resolved}/{pw_total} resolved ({pw_elapsed:.1f}s)")
        
        # 将PW结果写回
        if pw_resolved > 0:
            for entry in MODULE_REGISTRY:
                output_file = entry["output"]
                full_path = os.path.join(SCRIPT_DIR, output_file)
                if output_file not in articles_by_file_pw:
                    continue
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["articles"] = articles_by_file_pw[output_file]
                    atomic_write_json(data, full_path)
                except (json.JSONDecodeError, OSError) as e:
                    phase_log(f"  [WARN] PW write-back {output_file}: {e}")
        
        # 6. Full text（仅处理新增articles）
        phase_log("=" * 70)
        phase_log("PHASE: Full text fetch (new articles only)")
        from common import fetch_full_text_batch
        
        articles_by_file_ft = load_articles_from_modules()
        fetched, total_ft, ft_elapsed = await fetch_full_text_batch(
            articles_by_file_ft, priority_filter="all", concurrency=8, timeout=15
        )
        phase_log(f"PHASE DONE: Full text — {fetched}/{total_ft} fetched ({ft_elapsed:.1f}s)")
    else:
        phase_log("No new articles but FT retries pending — skipping Playwright/new FT")
        from common import fetch_full_text_batch
    
    # 6.5 P1: fulltext增量重试 — 处理上一轮fulltext_needs_retry的文章
    retry_fetched = 0
    if retry_count > 0:
        phase_log("=" * 70)
        phase_log(f"P1 FT RETRY: Retrying {retry_count} articles from previous runs")
        retry_fetched_actual, retry_total, retry_elapsed = await fetch_full_text_batch(
            retry_articles_by_file, priority_filter="all", concurrency=8, timeout=15
        )
        phase_log(f"P1 FT RETRY DONE: {retry_fetched_actual}/{retry_total} fetched ({retry_elapsed:.1f}s)")
        # 将重试成功的结果回写到模块JSON
        for output_file, retry_list in retry_articles_by_file.items():
            full_path = os.path.join(SCRIPT_DIR, output_file)
            if not os.path.exists(full_path):
                continue
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                existing_urls = {a.get("canonical_url") or a.get("link") for a in data.get("articles", [])}
                for ra in retry_list:
                    if ra.get("full_text"):
                        # 重试成功：更新content_status
                        ra["content_status"] = "has_fulltext"
                        retry_fetched += 1
                        if ra.get("canonical_url") not in existing_urls and ra.get("link") not in existing_urls:
                            data["articles"].append(ra)
                atomic_write_json(data, full_path)
            except (json.JSONDecodeError, OSError) as e:
                phase_log(f"  [WARN] P1 retry write-back {output_file}: {e}")
    
    # 7. Beijing time回填
    phase_log("PHASE: Beijing time backfill")
    from common import normalize_to_beijing_time
    bj_filled = 0
    for filename, articles in articles_by_file_ft.items():
        for article in articles:
            if not article.get("published_beijing") and article.get("published"):
                beijing = normalize_to_beijing_time(article["published"])
                if beijing:
                    article["published_beijing"] = beijing
                    bj_filled += 1
    if bj_filled > 0:
        phase_log(f"  Filled {bj_filled} articles with published_beijing")
    
    # 写回正文+时间
    if fetched > 0 or bj_filled > 0:
        write_back_articles(articles_by_file_ft)
    
    # 8. 全局去重（within-run cross-module dedup）
    phase_log("=" * 70)
    phase_log("PHASE: Global dedup (within-run)")
    seen, module_outputs = global_dedup()
    index = build_index(seen, module_outputs)
    
    # 9. 更新seen_index
    phase_log("=" * 70)
    phase_log("PHASE: Update SeenIndex")
    today_str = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
    
    # BUG2 FIX: pw_skipped_early_stop的文章也加入seen_index
    # 原逻辑：不加入→下轮重新出现→但没有canonical_url→P1 retry无法捞→死区
    # 新逻辑：加入seen_index防止重复采集 + 标记fulltext_unavailable
    added_to_index = 0
    skipped_pw = 0
    for h, entry in seen.items():
        article = entry["item"]
        if article.get("pw_skipped_early_stop"):
            skipped_pw += 1
            article["content_status"] = "fulltext_unavailable"
            # 仍然加入seen_index，避免下轮重复采集但永远无法获取正文
            if not seen_idx.is_seen(article):
                seen_idx.add(article, date_str=today_str)
                added_to_index += 1
            continue
        if not seen_idx.is_seen(article):
            seen_idx.add(article, date_str=today_str)
            added_to_index += 1
    if skipped_pw > 0:
        phase_log(f"  {skipped_pw} pw_skipped_early_stop articles added to seen_index as fulltext_unavailable (BUG2 fix)")
    
    # 清理旧条目（>90天）
    seen_idx.prune_old_entries(max_age_days=90)
    
    # 更新统计
    seen_idx.update_stats(today_str, added_to_index, total_seen)
    seen_idx.save(seen_index_path)
    
    phase_log(f"  Added {added_to_index} new entries to seen_index")
    
    # 10. 输出summary
    print(f"\n{'='*70}")
    print(f"INCREMENTAL DONE.")
    print(f"  When window: {when_str}")
    print(f"  Raw collected: {total_raw}")
    print(f"  SeenIndex filtered: {total_seen} already seen")
    print(f"  New articles: {total_new}")
    print(f"  After global dedup: {index['global_total']}")
    print(f"  Added to seen_index: {added_to_index}")
    print(f"  Playwright: {pw_resolved}/{pw_total}, Full text: {fetched}/{total_ft}, FT retry: {retry_fetched}")
    print(f"  SeenIndex total entries: {len(seen_idx.entries)}")
    print(f"{'='*70}")


async def backfill_mode():
    """
    v6.0 首次历史回填 — 30天全量采集，建立seen_index初始基线
    """
    phase_log("=" * 70)
    phase_log("BACKFILL MODE: 30-day historical collection")
    
    # 回填模式：强制when=30d
    await incremental_mode(forced_when_days=30)
    
    phase_log("BACKFILL DONE: seen_index baseline established")


async def pw_backfill_mode():
    """
    v6.0.8.1 GNews Playwright回填 — 对已有数据中未解析的GNews链接批量解析
    不跑采集/去重，只做Playwright解析+正文提取+写回模块文件
    分批处理，每批500篇，批次间冷却60s防Google限速
    v6.0.8.2: 自动从artifact下载模块数据（runner上无持久化的module JSON）
    """
    from common import batch_resolve_gnews_with_browser, atomic_write_json, _is_gnews_url
    
    phase_log("=" * 70)
    phase_log("PW-BACKFILL MODE: Resolve unresolved GNews URLs in existing data")
    
    # 0. 尝试从GitHub artifact下载模块数据（CI runner上没有持久化数据）
    articles_by_file = load_articles_from_modules()
    total_loaded = sum(len(v) for v in articles_by_file.values())
    
    if total_loaded == 0:
        phase_log("  No module data found locally, attempting to download from GitHub artifact...")
        _gh_token = os.environ.get("GITHUB_TOKEN", os.environ.get("GH_TOKEN", ""))
        _gh_repo = os.environ.get("GITHUB_REPOSITORY", "")
        try:
            import subprocess, zipfile, io, glob as _glob, shutil
            import urllib.request as _urllib_request
            import urllib.error as _urllib_error
            
            _api = "https://api.github.com"
            _headers = {"Authorization": f"token {_gh_token}", "Accept": "application/vnd.github.v3+json"}
            
            def _api_get(url):
                req = _urllib_request.Request(url, headers=_headers)
                with _urllib_request.urlopen(req, timeout=15) as resp:
                    return json.loads(resp.read().decode("utf-8")), resp.status
            
            # Step 1: Find successful workflow runs with substantial json-outputs artifact
            # (pw-backfill runs are "success" but have tiny artifacts ~1MB with only seen_index)
            _runs_data, _status = _api_get(f"{_api}/repos/{_gh_repo}/actions/runs?status=success&per_page=10")
            _runs = _runs_data.get("workflow_runs", [])
            if not _runs:
                phase_log("  WARN: No successful runs found")
                raise Exception("No runs")
            
            _best_run_id = None
            _json_art = None
            for _run in _runs:
                _art_data, _ = _api_get(f"{_api}/repos/{_gh_repo}/actions/runs/{_run['id']}/artifacts")
                _artifacts = _art_data.get("artifacts", [])
                _cand = next((a for a in _artifacts if a["name"].startswith("json-outputs")), None)
                if _cand and _cand["size_in_bytes"] > 200000:  # >200KB = has module data (not just seen_index)
                    _best_run_id = _run["id"]
                    _json_art = _cand
                    phase_log(f"  Found data-rich run: {_best_run_id} ({_cand['name']}, {_cand['size_in_bytes']} bytes)")
                    break
            
            if not _json_art:
                phase_log("  WARN: No json-outputs artifact with module data found in recent runs")
                raise Exception("No artifact")
            
            phase_log(f"  Found artifact: {_json_art['name']} (id: {_json_art['id']})")
            
            # Step 3: Download artifact zip via GitHub API (handles Azure Blob redirect)
            # Must strip Authorization header on redirect to Azure Blob (different host)
            _dl_url = f"{_api}/repos/{_gh_repo}/actions/artifacts/{_json_art['id']}/zip"
            
            class _NoAuthRedirectHandler(_urllib_request.HTTPRedirectHandler):
                """Remove Authorization header when redirecting to a different host"""
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
                    if new_req and new_req.host != req.host:
                        new_req.remove_header("Authorization")
                    return new_req
            
            try:
                _opener = _urllib_request.build_opener(_NoAuthRedirectHandler)
                _dl_req = _urllib_request.Request(_dl_url, headers={"Authorization": f"token {_gh_token}"})
                _dl_resp_raw = _opener.open(_dl_req, timeout=60)
                _dl_content = _dl_resp_raw.read()
            except _urllib_error.HTTPError as _http_err:
                phase_log(f"  WARN: Download artifact failed ({_http_err.code}): {str(_http_err)[:200]}")
                raise
            
            phase_log(f"  Downloaded artifact zip: {len(_dl_content)} bytes")
            
            # Step 4: Extract JSON files from zip to scripts/
            _zf = zipfile.ZipFile(io.BytesIO(_dl_content))
            _copied = 0
            for name in _zf.namelist():
                if name.endswith(".json") and not name.endswith("seen_index.json"):
                    data = _zf.read(name)
                    fname = os.path.basename(name)
                    dest = os.path.join(SCRIPT_DIR, fname)
                    with open(dest, "wb") as wf:
                        wf.write(data)
                    _copied += 1
                    phase_log(f"    Extracted {fname} ({len(data)} bytes)")
            _zf.close()
            phase_log(f"  Extracted {_copied} JSON files from artifact")
            
        except Exception as e:
            phase_log(f"  WARN: Artifact download failed: {type(e).__name__}: {str(e)[:200]}")
        
        # 重新加载
        articles_by_file = load_articles_from_modules()
        total_loaded = sum(len(v) for v in articles_by_file.values())
        phase_log(f"  After artifact restore: {total_loaded} articles from {len(articles_by_file)} files")
    
    # 1. 统计未解析GNews链接
    unresolved = 0
    for filename, articles in articles_by_file.items():
        for article in articles:
            if _is_gnews_url(article.get("link", "")) and not article.get("canonical_url"):
                unresolved += 1
    phase_log(f"  Unresolved GNews URLs: {unresolved}")
    
    if unresolved == 0:
        phase_log("PW-BACKFILL DONE: No unresolved GNews URLs")
        return
    
    # 3. 分批Playwright解析
    BATCH_SIZE = 500
    total_resolved = 0
    total_attempted = 0
    batch_num = 0
    
    while True:
        batch_num += 1
        # 重新加载（前批结果已写回）
        articles_by_file = load_articles_from_modules()
        
        # 统计剩余未解析
        remaining = 0
        for filename, articles in articles_by_file.items():
            for article in articles:
                if _is_gnews_url(article.get("link", "")) and not article.get("canonical_url"):
                    remaining += 1
        
        if remaining == 0:
            phase_log(f"PW-BACKFILL: All GNews URLs resolved after {batch_num - 1} batches")
            break
        
        phase_log(f"  Batch {batch_num}: {remaining} URLs remaining, processing up to {BATCH_SIZE}")
        
        # v6.0.8.1: 容错
        try:
            resolved, attempted, elapsed = await batch_resolve_gnews_with_browser(
                articles_by_file, priority_filter="all", max_items=BATCH_SIZE
            )
        except Exception as pw_err:
            phase_log(f"  [PW-BACKFILL] Batch {batch_num} CRASHED: {type(pw_err).__name__}: {str(pw_err)[:200]}")
            resolved, attempted, elapsed = 0, 0, 0.0
        
        total_resolved += resolved
        total_attempted += attempted
        phase_log(f"  Batch {batch_num} DONE: {resolved}/{attempted} resolved ({elapsed:.1f}s)")
        
        # 4. 写回模块文件
        written = 0
        for entry in MODULE_REGISTRY:
            output_file = entry["output"]
            full_path = os.path.join(SCRIPT_DIR, output_file)
            if output_file not in articles_by_file:
                continue
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["articles"] = articles_by_file[output_file]
                atomic_write_json(data, full_path)
                written += 1
            except (json.JSONDecodeError, OSError) as e:
                phase_log(f"  [WARN] PW write-back {output_file}: {e}")
        phase_log(f"  Written back to {written} module files")
        
        # 5. 批次间冷却
        if remaining > BATCH_SIZE:
            phase_log(f"  Cooling down 60s before next batch...")
            import asyncio
            await asyncio.sleep(60)
    
    # 6. 对新解析的文章补充full_text（有canonical_url但无full_text的）
    phase_log("=" * 70)
    phase_log("PHASE: Full text fetch for newly resolved articles")
    from common import fetch_full_text_batch
    
    articles_by_file_ft = load_articles_from_modules()
    ft_candidates = 0
    for filename, articles in articles_by_file_ft.items():
        for article in articles:
            if article.get("canonical_url") and not article.get("full_text") and not article.get("content_status"):
                ft_candidates += 1
    phase_log(f"  {ft_candidates} articles with canonical_url but no full_text")
    
    if ft_candidates > 0:
        try:
            fetched, ft_total, ft_elapsed = await fetch_full_text_batch(
                articles_by_file_ft, priority_filter="all", concurrency=8, timeout=15
            )
            phase_log(f"  Full text: {fetched}/{ft_total} fetched ({ft_elapsed:.1f}s)")
        except Exception as ft_err:
            phase_log(f"  [PW-BACKFILL] Full text CRASHED: {type(ft_err).__name__}: {str(ft_err)[:200]}")
        
        # 写回
        written = 0
        for entry in MODULE_REGISTRY:
            output_file = entry["output"]
            full_path = os.path.join(SCRIPT_DIR, output_file)
            if output_file not in articles_by_file_ft:
                continue
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["articles"] = articles_by_file_ft[output_file]
                atomic_write_json(data, full_path)
                written += 1
            except (json.JSONDecodeError, OSError) as e:
                phase_log(f"  [WARN] FT write-back {output_file}: {e}")
    
    phase_log(f"PW-BACKFILL DONE: {total_resolved}/{total_attempted} URLs resolved total")


if __name__ == "__main__":
    main()
