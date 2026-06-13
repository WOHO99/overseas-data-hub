#!/usr/bin/env python3
"""
fetch_all.py v5.0 — Split-Job架构 (4-Job流水线)
v4.7.1: 回滚+可观测性增强
v4.7.2: Playwright medium采样测试 → 数据证明medium全量需122min
v5.0: Split-Job架构 — 将pipeline拆为4个独立Job:
  - collect: 18模块RSS采集+去重
  - pw-high: Playwright HIGH only (~12min)
  - pw-medium: Playwright MEDIUM only (~122min, 与pw-high并行)
  - finalize: 合并PW结果+full_text+beijing+dedup+index

用法: python fetch_all.py [--mode collect|pw-high|pw-medium|finalize|full]
  full = v4.7.1单Job模式(默认, 兼容回退)
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

MODULE_REGISTRY = [
    {"module": "global_business", "output": "global_business.json", "core": True},
    {"module": "finance_global", "output": "finance.json", "core": False},
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
        sys.executable, script_path,
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
                                               "RATE_LIMITED", "FAIL", "Category:", "Elapsed"]):
                    print(f"  {line}")
        
        if stderr_data and proc.returncode != 0:
            err_text = stderr_data.decode("utf-8", errors="replace")[-500:]
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

    return final_seen, module_outputs


def build_index(seen, module_outputs):
    from common import atomic_write_json, link_hash

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    all_articles = list(seen.values())
    total_global = len(all_articles)
    high_global = len([a for a in all_articles if a["item"]["relevance"] == "high"])
    medium_global = len([a for a in all_articles if a["item"]["relevance"] == "medium"])

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

    # P4-8: 死源熔断器 — 连续3天零产出（排除rate_limited源）
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

    # 更新死亡历史
    CIRCUIT_BREAKER_THRESHOLD = 3
    updated_dead = {}
    circuit_broken_sources = []
    all_tags = set(list(source_output_count.keys()) + list(dead_history.keys()))
    for tag in all_tags:
        count = source_output_count.get(tag, 0)
        prev = dead_history.get(tag, {})
        consecutive_zeros = prev.get("consecutive_zeros", 0)
        is_rate_limited = tag in rate_limited_sources
        status = "active"

        if count == 0 and not is_rate_limited:
            consecutive_zeros += 1
        else:
            consecutive_zeros = 0

        if consecutive_zeros >= CIRCUIT_BREAKER_THRESHOLD:
            status = "circuit_breaker"
            circuit_broken_sources.append(tag)
            # 联动source_fingerprint：标记熔断状态
            if tag in source_fingerprint:
                source_fingerprint[tag]["status"] = "circuit_breaker"

        updated_dead[tag] = {
            "consecutive_zeros": consecutive_zeros,
            "status": status,
            "last_output_date": today_str if count > 0 else prev.get("last_output_date", ""),
        }

    atomic_write_json(updated_dead, circuit_breaker_path)
    if circuit_broken_sources:
        print(f"  Circuit breaker: {len(circuit_broken_sources)} sources dead "
              f"(>= {CIRCUIT_BREAKER_THRESHOLD} days zero output)")
        for src in circuit_broken_sources[:10]:
            info = updated_dead[src]
            print(f"    - {src}: {info['consecutive_zeros']} days zero, last output: {info.get('last_output_date', 'never')}")

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
    for a in all_articles:
        if a["item"]["relevance"] == "high":
            art = a["item"].copy()
            art["matched_modules"] = a["modules"]
            high_articles.append(art)
        inc = a["item"].get("_incremental", "")
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
        baseline = max(high_7d, 3)

        # P1: 计算连续告警天数
        consecutive_alert_days = 0
        for d_str in sorted(history.keys(), reverse=True):
            if d_str == today_str:
                continue
            d_count = history[d_str]
            d_baseline = 3  # 历史天无法重算baseline，用min baseline=3
            if d_count >= d_baseline:
                consecutive_alert_days += 1
            else:
                break

        # P1: 触发条件 = 超基线 OR (持续告警条件: count>=3 AND 连续告警>=1 AND count >= 7d均值×1.5)
        spike_triggered = count > baseline
        sustained_triggered = (count >= 3 and consecutive_alert_days >= 1 and count >= mean_7d * 1.5) if mean_7d > 0 else False
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
            "baseline_note": f"max(7d_high={high_7d}, 3)={baseline}",
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
        "method": "max(7d_high, 3) + sustained(mean_7d*1.5)",
        "signals": signal_summary_list,
    }
    from common import atomic_write_json as _awj  # already imported above
    _awj(signal_summary_output, os.path.join(SCRIPT_DIR, "signal_summary.json"))
    triggered_count = len(signal_alerts)
    print(f"  Signal baseline: {triggered_count} triggered, {len(global_signal_counts)} total signals")

    index = {
        "version": "4.3",
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


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    modes = {
        "collect": collect_mode,
        "pw-high": pw_high_mode,
        "pw-medium": pw_medium_mode,
        "finalize": finalize_mode,
        "full": main_async,
    }
    if mode not in modes:
        print(f"Unknown mode: {mode}. Available: {', '.join(modes.keys())}")
        sys.exit(1)
    asyncio.run(modes[mode]())


if __name__ == "__main__":
    main()
