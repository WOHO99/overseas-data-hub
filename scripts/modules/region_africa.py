#!/usr/bin/env python3
"""
region_africa.py — 非洲深度模块
v3.3升级：增加政治稳定、基础设施、科技、气候、人口、大国关系
"""

import sys
import os
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_module, gnews_url, load_keywords

_config_dir = os.path.join(_scripts_dir, "config")
_module_name = "region_africa"
_core_kw, _important_kw, _aux_kw, _signal_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "非洲深度",
    "output_file": "africa.json",
    "max_articles": 250,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "feeds": {
        "主要经济体": [
            {"url": gnews_url("South Africa economy trade mining export GDP"), "tag": "GNews | ZA Economy"},
            {"url": gnews_url("Nigeria economy oil trade investment GDP"), "tag": "GNews | NG Economy"},
            {"url": gnews_url("Kenya economy trade fintech investment startup"), "tag": "GNews | KE Economy/Fintech"},
            {"url": gnews_url("Egypt economy trade Suez Canal investment IMF"), "tag": "GNews | EG Economy"},
            {"url": gnews_url("Ethiopia economy manufacturing investment trade"), "tag": "GNews | ET Economy/Mfg"},
        ],
        "矿业+中国": [
            {"url": gnews_url("Congo DRC cobalt mining export China investment child labor"), "tag": "GNews | CD Cobalt"},
            {"url": gnews_url("Africa China investment infrastructure Belt Road BRI mining"), "tag": "GNews | Africa-China/BRI"},
            {"url": gnews_url("Africa critical minerals cobalt lithium copper export EU US"), "tag": "GNews | Africa Minerals"},
        ],
        "贸易+区域": [
            {"url": gnews_url("AfCFTA African Continental Free Trade Area implementation"), "tag": "GNews | AfCFTA"},
            {"url": gnews_url("AGOA Africa trade preference US renewal 2026"), "tag": "GNews | AGOA"},
            {"url": gnews_url("Africa debt crisis IMF World Bank default restructuring"), "tag": "GNews | Africa Debt/IMF"},
        ],
        "政治+冲突": [
            {"url": gnews_url("Africa conflict coup political crisis instability 2026"), "tag": "GNews | Africa Conflict"},
            {"url": gnews_url("Sahel conflict terrorism Mali Burkina Faso Niger"), "tag": "GNews | Sahel Crisis"},
            {"url": gnews_url("Sudan conflict civil war humanitarian crisis"), "tag": "GNews | Sudan Crisis"},
        ],
        "基础设施+科技": [
            {"url": gnews_url("Africa infrastructure port expansion railway project 2026"), "tag": "GNews | Africa Infra"},
            {"url": gnews_url("Africa technology mobile money fintech innovation hub"), "tag": "GNews | Africa Tech"},
        ],
        "气候+人口": [
            {"url": gnews_url("Africa drought flood climate change Sahara East Africa"), "tag": "GNews | Africa Climate"},
            {"url": gnews_url("Africa youth population unemployment urbanization"), "tag": "GNews | Africa Demo"},
        ],
        "大国关系": [
            {"url": gnews_url("US Africa summit trade investment partnership 2026"), "tag": "GNews | US-Africa"},
            {"url": gnews_url("EU Africa partnership trade investment critical minerals"), "tag": "GNews | EU-Africa"},
            {"url": gnews_url("China Africa FOCAC trade investment infrastructure BRI"), "tag": "GNews | China-Africa FOCAC"},
        ],
        "信号性查询": [
            {"url": gnews_url('"conflict escalation" "coup" Africa political crisis'), "tag": "GNews | Signal: Africa Crisis"},
            {"url": gnews_url('"famine" "record displacement" "debt default" Africa'), "tag": "GNews | Signal: Africa Emergency"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
