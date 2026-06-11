#!/usr/bin/env python3
"""
region_cis.py — 独联体深度模块
v3.3升级：增加政治稳定、基础设施、科技、水争端、人口、大国关系+俄语搜索
"""

import sys
import os
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_module, gnews_url, load_keywords

_config_dir = os.path.join(_scripts_dir, "config")
_module_name = "region_cis"
_core_kw, _important_kw, _aux_kw, _signal_kw, _exclude_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "独联体深度",
    "output_file": "cis.json",
    "max_articles": 250,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "exclude_keywords": _exclude_kw,
    "feeds": {
        "俄罗斯": [
            {"url": gnews_url("Russia sanctions SWIFT oil price cap export control 2026"), "tag": "GNews | RU Sanctions"},
            {"url": gnews_url("Russia economy ruble trade China oil gas pipeline"), "tag": "GNews | RU Economy"},
            {"url": gnews_url("Russia sanctions evasion circumvention transshipment"), "tag": "GNews | RU Evasion"},
        ],
        "中亚": [
            {"url": gnews_url("Kazakhstan trade investment China Belt Road uranium mining"), "tag": "GNews | KZ Trade/BRI"},
            {"url": gnews_url("Uzbekistan economy trade investment reform manufacturing"), "tag": "GNews | UZ Economy"},
            {"url": gnews_url("Central Asia China Belt Road investment infrastructure"), "tag": "GNews | Central Asia/BRI"},
        ],
        "白俄罗斯+能源": [
            {"url": gnews_url("Belarus sanctions trade economy potassium"), "tag": "GNews | BY Sanctions"},
            {"url": gnews_url("CIS energy oil gas pipeline LNG export"), "tag": "GNews | CIS Energy"},
        ],
        "战争+地缘": [
            {"url": gnews_url("Russia Ukraine war frontline ceasefire negotiation 2026"), "tag": "GNews | RU-UA War"},
            {"url": gnews_url("Georgia Armenia Azerbaijan conflict relation Russia"), "tag": "GNews | Caucasus"},
        ],
        "基础设施+科技": [
            {"url": gnews_url("Central Asia infrastructure railway project technology park 2026"), "tag": "GNews | CA Infra"},
        ],
        "气候+人口": [
            {"url": gnews_url("Central Asia water dispute Aral Sea climate drought"), "tag": "GNews | CA Climate/Water"},
            {"url": gnews_url("Central Asia demographic labor migration Russia Kazakhstan"), "tag": "GNews | CA Demo"},
        ],
        "大国关系": [
            {"url": gnews_url("US Central Asia relation trade cooperation 2026"), "tag": "GNews | US-CA"},
            {"url": gnews_url("China Central Asia summit cooperation BRI investment"), "tag": "GNews | China-CA"},
            {"url": gnews_url("Russia influence Central Asia Eurasian Economic Union"), "tag": "GNews | RU-CA"},
        ],
        "本地语言搜索": [
            {"url": gnews_url("Россия экономика торговля инвестиции экспорт", hl="ru", gl="RU", ceid="RU:ru"), "tag": "GNews | RU Русский"},
            {"url": gnews_url("Казахстан экономика торговля инвестиции", hl="ru", gl="KZ", ceid="KZ:ru"), "tag": "GNews | KZ Русский"},
            {"url": gnews_url("Україна економіка торгівля інвестиції експорт", hl="uk", gl="UA", ceid="UA:uk"), "tag": "GNews | UA Українська"},
        ],
        "独立RSS源": [
            {"url": "https://www.themoscowtimes.com/rss/news", "tag": "Moscow Times"},
            {"url": "https://www.ukrinform.net/rss", "tag": "Ukrinform EN"},
        ],
        "信号性查询": [
            {"url": gnews_url('"military escalation" "nuclear threat" Russia Ukraine'), "tag": "GNews | Signal: RU-UA"},
            {"url": gnews_url('"cyber attack" "energy crisis" Russia CIS pipeline'), "tag": "GNews | Signal: CIS Energy"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
