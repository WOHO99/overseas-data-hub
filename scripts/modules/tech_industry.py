#!/usr/bin/env python3
"""
tech_industry.py — 全球科技与工业前沿模块
覆盖：半导体、AI、电动车/电池、生物科技、航天、新材料、量子计算
无论地域，只追前沿
v3.5: Batch D新增19个直连RSS源(Hacker News/博客/科技媒体/安全/科学)
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
        "Track17半导体AI专项": [
            # v3.4新增(07/21): Track17 A股池技术股深度查询
            # 技术/产品视角,与chinese_firms_overseas的业务合规视角互补
            {"url": gnews_url("SMIC 7nm 5nm foundry Huawei HiSilicon Kirin chip breakthrough"), "tag": "GNews | SMIC Tech T17"},
            {"url": gnews_url("Cambricon AI inference training chip MLU performance datacenter 2026"), "tag": "GNews | Cambricon Tech T17"},
            {"url": gnews_url("Loongson 3A6000 3C5000 CPU MIPS LoongArch performance benchmark"), "tag": "GNews | Loongson Tech T17"},
            {"url": gnews_url("Hygon DCU deep learning accelerator CUDA Copicker AI compute"), "tag": "GNews | Hygon Tech T17"},
            {"url": gnews_url("Naura etching PVD ALD semiconductor equipment domestic China 2026"), "tag": "GNews | Naura Tech T17"},
            {"url": gnews_url("JCET Chiplet HBM fan-out packaging test 2026"), "tag": "GNews | JCET Tech T17"},
            {"url": gnews_url("Sugon supercomputer server HPC liquid cooling liquid immersion 2026"), "tag": "GNews | Sugon Tech T17"},
            {"url": gnews_url("QuantumCTek QKD quantum communication distribution network China 2026"), "tag": "GNews | QuantumCTek Tech T17"},
            {"url": gnews_url("Will Semiconductor OmniVision image sensor 50MP 200MP smartphone CIS 2026"), "tag": "GNews | Will Semi Tech T17"},
            {"url": gnews_url("ZTE 5G 6G base station Open RAN telecom equipment overseas"), "tag": "GNews | ZTE Tech T17"},
            {"url": gnews_url("GigaDevice NAND flash MCU GD32 microcontroller China"), "tag": "GNews | GigaDevice Tech T17"},
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
        ],
        "独立RSS源": [
            # DEAD: {"url": "https://arstechnica.com/rss", "tag": "Ars Technica (old)"},
            # DEAD: {"url": "https://www.wired.com/feed/rss", "tag": "Wired"},
        ],
        "科技媒体RSS(D)": [
            # v3.5 Batch D: 科技新闻媒体
            {"url": "http://feeds.arstechnica.com/arstechnica/index", "tag": "Ars Technica Index"},
            {"url": "http://feeds.arstechnica.com/arstechnica/science", "tag": "Ars Technica Science"},
            {"url": "https://www.technologyreview.com/feed/", "tag": "MIT Tech Review"},
            {"url": "https://www.newscientist.com/feed/home", "tag": "New Scientist"},
            # DEAD: {"url": "https://www.nasa.gov/rss/dyn/breaking_news.rss", "tag": "NASA Breaking News"},
            # DEAD: {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml", "tag": "NYT Technology"},
            {"url": "https://feeds.reuters.com/reuters/technologyNews", "tag": "Reuters Technology"},
        ],
        "开发者社区RSS(D)": [
            # v3.5 Batch D: 开发者社区/聚合器
            # DEAD: {"url": "https://news.ycombinator.com/rss", "tag": "Hacker News Top"},
            {"url": "https://news.ycombinator.com/newest?rss", "tag": "Hacker News New"},
            {"url": "https://stackoverflow.blog/feed/", "tag": "Stack Overflow Blog"},
            # DEAD: {"url": "https://github.blog/feed/", "tag": "GitHub Blog"},
            # DEAD: {"url": "https://lwn.net/headlines/rss", "tag": "LWN Headlines"},
        ],
        "技术博客RSS(D)": [
            # v3.5 Batch D: 个人/公司技术博客
            {"url": "https://blog.codinghorror.com/rss/", "tag": "Coding Horror"},
            {"url": "https://www.joelonsoftware.com/feed/", "tag": "Joel on Software"},
            {"url": "https://martinfowler.com/feed.atom", "tag": "Martin Fowler"},
            {"url": "https://simonwillison.net/atom/everything/", "tag": "Simon Willison"},
            {"url": "https://jvns.ca/atom.xml", "tag": "Julia Evans"},
            {"url": "https://danluu.com/atom.xml", "tag": "Dan Luu"},
        ],
        "平台专精RSS(D)": [
            # v3.5 Batch D: Apple/Linux/硬件专精
            # DEAD: {"url": "https://9to5mac.com/feed/", "tag": "9to5Mac"},
            # DEAD: {"url": "https://www.macrumors.com/macrumors.xml", "tag": "MacRumors"},
            # DEAD: {"url": "https://www.omgubuntu.co.uk/feed", "tag": "OMG! Ubuntu"},
            # DEAD: {"url": "https://www.phoronix.com/rss.php", "tag": "Phoronix"},
        ],
        "新增直连RSS(B)": [
            # v3.6 Batch B: 7源
            {"url": "https://stratechery.com/feed/", "tag": "Stratechery"},
            # DEAD: {"url": "https://www.theverge.com/rss/index.xml", "tag": "The Verge"},
            # DEAD: {"url": "https://openai.com/blog/rss.xml", "tag": "OpenAI Blog"},
            # DEAD: {"url": "https://deepmind.google/blog/rss.xml", "tag": "DeepMind Blog"},
            {"url": "https://feeds.feedburner.com/bloomberg-technology-news", "tag": "Bloomberg Technology"},
            {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10002647", "tag": "CNBC Technology"},
            {"url": "https://feeds.content.dowjones.io/public/rss/WSJD", "tag": "WSJ Tech"},
            # v3.6 RSS Library: 2源(科学)
            {"url": "http://feeds.nature.com/nature/rss/current", "tag": "Nature"},
            {"url": "https://www.science.org/rss/news_current.xml", "tag": "Science News"},
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
            # DEAD: {"url": "http://feeds.bbci.co.uk/news/technology/rss.xml", "tag": "BBC Tech"},
            # DEAD: {"url": "https://www.theguardian.com/technology/rss", "tag": "Guardian Tech"},
            {"url": "http://rss.cnn.com/rss/cnn_tech.rss", "tag": "CNN Tech"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
