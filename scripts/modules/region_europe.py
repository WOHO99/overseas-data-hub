#!/usr/bin/env python3
"""
region_europe.py — 欧洲深度模块
v3.3升级：增加政治稳定、基础设施、科技、气候、人口、大国关系+德/法语搜索
v3.4: Batch D新增3个瑞典移民局RSS源
"""

import sys
import os
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_module, gnews_url, load_keywords

_config_dir = os.path.join(_scripts_dir, "config")
_module_name = "region_europe"
_core_kw, _important_kw, _aux_kw, _signal_kw, _exclude_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "欧洲深度",
    "output_file": "europe.json",
    "max_articles": 800,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "exclude_keywords": _exclude_kw,
    "feeds": {
        "EU政策+制裁": [
            {"url": gnews_url("EU CBAM carbon border adjustment mechanism import tax", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews | EU CBAM"},
            {"url": gnews_url("EU sanctions Russia China export control trade restriction", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews | EU Sanctions"},
            {"url": gnews_url("EU Digital Services Act AI Act regulation compliance", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews | EU Digital Reg"},
            {"url": gnews_url("EU anti-subsidy investigation Chinese EV tariff", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews | EU EV Anti-subsidy"},
            {"url": gnews_url("EU supply chain due diligence deforestation EUDR", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews | EU SC/EUDR"},
            {"url": gnews_url("GDPR data protection cross-border transfer compliance", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews | GDPR/Transfer"},
        ],
        "主要国家": [
            {"url": gnews_url("Germany economy trade manufacturing export automotive", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews | DE Economy"},
            {"url": gnews_url("France economy trade investment regulation", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews | FR Economy"},
            {"url": gnews_url("UK economy trade regulation post-Brexit FTA", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews | UK Economy"},
            {"url": gnews_url("Netherlands trade port Rotterdam semiconductor ASML", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews | NL Trade/ASML"},
        ],
        "ECB+经济": [
            {"url": gnews_url("ECB interest rate monetary policy inflation euro zone", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews | ECB/Rate"},
            {"url": gnews_url("Europe economy GDP PMI recession growth 2026", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews | EU Economy"},
        ],
        "政治+社会": [
            {"url": gnews_url("Europe political stability election far right protest migration 2026", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews | EU Politics"},
            {"url": gnews_url("Ukraine reconstruction investment EU membership negotiation", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews | Ukraine Recon"},
            {"url": gnews_url("NATO defense spending Europe military budget 2026", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews | NATO/EU Defense"},
        ],
        "基础设施+科技": [
            {"url": gnews_url("Europe chip fab semiconductor factory investment 2026", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews | EU Chip Fab"},
            {"url": gnews_url("Europe technology hub innovation AI startup Berlin Paris", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews | EU Tech Hub"},
        ],
        "气候+人口": [
            {"url": gnews_url("Europe heatwave drought flood climate change energy crisis", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews | EU Climate"},
            {"url": gnews_url("Europe demographic aging population immigration policy", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews | EU Demo"},
            {"url": gnews_url("Europe energy transition renewable nuclear grid 2026", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews | EU Energy Trans"},
        ],
        "大国关系": [
            {"url": gnews_url("US EU trade relation tariff negotiation partnership"), "tag": "GNews | US-EU"},
            {"url": gnews_url("China EU relation trade investment sanction negotiation"), "tag": "GNews | China-EU"},
        ],
        "本地语言搜索": [
            {"url": gnews_url("Deutschland Wirtschaft Handel Investition Industrie", hl="de", gl="DE", ceid="DE:de"), "tag": "GNews | DE Deutsch"},
            {"url": gnews_url("France économie commerce investissement industrie", hl="fr", gl="FR", ceid="FR:fr"), "tag": "GNews | FR Français"},
            {"url": gnews_url("España economía comercio inversión industria", hl="es", gl="ES", ceid="ES:es"), "tag": "GNews | ES Español"},
            {"url": gnews_url("Italia economia commercio investimento industria", hl="it", gl="IT", ceid="IT:it"), "tag": "GNews | IT Italiano"},
        ],
        "独立RSS源": [
            {"url": "https://english.elpais.com/rss/elpais/rss_section.html?lst=english&s=business", "tag": "El País Business EN"},
            {"url": "https://www.corriere.it/rss/homepage.xml", "tag": "Corriere della Sera"},
            {"url": "http://feeds.bbci.co.uk/news/uk/rss.xml", "tag": "BBC UK"},
            {"url": "https://www.theguardian.com/uk/rss", "tag": "Guardian UK"},
            {"url": "https://www.lemonde.fr/rss/une.xml", "tag": "Le Monde"},
            {"url": "http://www.spiegel.de/schlagzeilen/index.rss", "tag": "Der Spiegel"},
            # v3.4 Batch D: 3个瑞典移民局RSS
            {"url": "https://www.migrationsverket.se/rss_en", "tag": "Swedish Migration Agency"},
            {"url": "https://www.migrationsverket.se/rss_employers", "tag": "Swedish Migration Employers"},
            {"url": "https://www.migrationsverket.se/rss_working", "tag": "Swedish Migration Work Permits"},
        ],
        "信号性查询": [
            {"url": gnews_url('"energy crisis" "supply disruption" Europe gas nuclear'), "tag": "GNews | Signal: EU Energy"},
            {"url": gnews_url('"regulatory crackdown" "sanctions announced" EU compliance'), "tag": "GNews | Signal: EU Sanction"},
        ],
        "专题精选": [
            {"url": gnews_url(topic="WORLD", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews Topic | WORLD(GB)"},
            {"url": gnews_url(topic="BUSINESS", hl="en-GB", gl="GB", ceid="GB:en"), "tag": "GNews Topic | BUSINESS(GB)"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
