#!/usr/bin/env python3
"""
region_latin_america.py — 拉美深度模块
v3.3升级：增加政治稳定、基础设施、科技、气候、人口、大国关系+葡/西语搜索
"""

import sys
import os
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_module, gnews_url, load_keywords

_config_dir = os.path.join(_scripts_dir, "config")
_module_name = "region_latin_america"
_core_kw, _important_kw, _aux_kw, _signal_kw, _exclude_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "拉美深度",
    "output_file": "latam.json",
    "max_articles": 800,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "exclude_keywords": _exclude_kw,
    "feeds": {
        "墨西哥": [
        ],
        "巴西": [
        ],
        "阿根廷+智利+其他": [
        ],
        "政治+社会": [
        ],
        "基础设施+科技": [
        ],
        "气候+人口": [
        ],
        "大国关系": [
            {"url": gnews_url("US Latin America trade relation summit policy 2026"), "tag": "GNews | US-LatAm"},
            {"url": gnews_url("China Latin America trade investment BRI critical minerals"), "tag": "GNews | China-LatAm"},
        ],
        "本地语言搜索": [
        ],
        "独立RSS源": [
            # DEAD: {"url": "https://en.mercopress.com/rss/", "tag": "MercoPress"},
            {"url": "https://valor.globo.com/rss", "tag": "Valor Econômico"},
        ],
        "信号性查询": [
            {"url": gnews_url('"supply disruption" Latin America mining commodity'), "tag": "GNews | Signal: LatAm Disrupt"},
            {"url": gnews_url('"political crisis" "debt default" Latin America'), "tag": "GNews | Signal: LatAm Crisis"},
        ],
        "专题精选": [
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
