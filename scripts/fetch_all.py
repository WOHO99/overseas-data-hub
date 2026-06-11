#!/usr/bin/env python3
"""
fetch_all.py v3.4 — 主调度脚本
v3.2: 模块超时、错误隔离、连续失败告警、关键词外置、全局双层去重
v3.3: 14模块（2场景+4主题+8区域），信号性词汇检测，全球商业情报仪表盘
v3.4: 模块并行执行(ProcessPoolExecutor)+模块超时收紧5min，总运行时间从30-60min降至4-8min
"""

import json
import os
import sys
from datetime import datetime, timezone
from concurrent.futures import ProcessPoolExecutor, as_completed

# 将common.py和modules目录加入path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(SCRIPT_DIR, "modules"))

# ============================================================
# 模块注册表 — v3.3: 14模块（2场景+4主题+8区域）
# ============================================================
MODULE_REGISTRY = [
    # 场景模块
    {"module": "global_business", "output": "global_business.json", "core": True},
    {"module": "finance_global", "output": "finance.json", "core": False},
    # 主题模块 (v3.3新增)
    {"module": "tech_industry", "output": "tech_industry.json", "core": False},
    {"module": "energy_commodities", "output": "energy_commodities.json", "core": False},
    {"module": "geopolitics_risk", "output": "geopolitics_risk.json", "core": False},
    {"module": "esg_sustainability", "output": "esg_sustainability.json", "core": False},
    # 区域模块
    {"module": "region_se_asia", "output": "se_asia.json", "core": False},
    {"module": "region_south_asia", "output": "south_asia.json", "core": False},
    {"module": "region_middle_east", "output": "middle_east.json", "core": False},
    {"module": "region_latin_america", "output": "latam.json", "core": False},
    {"module": "region_africa", "output": "africa.json", "core": False},
    {"module": "region_europe", "output": "europe.json", "core": False},
    {"module": "region_cis", "output": "cis.json", "core": False},
    {"module": "region_east_asia", "output": "east_asia.json", "core": False},
]

MODULE_TIMEOUT_SECONDS = 300  # 5分钟超时（v3.4: 从15min收紧，含15s/socket超时后单模块最多3-4min）
MAX_PARALLEL_MODULES = 7      # 并行模块数（GitHub Actions ubuntu-latest: 2核，7进程足够）


def run_single_module(mod_name):
    """
    在当前进程中运行单个模块（用于ProcessPoolExecutor）。
    返回 (mod_name, success_bool)。
    """
    import socket
    socket.setdefaulttimeout(15)  # 子进程也要设socket超时

    try:
        mod = __import__(mod_name)
        from common import run_module
        output = run_module(mod.CONFIG)
        return (mod_name, True)
    except Exception as e:
        print(f"  [RUN_ERROR] {mod_name}: {e}")
        return (mod_name, False)


def run_all_modules_parallel():
    """
    v3.4: 并行执行所有模块，错误隔离。
    14个模块分批并行，每批MAX_PARALLEL_MODULES个。
    """
    results = {}

    print(f"\nLaunching {len(MODULE_REGISTRY)} modules with max {MAX_PARALLEL_MODULES} parallel...")
    start_time = datetime.now(timezone.utc)

    with ProcessPoolExecutor(max_workers=MAX_PARALLEL_MODULES) as executor:
        future_to_mod = {}
        for entry in MODULE_REGISTRY:
            mod_name = entry["module"]
            future = executor.submit(run_single_module, mod_name)
            future_to_mod[future] = mod_name

        for future in as_completed(future_to_mod, timeout=MODULE_TIMEOUT_SECONDS + 30):
            mod_name = future_to_mod[future]
            try:
                _, success = future.result(timeout=5)
                results[mod_name] = success
                status = "OK" if success else "FAIL"
                print(f"  [{status}] {mod_name} (parallel)")
            except Exception as e:
                results[mod_name] = False
                print(f"  [EXCEPTION] {mod_name}: {e}")

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    print(f"\nAll modules finished in {elapsed:.0f}s ({elapsed/60:.1f}min)")

    # 连续失败计数
    fail_counts = load_fail_counts()
    new_fail_counts = {}
    for entry in MODULE_REGISTRY:
        mod_name = entry["module"]
        is_core = entry.get("core", False)
        if results.get(mod_name, False):
            new_fail_counts[mod_name] = 0
        else:
            prev = fail_counts.get(mod_name, 0)
            new_fail_counts[mod_name] = prev + 1
            consecutive = new_fail_counts[mod_name]
            if is_core and consecutive >= 3:
                print(f"\n{'!'*70}")
                print(f"!!! CRITICAL: Core module {mod_name} has failed {consecutive} days in a row!")
                print(f"!!! Manual intervention required.")
                print(f"{'!'*70}")

    save_fail_counts(new_fail_counts)

    # 转换为 output_file → bool 格式
    output_results = {}
    for entry in MODULE_REGISTRY:
        output_results[entry["output"]] = results.get(entry["module"], False)

    return output_results


# ============================================================
# 连续失败计数（持久化到 fail_counts.json）
# ============================================================

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


# ============================================================
# 全局去重（双层：link哈希 + 标题相似度）
# ============================================================

def global_dedup():
    """跨模块全局去重"""
    from common import link_hash, title_similarity, parse_published_time

    seen = {}  # link_hash → {"item": ..., "modules": [...]}
    module_outputs = {}

    for entry in MODULE_REGISTRY:
        output_file = entry["output"]
        if not os.path.exists(output_file):
            continue
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print(f"  [WARN] {output_file} is corrupt, skipping")
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
                seen[h] = {
                    "item": article,
                    "modules": [data["module"]]
                }

    # 第二层：标题相似度去重（跨模块）
    items_list = list(seen.values())
    items_list.sort(key=lambda x: x["item"]["priority"], reverse=True)
    kept = []
    removed_hashes = set()

    for i, entry_a in enumerate(items_list):
        h_a = link_hash(entry_a["item"]["link"])
        if h_a in removed_hashes:
            continue
        kept.append(entry_a)
        for j in range(i + 1, len(items_list)):
            h_b = link_hash(items_list[j]["item"]["link"])
            if h_b in removed_hashes:
                continue
            sim = title_similarity(entry_a["item"]["title"], items_list[j]["item"]["title"])
            if sim >= 0.85:
                t1 = parse_published_time(entry_a["item"]["published"])
                t2 = parse_published_time(items_list[j]["item"]["published"])
                if t1 and t2 and abs((t1 - t2).total_seconds()) < 86400:
                    removed_hashes.add(h_b)

    # 重建seen dict
    final_seen = {}
    for entry in kept:
        h = link_hash(entry["item"]["link"])
        final_seen[h] = entry

    return final_seen, module_outputs


# ============================================================
# 全局索引
# ============================================================

def build_index(seen, module_outputs):
    """构建全局索引文件 index.json（v3.4: 含信号性词汇聚集检测）"""
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
            }

    high_articles = []
    for a in all_articles:
        if a["item"]["relevance"] == "high":
            art = a["item"].copy()
            art["matched_modules"] = a["modules"]
            high_articles.append(art)
    high_articles.sort(key=lambda x: x["priority"], reverse=True)

    # v3.3: 全局信号性词汇聚集检测
    global_signal_counts = {}
    for a in all_articles:
        for sk in a["item"].get("signal_keywords", []):
            global_signal_counts[sk] = global_signal_counts.get(sk, 0) + 1

    # 聚集阈值：同一信号词在全库出现>=5次 → 告警
    signal_alerts = {k: v for k, v in global_signal_counts.items() if v >= 5}

    index = {
        "version": "3.4",
        "updated": now.isoformat(),
        "fetch_date_utc": now.strftime("%Y-%m-%d"),
        "global_total": total_global,
        "global_high": high_global,
        "global_medium": medium_global,
        "global_signal_alerts": signal_alerts,
        "modules": module_stats,
        "high_priority_articles": high_articles[:100],
    }

    atomic_write_json(index, "index.json")
    return index


# ============================================================
# 主入口
# ============================================================

def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting daily global fetch v3.4 (14 modules, parallel)...")
    print(f"Registered modules: {len(MODULE_REGISTRY)}")
    print(f"Parallel workers: {MAX_PARALLEL_MODULES}")
    print(f"Module timeout: {MODULE_TIMEOUT_SECONDS}s ({MODULE_TIMEOUT_SECONDS//60}min)")

    # Step 1: 并行运行所有模块
    results = run_all_modules_parallel()

    # Step 2: 全局去重+索引
    print(f"\n{'='*70}")
    print("Building global index with cross-module dedup (link + title)...")
    seen, module_outputs = global_dedup()

    # Step 3: 输出全局索引
    index = build_index(seen, module_outputs)

    print(f"\n{'='*70}")
    print(f"ALL DONE.")
    print(f"  Global total: {index['global_total']}")
    print(f"  Global high: {index['global_high']}")
    print(f"  Global medium: {index['global_medium']}")
    print(f"  Modules: {len(index['modules'])}")
    for mod, stat in index["modules"].items():
        print(f"    {mod}: {stat['total']} articles ({stat['high']} high)")
    print(f"  Failed modules: {sum(1 for v in results.values() if not v)}/{len(results)}")
    print(f"  Index: index.json")
    print(f"{'='*70}")

    # 如果全部失败，返回非零退出码
    if all(not v for v in results.values()):
        print("ALL MODULES FAILED — exit with error code 1")
        sys.exit(1)


if __name__ == "__main__":
    main()
