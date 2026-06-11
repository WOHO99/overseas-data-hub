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
_core_kw, _important_kw, _aux_kw, _signal_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "中东深度",
    "output_file": "middle_east.json",
    "max_articles": 300,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "feeds": {
        "海湾国家": [
            {"url": gnews_url("Saudi Arabia Vision 2030 investment trade export diversification"), "tag": "GNews | SA Vision 2030"},
            {"url": gnews_url("UAE Dubai trade logistics free zone investment DIFC"), "tag": "GNews | UAE Trade/FTZ"},
            {"url": gnews_url("Qatar investment LNG trade energy economy"), "tag": "GNews | QA Trade/LNG"},
            {"url": gnews_url("Gulf sovereign wealth fund PIF ADIA investment global"), "tag": "GNews | Gulf SWF"},
            {"url": gnews_url("Saudi NEOM construction infrastructure project"), "tag": "GNews | SA NEOM/Infra"},
        ],
        "伊朗+土耳其": [
            {"url": gnews_url("Iran sanctions oil export trade SWIFT nuclear"), "tag": "GNews | Iran Sanctions"},
            {"url": gnews_url("Turkey economy trade inflation lira Erdogan policy"), "tag": "GNews | TR Economy"},
            {"url": gnews_url("Turkey manufacturing export textile automotive"), "tag": "GNews | TR Mfg/Export"},
        ],
        "以色列+其他": [
            {"url": gnews_url("Israel tech startup investment trade cybersecurity"), "tag": "GNews | IL Tech/Trade"},
            {"url": gnews_url("Middle East logistics port shipping trade corridor"), "tag": "GNews | ME Logistics"},
            {"url": gnews_url("Middle East China trade investment Belt Road BRI"), "tag": "GNews | ME-China/BRI"},
        ],
        "政治+安全": [
            {"url": gnews_url("Middle East conflict Gaza Israel ceasefire Red Sea Houthi"), "tag": "GNews | ME Conflict"},
            {"url": gnews_url("Saudi Israel normalization Abraham Accord diplomacy"), "tag": "GNews | SA-IL Normalization"},
            {"url": gnews_url("Iran nuclear deal JCPOA diplomacy sanctions relief"), "tag": "GNews | Iran Nuclear Deal"},
        ],
        "基础设施+科技": [
            {"url": gnews_url("Gulf infrastructure megaproject port desalination solar energy"), "tag": "GNews | Gulf Infra"},
            {"url": gnews_url("Dubai technology hub AI startup innovation"), "tag": "GNews | Gulf Tech"},
        ],
        "气候+人口": [
            {"url": gnews_url("Middle East heatwave drought water crisis energy"), "tag": "GNews | ME Climate"},
            {"url": gnews_url("MENA youth unemployment population demographic"), "tag": "GNews | ME Demo"},
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
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
