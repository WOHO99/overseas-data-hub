#!/usr/bin/env python3
"""
region_middle_east.py — 中东深度模块
v3.3升级：增加政治稳定、基础设施、科技、气候、人口、大国关系+阿拉伯语搜索
"""

import sys
import os
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_module, gnews_url, load_keywords

_config_dir = os.path.join(_scripts_dir, "config")
_module_name = "region_middle_east"
_core_kw, _important_kw, _aux_kw, _signal_kw, _exclude_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "中东深度",
    "output_file": "middle_east.json",
    "max_articles": 800,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "exclude_keywords": _exclude_kw,
    "feeds": {
        "海湾国家": [
            {"url": gnews_url("Saudi Arabia Vision 2030 investment trade export diversification", hl="en-AE", gl="AE", ceid="AE:en"), "tag": "GNews | SA Vision 2030"},
            {"url": gnews_url("UAE Dubai trade logistics free zone investment DIFC", hl="en-AE", gl="AE", ceid="AE:en"), "tag": "GNews | UAE Trade/FTZ"},
            {"url": gnews_url("Qatar investment LNG trade energy economy", hl="en-AE", gl="AE", ceid="AE:en"), "tag": "GNews | QA Trade/LNG"},
            {"url": gnews_url("Gulf sovereign wealth fund PIF ADIA investment global", hl="en-AE", gl="AE", ceid="AE:en"), "tag": "GNews | Gulf SWF"},
            {"url": gnews_url("Saudi NEOM construction infrastructure project", hl="en-AE", gl="AE", ceid="AE:en"), "tag": "GNews | SA NEOM/Infra"},
        ],
        "伊朗+土耳其": [
            {"url": gnews_url("Iran sanctions oil export trade SWIFT nuclear", hl="en-AE", gl="AE", ceid="AE:en"), "tag": "GNews | Iran Sanctions"},
            {"url": gnews_url("Turkey economy trade inflation lira Erdogan policy", hl="en-AE", gl="AE", ceid="AE:en"), "tag": "GNews | TR Economy"},
            {"url": gnews_url("Turkey manufacturing export textile automotive", hl="en-AE", gl="AE", ceid="AE:en"), "tag": "GNews | TR Mfg/Export"},
        ],
        "以色列+其他": [
            {"url": gnews_url("Israel tech startup investment trade cybersecurity", hl="en-AE", gl="AE", ceid="AE:en"), "tag": "GNews | IL Tech/Trade"},
            {"url": gnews_url("Middle East logistics port shipping trade corridor", hl="en-AE", gl="AE", ceid="AE:en"), "tag": "GNews | ME Logistics"},
            {"url": gnews_url("Middle East China trade investment Belt Road BRI", hl="en-AE", gl="AE", ceid="AE:en"), "tag": "GNews | ME-China/BRI"},
        ],
        "政治+安全": [
            {"url": gnews_url("Middle East conflict Gaza Israel ceasefire Red Sea Houthi", hl="en-AE", gl="AE", ceid="AE:en"), "tag": "GNews | ME Conflict"},
            {"url": gnews_url("Saudi Israel normalization Abraham Accord diplomacy", hl="en-AE", gl="AE", ceid="AE:en"), "tag": "GNews | SA-IL Normalization"},
            {"url": gnews_url("Iran nuclear deal JCPOA diplomacy sanctions relief", hl="en-AE", gl="AE", ceid="AE:en"), "tag": "GNews | Iran Nuclear Deal"},
        ],
        "基础设施+科技": [
            {"url": gnews_url("Gulf infrastructure megaproject port desalination solar energy", hl="en-AE", gl="AE", ceid="AE:en"), "tag": "GNews | Gulf Infra"},
            {"url": gnews_url("Dubai technology hub AI startup innovation", hl="en-AE", gl="AE", ceid="AE:en"), "tag": "GNews | Gulf Tech"},
        ],
        "气候+人口": [
            {"url": gnews_url("Middle East heatwave drought water crisis energy", hl="en-AE", gl="AE", ceid="AE:en"), "tag": "GNews | ME Climate"},
            {"url": gnews_url("MENA youth unemployment population demographic", hl="en-AE", gl="AE", ceid="AE:en"), "tag": "GNews | ME Demo"},
        ],
        "大国关系": [
            {"url": gnews_url("US Gulf cooperation trade investment defense"), "tag": "GNews | US-Gulf"},
            {"url": gnews_url("China Gulf trade investment BRI Saudi UAE"), "tag": "GNews | China-Gulf"},
        ],
        "本地语言搜索": [
            {"url": gnews_url("السعودية استثمار تجارة تصدير اقتصاد", hl="ar", gl="SA", ceid="SA:ar"), "tag": "GNews | SA العربية"},
            {"url": gnews_url("الإمارات اقتصاد تجارة استثمار", hl="ar", gl="AE", ceid="AE:ar"), "tag": "GNews | UAE العربية"},
            {"url": gnews_url("Türkiye ekonomi ticaret ihracat yatırım", hl="tr", gl="TR", ceid="TR:tr"), "tag": "GNews | TR Türkçe"},
            {"url": gnews_url("ישראל כלכלה מסחר השקעה יצוא", hl="he", gl="IL", ceid="IL:he"), "tag": "GNews | IL עברית"},
        ],
        "独立RSS源": [
            {"url": "https://www.aljazeera.com/xml/rss/all.xml", "tag": "Al Jazeera"},
            {"url": "https://www.dailysabah.com/rssFeed/world", "tag": "Daily Sabah"},
            {"url": "https://www.timesofisrael.com/rss/feedsfrontpage.xml", "tag": "Times of Israel"},
        ],
        "信号性查询": [
            {"url": gnews_url('"supply disruption" oil gas Red Sea Suez Middle East'), "tag": "GNews | Signal: ME Disrupt"},
            {"url": gnews_url('"military escalation" "unprecedented" Middle East'), "tag": "GNews | Signal: ME Escalation"},
        ],
        "专题精选": [
            {"url": gnews_url(topic="WORLD", hl="en-US", gl="AE", ceid="AE:en"), "tag": "GNews Topic | WORLD(AE)"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
