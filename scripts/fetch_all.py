#!/usr/bin/env python3
"""
fetch_all.py v4.2 — 主调度脚本 (subprocess隔离 + 并发模块 + Bucket+RapidFuzz去重)
v3.5: 顺序执行，40-60min，卡死风险
v4.0: asyncio同进程，仍然卡死（feedparser线程池hang无法取消）
v4.1: 每个模块独立subprocess，3个模块并发，硬超时SIGKILL
v4.2: global_dedup()用Bucket分桶+RapidFuzz替代O(n²)difflib，97min→0.4s
  - Bucket分桶：按标准化标题前3字符分桶，比较次数降88倍
  - RapidFuzz：C++实现，单次比较比difflib快206倍
  - dedup_title_level()同步优化
"""

import json
import os
import sys
import asyncio
import time
import re
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 确保common.py可导入
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(SCRIPT_DIR, "modules"))

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
]

MAX_CONCURRENT = 3
MODULE_TIMEOUT = 300  # 5分钟硬超时
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

    # 按标准化标题前3字符分桶 — 将 O(n²) 降至 O(bucket_size²)
    def _norm_key(title):
        return re.sub(r'[^\w\s]', '', title.lower()).strip()[:3]

    buckets = {}
    for idx, entry in enumerate(items_list):
        key = _norm_key(entry["item"]["title"]) or "_"
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
    from common import atomic_write_json

    now = datetime.now(timezone.utc)
    all_articles = list(seen.values())
    total_global = len(all_articles)
    high_global = len([a for a in all_articles if a["item"]["relevance"] == "high"])
    medium_global = len([a for a in all_articles if a["item"]["relevance"] == "medium"])

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
    signal_alerts = {k: v for k, v in global_signal_counts.items() if v >= 5}

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
        "modules": module_stats,
        "high_priority_articles": high_articles[:100],
    }
    atomic_write_json(index, os.path.join(SCRIPT_DIR, "index.json"))
    return index


async def main_async():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting daily global fetch v4.3")
    print(f"  Concurrency: {MAX_CONCURRENT} modules at a time")
    print(f"  Module timeout: {MODULE_TIMEOUT}s ({MODULE_TIMEOUT//60}min)")
    print(f"  Retry: {MAX_RETRIES}x on failure")

    results = await run_all_modules_concurrent()

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


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
