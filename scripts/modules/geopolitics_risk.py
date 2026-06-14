#!/usr/bin/env python3
"""
geopolitics_risk.py — 全球治理与地缘风险模块
覆盖：制裁、战争、条约、选举、网络攻击，不受国别限制
v3.4: Batch A新增3个直连RSS源(Reuters World/Politico/Politico EU)
v3.5: Batch D新增4个直连RSS源(BBC Top/NYT World/WaPo World/The Atlantic)
"""

import sys
import os
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_module, gnews_url, load_keywords

_config_dir = os.path.join(_scripts_dir, "config")
_module_name = "geopolitics_risk"
_core_kw, _important_kw, _aux_kw, _signal_kw, _exclude_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "全球治理与地缘风险",
    "output_file": "geopolitics_risk.json",
    "max_articles": 500,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "exclude_keywords": _exclude_kw,
    "feeds": {
        "联合国+国际治理": [
            {"url": gnews_url("UN Security Council resolution sanctions vote veto"), "tag": "GNews | UNSC"},
            {"url": gnews_url("ICC ICJ war crime genocide ruling investigation"), "tag": "GNews | ICC/ICJ"},
            {"url": gnews_url("arms control treaty non-proliferation nuclear 2026"), "tag": "GNews | Arms Control"},
        ],
        "军事冲突": [
            {"url": gnews_url("Russia Ukraine ceasefire negotiation peace deal frontline"), "tag": "GNews | Russia-Ukraine"},
            {"url": gnews_url("Israel Gaza ceasefire hostage ceasefire negotiation"), "tag": "GNews | Israel-Gaza"},
            {"url": gnews_url("South China Sea Taiwan Strait military tension patrol"), "tag": "GNews | SCS/Taiwan"},
            {"url": gnews_url("Iran nuclear deal JCPOA diplomacy enrichment"), "tag": "GNews | Iran Nuclear"},
            {"url": gnews_url("North Korea missile nuclear test sanction China Russia"), "tag": "GNews | DPRK"},
            {"url": gnews_url("Middle East conflict escalation proxy war 2026"), "tag": "GNews | ME Conflict"},
        ],
        "选举+政策": [
            {"url": gnews_url("US election presidential policy trade tariff 2028 campaign"), "tag": "GNews | US Election"},
            {"url": gnews_url("NATO EU defense strategy military budget spending"), "tag": "GNews | NATO/EU Defense"},
            {"url": gnews_url("sanctions announced new restrictions trade embargo 2026"), "tag": "GNews | New Sanctions"},
        ],
        "网络+安全": [
            {"url": gnews_url("cyber attack critical infrastructure ransomware state-sponsored"), "tag": "GNews | Cyber Attack"},
            {"url": gnews_url("espionage counterintelligence spy diplomat expulsion"), "tag": "GNews | Espionage"},
            {"url": gnews_url("election interference disinformation deepfake foreign influence"), "tag": "GNews | Info War"},
        ],
        "本地语言搜索": [
            {"url": gnews_url("санкции война конфликт безопасность Россия", hl="ru", gl="RU", ceid="RU:ru"), "tag": "GNews | RU Санкции"},
            {"url": gnews_url("санкції війна конфлікт безпека Україна", hl="uk", gl="UA", ceid="UA:uk"), "tag": "GNews | UA Санкції"},
        ],
        "信号性查询": [
            {"url": gnews_url('"emergency meeting" security council NATO defense'), "tag": "GNews | Signal: Emergency"},
            {"url": gnews_url('"unprecedented" military escalation red line ultimatum'), "tag": "GNews | Signal: Escalation"},
            {"url": gnews_url('"first ever" treaty summit diplomatic breakthrough'), "tag": "GNews | Signal: Diplomacy First"},
        ],
        "专题精选": [
            {"url": gnews_url(topic="WORLD"), "tag": "GNews Topic | WORLD(US)"},
            {"url": gnews_url(topic="WORLD", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews Topic | WORLD(GB)"},
        ],
        "地缘权威RSS": [
            {"url": "http://feeds.bbci.co.uk/news/world/rss.xml", "tag": "BBC World"},
            {"url": "https://www.theguardian.com/world/rss", "tag": "Guardian World"},
            {"url": "https://www.theguardian.com/us-news/rss", "tag": "Guardian US"},
            {"url": "http://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml", "tag": "BBC North America"},
            {"url": "https://feeds.npr.org/1001/rss.xml", "tag": "NPR World"},
            # v3.4 Batch A: 3个新增直连RSS
            {"url": "http://feeds.reuters.com/Reuters/worldNews", "tag": "Reuters World"},
            {"url": "https://www.politico.com/rss", "tag": "Politico"},
            {"url": "https://www.politico.eu/feed/", "tag": "Politico EU"},
            # v3.5 Batch D: 4个新增直连RSS
            {"url": "http://feeds.bbci.co.uk/news/rss.xml", "tag": "BBC News Top"},
            {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "tag": "NYT World"},
            {"url": "https://feeds.washingtonpost.com/rss/world", "tag": "WaPo World"},
            {"url": "https://www.theatlantic.com/feed/all/", "tag": "The Atlantic"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
