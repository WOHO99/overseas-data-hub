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
_core_kw, _important_kw, _aux_kw, _signal_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "拉美深度",
    "output_file": "latam.json",
    "max_articles": 300,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "feeds": {
        "墨西哥": [
            {"url": gnews_url("Mexico nearshoring manufacturing export tariff USMCA factory"), "tag": "GNews | MX Nearshoring"},
            {"url": gnews_url("Mexico auto manufacturing export automotive investment"), "tag": "GNews | MX Auto/Mfg"},
            {"url": gnews_url("Mexico economy GDP trade FDI infrastructure energy"), "tag": "GNews | MX Economy"},
        ],
        "巴西": [
            {"url": gnews_url("Brazil commodity export soybean iron ore China trade"), "tag": "GNews | BR Commodity/China"},
            {"url": gnews_url("Brazil economy GDP inflation central bank BCB"), "tag": "GNews | BR Economy"},
            {"url": gnews_url("Brazil lithium mining critical minerals investment export"), "tag": "GNews | BR Lithium/Mining"},
        ],
        "阿根廷+智利+其他": [
            {"url": gnews_url("Argentina economy IMF debt peso inflation trade"), "tag": "GNews | AR Economy/IMF"},
            {"url": gnews_url("Chile lithium mining export trade copper investment"), "tag": "GNews | CL Lithium/Copper"},
            {"url": gnews_url("Colombia Peru trade mining investment economy"), "tag": "GNews | CO/PE Trade"},
            {"url": gnews_url("Latin America China trade investment infrastructure BRI"), "tag": "GNews | LatAm-China/BRI"},
        ],
        "政治+社会": [
            {"url": gnews_url("Latin America political crisis election protest policy change 2026"), "tag": "GNews | LatAm Politics"},
            {"url": gnews_url("Venezuela oil economy sanctions political crisis"), "tag": "GNews | Venezuela"},
        ],
        "基础设施+科技": [
            {"url": gnews_url("Latin America infrastructure port railway modernization 2026"), "tag": "GNews | LatAm Infra"},
            {"url": gnews_url("Latin America fintech technology hub startup Brazil Mexico"), "tag": "GNews | LatAm Tech"},
        ],
        "气候+人口": [
            {"url": gnews_url("Amazon deforestation drought climate change Brazil"), "tag": "GNews | Amazon Climate"},
            {"url": gnews_url("Latin America demographic urbanization migration"), "tag": "GNews | LatAm Demo"},
        ],
        "大国关系": [
            {"url": gnews_url("US Latin America trade relation summit policy 2026"), "tag": "GNews | US-LatAm"},
            {"url": gnews_url("China Latin America trade investment BRI critical minerals"), "tag": "GNews | China-LatAm"},
        ],
        "本地语言搜索": [
            {"url": gnews_url("Brasil exportação comércio investimento economia", hl="pt-BR", gl="BR", ceid="BR:pt-419"), "tag": "GNews | BR Português"},
            {"url": gnews_url("México exportación comercio inversión economía", hl="es-419", gl="MX", ceid="MX:es-419"), "tag": "GNews | MX Español"},
            {"url": gnews_url("Argentina exportación comercio inversión economía", hl="es-419", gl="AR", ceid="AR:es-419"), "tag": "GNews | AR Español"},
            {"url": gnews_url("Colombia exportación comercio inversión economía", hl="es-419", gl="CO", ceid="CO:es-419"), "tag": "GNews | CO Español"},
        ],
        "独立RSS源": [
            {"url": "https://en.mercopress.com/rss/", "tag": "MercoPress"},
            {"url": "https://valor.globo.com/rss", "tag": "Valor Econômico"},
        ],
        "信号性查询": [
            {"url": gnews_url('"supply disruption" Latin America mining commodity'), "tag": "GNews | Signal: LatAm Disrupt"},
            {"url": gnews_url('"political crisis" "debt default" Latin America'), "tag": "GNews | Signal: LatAm Crisis"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
