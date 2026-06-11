#!/usr/bin/env python3
"""
fetch_all.py v3.5 — 主调度脚本
v3.2: 模块超时、错误隔离、连续失败告警、关键词外置、全局双层去重
v3.3: 14模块（2场景+4主题+8区域），信号性词汇检测，全球商业情报仪表盘
v3.4: 模块并行(ProcessPoolExecutor) — 实测在2核VM上卡死，放弃
v3.5: 回退顺序执行 + socket 10s + 模块超时5min + 步进式日志
      预计运行时间：40-60min（阶段2将用asyncio降至3-5min）
"""

import json
import os
import sys
import subprocess
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(SCRIPT_DIR, "modules"))

# ============================================================
# 模块注册表 — 14模块
# ============================================================
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

MODULE_TIMEOUT_SECONDS = 300  # 5分钟硬超时


def run_module_with_timeout(mod_name, timeout=MODULE_TIMEOUT_SECONDS):
    """在子进程中运行单个模块，带超时控制。"""
    import socket
    socket.setdefaulttimeout(10)  # 子进程也设10s

    try:
        proc = subprocess.Popen(
            [sys.executable, "-c",
             f"import sys,socket; socket.setdefaulttimeout(10); "
             f"sys.path.insert(0, '{SCRIPT_DIR}'); "
             f"sys.path.insert(0, '{os.path.join(SCRIPT_DIR, 'modules')}'); "
             f"import {mod_name}; from common import run_module; "
             f"run_module({mod_name}.CONFIG)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=SCRIPT_DIR,
        )
        try:
            stdout, _ = proc.communicate(timeout=timeout)
            print(stdout)
            if proc.returncode != 0:
                print(f"  [MODULE_ERROR] {mod_name} exited with code {proc.returncode}")
                return False
            return True
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            print(f"  [TIMEOUT] {mod_name} exceeded {timeout}s, killed.")
            return False
    except Exception as e:
        print(f"  [LAUNCH_ERROR] {mod_name}: {e}")
        return False


def run_all_modules():
    """顺序执行所有模块，错误隔离"""
    results = {}
    fail_counts = load_fail_counts()
    new_fail_counts = {}
    start_all = datetime.now(timezone.utc)

    for i, entry in enumerate(MODULE_REGISTRY):
        mod_name = entry["module"]
        is_core = entry.get("core", False)
        elapsed = (datetime.now(timezone.utc) - start_all).total_seconds()
        print(f"\n{'#'*70}")
        print(f"# [{i+1}/{len(MODULE_REGISTRY)}] Module: {mod_name} {'[CORE]' if is_core else ''}")
        print(f"# Elapsed: {elapsed:.0f}s ({elapsed/60:.1f}min)")
        print(f"{'#'*70}")

        success = run_module_with_timeout(mod_name)

        if success and os.path.exists(entry["output"]):
            results[entry["output"]] = True
            new_fail_counts[mod_name] = 0
            print(f"[OK] {mod_name} → {entry['output']}")
        else:
            results[entry["output"]] = False
            prev = fail_counts.get(mod_name, 0)
            new_fail_counts[mod_name] = prev + 1
            consecutive = new_fail_counts[mod_name]
            print(f"[FAIL] {mod_name} (consecutive: {consecutive})")

            if is_core and consecutive >= 3:
                print(f"\n{'!'*70}")
                print(f"!!! CRITICAL: Core module {mod_name} has failed {consecutive} days in a row!")
                print(f"!!! Manual intervention required.")
                print(f"{'!'*70}")

    save_fail_counts(new_fail_counts)

    elapsed = (datetime.now(timezone.utc) - start_all).total_seconds()
    print(f"\nAll modules completed in {elapsed:.0f}s ({elapsed/60:.1f}min)")
    return results


# ============================================================
# 连续失败计数
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
# 全局去重
# ============================================================

def global_dedup():
    from common import link_hash, title_similarity, parse_published_time

    seen = {}
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
                seen[h] = {"item": article, "modules": [data["module"]]}

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

    final_seen = {}
    for entry in kept:
        h = link_hash(entry["item"]["link"])
        final_seen[h] = entry

    return final_seen, module_outputs


# ============================================================
# 全局索引
# ============================================================

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
    for a in all_articles:
        if a["item"]["relevance"] == "high":
            art = a["item"].copy()
            art["matched_modules"] = a["modules"]
            high_articles.append(art)
    high_articles.sort(key=lambda x: x["priority"], reverse=True)

    global_signal_counts = {}
    for a in all_articles:
        for sk in a["item"].get("signal_keywords", []):
            global_signal_counts[sk] = global_signal_counts.get(sk, 0) + 1

    signal_alerts = {k: v for k, v in global_signal_counts.items() if v >= 5}

    index = {
        "version": "3.5",
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
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting daily global fetch v3.5 (14 modules, sequential)...")
    print(f"Registered modules: {len(MODULE_REGISTRY)}")
    print(f"Module timeout: {MODULE_TIMEOUT_SECONDS}s ({MODULE_TIMEOUT_SECONDS//60}min)")

    results = run_all_modules()

    print(f"\n{'='*70}")
    print("Building global index with cross-module dedup...")
    seen, module_outputs = global_dedup()
    index = build_index(seen, module_outputs)

    print(f"\n{'='*70}")
    print(f"ALL DONE.")
    print(f"  Global total: {index['global_total']}")
    print(f"  Global high: {index['global_high']}")
    print(f"  Global medium: {index['global_medium']}")
    print(f"  Modules: {len(index['modules'])}")
    for mod, stat in index["modules"].items():
        rl = stat.get('rate_limited_feeds', 0)
        rl_tag = f" (rate_limited: {rl})" if rl else ""
        print(f"    {mod}: {stat['total']} articles ({stat['high']} high){rl_tag}")
    print(f"  Failed modules: {sum(1 for v in results.values() if not v)}/{len(results)}")
    print(f"  Index: index.json")
    print(f"{'='*70}")

    if all(not v for v in results.values()):
        print("ALL MODULES FAILED — exit with error code 1")
        sys.exit(1)


if __name__ == "__main__":
    main()
