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
_core_kw, _important_kw, _aux_kw, _signal_kw, _exclude_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "非洲深度",
    "output_file": "africa.json",
    "max_articles": 800,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "exclude_keywords": _exclude_kw,
    "feeds": {
        "主要经济体": [
            {"url": gnews_url("South Africa economy trade mining export GDP", hl="en-ZA", gl="ZA", ceid="ZA:en"), "tag": "GNews | ZA Economy"},
            {"url": gnews_url("Nigeria economy oil trade investment GDP", hl="en-NG", gl="NG", ceid="NG:en"), "tag": "GNews | NG Economy"},
            {"url": gnews_url("Kenya economy trade fintech investment startup", hl="en-KE", gl="KE", ceid="KE:en"), "tag": "GNews | KE Economy/Fintech"},
            {"url": gnews_url("Egypt economy trade Suez Canal investment IMF", hl="en-EG", gl="EG", ceid="EG:en"), "tag": "GNews | EG Economy"},
            {"url": gnews_url("Ethiopia economy manufacturing investment trade", hl="en-ET", gl="ET", ceid="ET:en"), "tag": "GNews | ET Economy/Mfg"},
        ],
        "矿业+中国": [
            {"url": gnews_url("Congo DRC cobalt mining export China investment child labor", hl="en-CD", gl="CD", ceid="CD:en"), "tag": "GNews | CD Cobalt"},
            {"url": gnews_url("Africa China investment infrastructure Belt Road BRI mining", hl="en-ZA", gl="ZA", ceid="ZA:en"), "tag": "GNews | Africa-China/BRI"},
            {"url": gnews_url("Africa critical minerals cobalt lithium copper export EU US", hl="en-ZA", gl="ZA", ceid="ZA:en"), "tag": "GNews | Africa Minerals"},
        ],
        "贸易+区域": [
            {"url": gnews_url("AfCFTA African Continental Free Trade Area implementation", hl="en-ZA", gl="ZA", ceid="ZA:en"), "tag": "GNews | AfCFTA"},
            {"url": gnews_url("AGOA Africa trade preference US renewal 2026", hl="en-ZA", gl="ZA", ceid="ZA:en"), "tag": "GNews | AGOA"},
            {"url": gnews_url("Africa debt crisis IMF World Bank default restructuring", hl="en-ZA", gl="ZA", ceid="ZA:en"), "tag": "GNews | Africa Debt/IMF"},
        ],
        "政治+冲突": [
            {"url": gnews_url("Africa conflict coup political crisis instability 2026", hl="en-ZA", gl="ZA", ceid="ZA:en"), "tag": "GNews | Africa Conflict"},
            {"url": gnews_url("Sahel conflict terrorism Mali Burkina Faso Niger", hl="fr-ML", gl="ML", ceid="ML:fr"), "tag": "GNews | Sahel Crisis"},
            {"url": gnews_url("Sudan conflict civil war humanitarian crisis", hl="ar-SD", gl="SD", ceid="SD:ar"), "tag": "GNews | Sudan Crisis"},
        ],
        "基础设施+科技": [
            {"url": gnews_url("Africa infrastructure port expansion railway project 2026", hl="en-ZA", gl="ZA", ceid="ZA:en"), "tag": "GNews | Africa Infra"},
            {"url": gnews_url("Africa technology mobile money fintech innovation hub", hl="en-KE", gl="KE", ceid="KE:en"), "tag": "GNews | Africa Tech"},
        ],
        "气候+人口": [
            {"url": gnews_url("Africa drought flood climate change Sahara East Africa", hl="en-KE", gl="KE", ceid="KE:en"), "tag": "GNews | Africa Climate"},
            {"url": gnews_url("Africa youth population unemployment urbanization", hl="en-ZA", gl="ZA", ceid="ZA:en"), "tag": "GNews | Africa Demo"},
        ],
        "大国关系": [
            {"url": gnews_url("US Africa summit trade investment partnership 2026"), "tag": "GNews | US-Africa"},
            {"url": gnews_url("EU Africa partnership trade investment critical minerals"), "tag": "GNews | EU-Africa"},
            {"url": gnews_url("China Africa FOCAC trade investment infrastructure BRI"), "tag": "GNews | China-Africa FOCAC"},
        ],
        "独立RSS源": [
            {"url": "https://www.dailymaverick.co.za/rss/", "tag": "Daily Maverick ZA"},
            {"url": "https://www.theeastafrican.co.ke/rss", "tag": "The East African"},
        ],
        "本地语言搜索": [
            {"url": gnews_url("South Africa trade export investment economy mining", hl="en-ZA", gl="ZA", ceid="ZA:en"), "tag": "GNews | ZA English"},
            {"url": gnews_url("مصر اقتصاد تجارة استثمار تصدير", hl="ar", gl="EG", ceid="EG:ar"), "tag": "GNews | EG العربية"},
            {"url": gnews_url("Nigeria commerce investissement pétrole exportation", hl="fr-NG", gl="NG", ceid="NG:fr"), "tag": "GNews | NG Français"},
            {"url": gnews_url("Congo RDC mines cobalt investissement Chine", hl="fr-CD", gl="CD", ceid="CD:fr"), "tag": "GNews | CD Français"},
            {"url": gnews_url("Sénégal économie commerce investissement", hl="fr-SN", gl="SN", ceid="SN:fr"), "tag": "GNews | SN Français"},
            {"url": gnews_url("Côte d'Ivoire économie commerce cacao investissement", hl="fr-CI", gl="CI", ceid="CI:fr"), "tag": "GNews | CI Français"},
            {"url": gnews_url("Kenya biashara uwekezaji biashara ya kimataifa", hl="sw", gl="KE", ceid="KE:sw"), "tag": "GNews | KE Kiswahili"},
            {"url": gnews_url("Angola economia comércio petróleo investimento", hl="pt-AO", gl="AO", ceid="AO:pt"), "tag": "GNews | AO Português"},
            {"url": gnews_url("Moçambique economia comércio gás investimento", hl="pt-MZ", gl="MZ", ceid="MZ:pt"), "tag": "GNews | MZ Português"},
        ],
        "信号性查询": [
            {"url": gnews_url('"conflict escalation" "coup" Africa political crisis'), "tag": "GNews | Signal: Africa Crisis"},
            {"url": gnews_url('"famine" "record displacement" "debt default" Africa'), "tag": "GNews | Signal: Africa Emergency"},
        ],
        "专题精选": [
            {"url": gnews_url(topic="WORLD", hl="en-US", gl="ZA", ceid="ZA:en"), "tag": "GNews Topic | WORLD(ZA)"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
