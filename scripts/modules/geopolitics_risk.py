#!/usr/bin/env python3
"""
geopolitics_risk.py — 全球治理与地缘风险模块
覆盖：制裁、战争、条约、选举、网络攻击，不受国别限制
"""

import sys
import os
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_module, gnews_url, load_keywords

_config_dir = os.path.join(_scripts_dir, "config")
_module_name = "geopolitics_risk"
_core_kw, _important_kw, _aux_kw, _signal_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "全球治理与地缘风险",
    "output_file": "geopolitics_risk.json",
    "max_articles": 350,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
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
        "信号性查询": [
            {"url": gnews_url('"emergency meeting" security council NATO defense'), "tag": "GNews | Signal: Emergency"},
            {"url": gnews_url('"unprecedented" military escalation red line ultimatum'), "tag": "GNews | Signal: Escalation"},
            {"url": gnews_url('"first ever" treaty summit diplomatic breakthrough'), "tag": "GNews | Signal: Diplomacy First"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
