#!/usr/bin/env python3
"""
region_south_asia.py — 南亚深度模块
v3.3升级：增加政治稳定、基础设施、科技、气候、人口、大国关系+印地语/孟加拉语搜索
"""

import sys
import os
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_module, gnews_url, load_keywords

_config_dir = os.path.join(_scripts_dir, "config")
_module_name = "region_south_asia"
_core_kw, _important_kw, _aux_kw, _signal_kw, _exclude_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "南亚深度",
    "output_file": "south_asia.json",
    "max_articles": 300,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "exclude_keywords": _exclude_kw,
    "feeds": {
        "印度": [
            {"url": gnews_url("India manufacturing export PLI scheme trade FDI 2026"), "tag": "GNews | IN Mfg/PLI"},
            {"url": gnews_url("India trade tariff US EU agreement negotiation"), "tag": "GNews | IN Trade/Tariff"},
            {"url": gnews_url("India pharmaceutical export drug regulation FDA"), "tag": "GNews | IN Pharma"},
            {"url": gnews_url("India IT services tech outsourcing H-1B visa"), "tag": "GNews | IN IT/Visa"},
            {"url": gnews_url("India economy GDP RBI monetary policy inflation"), "tag": "GNews | IN Economy/RBI"},
            {"url": gnews_url("India semiconductor fab plant investment Tata"), "tag": "GNews | IN Semiconductor"},
        ],
        "孟加拉": [
            {"url": gnews_url("Bangladesh garment export factory trade tariff GSP"), "tag": "GNews | BD Garment/GSP"},
            {"url": gnews_url("Bangladesh economy GDP IMF loan textile"), "tag": "GNews | BD Economy"},
        ],
        "巴基斯坦": [
            {"url": gnews_url("Pakistan trade economy IMF debt CPEC China"), "tag": "GNews | PK Economy/CPEC"},
        ],
        "斯里兰卡": [
            {"url": gnews_url("Sri Lanka economy debt IMF recovery trade export"), "tag": "GNews | LK Economy/IMF"},
        ],
        "政治+社会": [
            {"url": gnews_url("India political stability protest election policy change 2026"), "tag": "GNews | IN Politics"},
            {"url": gnews_url("Pakistan political crisis election instability"), "tag": "GNews | PK Politics"},
            {"url": gnews_url("Bangladesh political unrest protest factory"), "tag": "GNews | BD Politics"},
        ],
        "基础设施+科技": [
            {"url": gnews_url("India infrastructure project port railway expressway 2026"), "tag": "GNews | IN Infra"},
            {"url": gnews_url("India technology hub Bangalore startup innovation"), "tag": "GNews | IN Tech Hub"},
        ],
        "气候+人口": [
            {"url": gnews_url("South Asia heatwave monsoon drought flood climate 2026"), "tag": "GNews | SA Climate"},
            {"url": gnews_url("India demographic youth population employment unemployment"), "tag": "GNews | IN Demo"},
        ],
        "大国关系": [
            {"url": gnews_url("India US trade relation Quad strategic partnership"), "tag": "GNews | IN-US/Quad"},
            {"url": gnews_url("India China border tension trade relation"), "tag": "GNews | IN-CN Relation"},
        ],
        "本地语言搜索": [
            {"url": gnews_url("भारत निर्यात व्यापार निवेश अर्थव्यवस्था", hl="hi", gl="IN", ceid="IN:hi"), "tag": "GNews | IN हिन्दी"},
            {"url": gnews_url("বাংলাদেশ রপ্তানি বাণিজ্য অর্থনীতি", hl="bn", gl="BD", ceid="BD:bn"), "tag": "GNews | BD বাংলা"},
            {"url": gnews_url("پاکستان برآمد تجارت سرمایہ کاری معیشت", hl="ur", gl="PK", ceid="PK:ur"), "tag": "GNews | PK اردو"},
        ],
        "独立RSS源": [
            {"url": "https://www.thehindu.com/business/feeder/default.rss", "tag": "The Hindu Business"},
            {"url": "https://www.dawn.com/feed", "tag": "Dawn Pakistan"},
        ],
        "信号性查询": [
            {"url": gnews_url('"emergency meeting" India Pakistan South Asia'), "tag": "GNews | Signal: SA Emergency"},
            {"url": gnews_url('"unprecedented" "record high" India economy trade'), "tag": "GNews | Signal: IN Record"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
