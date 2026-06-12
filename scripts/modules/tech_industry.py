#!/usr/bin/env python3
"""
tech_industry.py — 全球科技与工业前沿模块
覆盖：半导体、AI、电动车/电池、生物科技、航天、新材料、量子计算
无论地域，只追前沿
"""

import sys
import os
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_module, gnews_url, load_keywords

_config_dir = os.path.join(_scripts_dir, "config")
_module_name = "tech_industry"
_core_kw, _important_kw, _aux_kw, _signal_kw, _exclude_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "全球科技与工业前沿",
    "output_file": "tech_industry.json",
    "max_articles": 500,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "exclude_keywords": _exclude_kw,
    "feeds": {
        "半导体": [
            {"url": gnews_url("semiconductor chip foundry TSMC Samsung Intel ASML"), "tag": "GNews | Chip Foundry"},
            {"url": gnews_url('"semiconductor equipment" export ban China restriction'), "tag": "GNews | Chip Export Ban"},
            {"url": gnews_url("CHIPS Act EU Chips Act Japan chip fab investment"), "tag": "GNews | Chip Fab Policy"},
            {"url": gnews_url("TSMC factory US Japan Germany Arizona Kumamoto"), "tag": "GNews | TSMC Global Fab"},
            {"url": gnews_url("chip shortage automotive supply 2026"), "tag": "GNews | Auto Chip Shortage"},
            {"url": gnews_url("rare earth magnet semiconductor supply chain China"), "tag": "GNews | Rare Earth/Chip SC"},
        ],
        "AI": [
            {"url": gnews_url("artificial intelligence regulation ban deepfake generative AI"), "tag": "GNews | AI Regulation"},
            {"url": gnews_url("AI chip export control NVIDIA compute restriction"), "tag": "GNews | AI Chip Control"},
            {"url": gnews_url("AI safety summit frontier model regulation 2026"), "tag": "GNews | AI Safety"},
            {"url": gnews_url("generative AI enterprise adoption productivity impact"), "tag": "GNews | GenAI Enterprise"},
            {"url": gnews_url("AI copyright lawsuit training data fair use"), "tag": "GNews | AI Copyright"},
        ],
        "电动车+电池": [
            {"url": gnews_url("electric vehicle battery solid state charging infrastructure 2026"), "tag": "GNews | EV/Battery"},
            {"url": gnews_url("BYD Tesla global expansion market share competition"), "tag": "GNews | EV Competition"},
            {"url": gnews_url("lithium iron phosphate battery cost manufacturing"), "tag": "GNews | LFP Battery"},
            {"url": gnews_url("EV tariff US EU China import restriction"), "tag": "GNews | EV Tariff"},
            {"url": gnews_url("sodium ion battery alternative lithium 2026"), "tag": "GNews | Na-ion Battery"},
        ],
        "生物+航天": [
            {"url": gnews_url("biotechnology gene editing CRISPR clinical trial FDA approval"), "tag": "GNews | Biotech"},
            {"url": gnews_url("weight loss drug GLP-1 Ozempic pharmaceutical"), "tag": "GNews | GLP-1 Drug"},
            {"url": gnews_url("space industry launch satellite Starlink military SpaceX"), "tag": "GNews | Space"},
            {"url": gnews_url("quantum computing breakthrough error correction 2026"), "tag": "GNews | Quantum"},
        ],
        "本地语言搜索": [
            {"url": gnews_url("芯片 半导体 出口管制 人工智能 制裁", hl="zh-CN", gl="CN", ceid="CN:zh-Hans"), "tag": "GNews | CN 芯片/AI"},
            {"url": gnews_url("반도체 칩 수출 통제 AI 규제", hl="ko", gl="KR", ceid="KR:ko"), "tag": "GNews | KR 반도체"},
        ],
        "独立RSS源": [
            {"url": "https://arstechnica.com/rss", "tag": "Ars Technica"},
            {"url": "https://www.wired.com/feed/rss", "tag": "Wired"},
        ],
        "信号性查询": [
            {"url": gnews_url('"first ever" breakthrough technology semiconductor AI'), "tag": "GNews | Signal: First Ever Tech"},
            {"url": gnews_url('"unprecedented" "record high" chip AI technology'), "tag": "GNews | Signal: Record Tech"},
            {"url": gnews_url('"supply disruption" semiconductor battery critical technology'), "tag": "GNews | Signal: Tech Disruption"},
        ],
        "专题精选": [
            {"url": gnews_url(topic="TECHNOLOGY"), "tag": "GNews Topic | TECH(US)"},
        ],
        "科技权威RSS": [
            {"url": "http://feeds.bbci.co.uk/news/technology/rss.xml", "tag": "BBC Tech"},
            {"url": "https://www.theguardian.com/technology/rss", "tag": "Guardian Tech"},
            {"url": "http://rss.cnn.com/rss/cnn_tech.rss", "tag": "CNN Tech"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
