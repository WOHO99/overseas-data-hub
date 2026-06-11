#!/usr/bin/env python3
"""
fetch_all.py v4.0 — 主调度脚本 (asyncio版)
v3.5: 顺序执行止血，40-60min
v4.0: asyncio异步执行，预期3-5min
  - 每个模块内部全量异步并发(aiohttp Semaphore50)
  - 模块间顺序执行(asyncio.wait_for 300s超时)
"""

import json
import os
import sys
import asyncio
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
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

MODULE_TIMEOUT_SECONDS = 300


async def run_all_modules_async():
    from common import run_module_async

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

        mod = __import__(mod_name)
        try:
            await asyncio.wait_for(
                run_module_async(mod.CONFIG),
                timeout=MODULE_TIMEOUT_SECONDS
            )
            success = os.path.exists(entry["output"])
        except asyncio.TimeoutError:
            print(f"  [TIMEOUT] {mod_name} exceeded {MODULE_TIMEOUT_SECONDS}s")
            success = False
        except Exception as e:
            print(f"  [RUN_ERROR] {mod_name}: {e}")
            success = False

        if success:
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
                print(f"!!! CRITICAL: Core module {mod_name} failed {consecutive} days in a row!")
                print(f"{'!'*70}")

    save_fail_counts(new_fail_counts)
    elapsed = (datetime.now(timezone.utc) - start_all).total_seconds()
    print(f"\nAll modules completed in {elapsed:.0f}s ({elapsed/60:.1f}min)")
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
        "version": "4.0",
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


async def main_async():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting daily global fetch v4.0 (asyncio, 14 modules)...")
    print(f"Module timeout: {MODULE_TIMEOUT_SECONDS}s ({MODULE_TIMEOUT_SECONDS//60}min)")

    results = await run_all_modules_async()

    print(f"\n{'='*70}")
    print("Building global index...")
    seen, module_outputs = global_dedup()
    index = build_index(seen, module_outputs)

    print(f"\n{'='*70}")
    print(f"ALL DONE.")
    print(f"  Global total: {index['global_total']}")
    print(f"  Global high: {index['global_high']}")
    print(f"  Global medium: {index['global_medium']}")
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
