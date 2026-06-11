#!/usr/bin/env python3
"""
region_se_asia.py — 东南亚深度模块
v3.3升级：增加政治稳定、基础设施、科技、气候、人口、大国关系+越南语/印尼语搜索
"""

import sys
import os
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_module, gnews_url, load_keywords

_config_dir = os.path.join(_scripts_dir, "config")
_module_name = "region_se_asia"
_core_kw, _important_kw, _aux_kw, _signal_kw, _exclude_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "东南亚深度",
    "output_file": "se_asia.json",
    "max_articles": 400,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "exclude_keywords": _exclude_kw,
    "feeds": {
        "新加坡": [
            {"url": "https://www.straitstimes.com/rss/breaking-news", "tag": "Straits Times"},
            {"url": gnews_url("Singapore economy trade finance technology 2026"), "tag": "GNews | SG Economy"},
            {"url": gnews_url("Singapore MAS regulation fintech crypto"), "tag": "GNews | SG MAS/Fintech"},
        ],
        "越南": [
            {"url": gnews_url("Vietnam export manufacturing FDI trade 2026"), "tag": "GNews | VN Trade/FDI"},
            {"url": gnews_url("Vietnam tariff US EU market access textile electronics"), "tag": "GNews | VN Tariff"},
            {"url": gnews_url("Vietnam factory relocation China supply chain shift"), "tag": "GNews | VN Factory Shift"},
            {"url": gnews_url("Vietnam economy GDP growth real estate banking"), "tag": "GNews | VN Economy"},
            {"url": gnews_url("xuất khẩu thuế quan đầu tư FDI Việt Nam", hl="vi", gl="VN", ceid="VN:vi"), "tag": "GNews | VN Tiếng Việt"},
        ],
        "印尼": [
            {"url": "https://www.thejakartapost.com/rss", "tag": "Jakarta Post"},
            {"url": gnews_url("Indonesia nickel EV battery export ban processing"), "tag": "GNews | ID Nickel/EV"},
            {"url": gnews_url("Indonesia trade tariff US EU critical minerals"), "tag": "GNews | ID Trade/Tariff"},
            {"url": gnews_url("Indonesia economy GDP investment manufacturing"), "tag": "GNews | ID Economy"},
            {"url": gnews_url("ekspor tarif investasi Indonesia", hl="id", gl="ID", ceid="ID:id"), "tag": "GNews | ID Bahasa"},
        ],
        "泰国": [
            {"url": "https://www.bangkokpost.com/rss/data/breakingnews.xml", "tag": "Bangkok Post"},
            {"url": gnews_url("Thailand export manufacturing tariff investment EV"), "tag": "GNews | TH Trade/EV"},
            {"url": gnews_url("Thailand economy GDP tourism BOI investment"), "tag": "GNews | TH Economy"},
        ],
        "菲律宾": [
            {"url": gnews_url("Philippines trade export BPO investment manufacturing"), "tag": "GNews | PH Trade/BPO"},
            {"url": gnews_url("Philippines economy GDP remittance infrastructure"), "tag": "GNews | PH Economy"},
        ],
        "马来西亚": [
            {"url": "https://www.thestar.com.my/rss/News", "tag": "The Star MY"},
            {"url": gnews_url("Malaysia semiconductor trade investment export penang"), "tag": "GNews | MY Semi/Trade"},
            {"url": gnews_url("Malaysia economy GDP palm oil oil gas"), "tag": "GNews | MY Economy"},
        ],
        "柬埔寨+缅甸+老挝": [
            {"url": gnews_url("Cambodia garment manufacturing export tariff GSP"), "tag": "GNews | KH Garment/GSP"},
            {"url": gnews_url("Myanmar trade sanction investment conflict economy"), "tag": "GNews | MM Trade/Sanction"},
            {"url": gnews_url("Laos economy debt infrastructure China investment"), "tag": "GNews | LA Economy/China"},
        ],
        "政治+社会": [
            {"url": gnews_url("Southeast Asia political stability protest election policy change"), "tag": "GNews | SE Asia Politics"},
            {"url": gnews_url("Myanmar conflict military junta ASEAN response"), "tag": "GNews | Myanmar Crisis"},
            {"url": gnews_url("South China Sea dispute ASEAN Philippines Vietnam patrol"), "tag": "GNews | SCS/ASEAN"},
        ],
        "基础设施+科技": [
            {"url": gnews_url("Southeast Asia infrastructure project port railway energy"), "tag": "GNews | SE Asia Infra"},
            {"url": gnews_url("Southeast Asia technology innovation startup hub Singapore Vietnam"), "tag": "GNews | SE Asia Tech"},
        ],
        "气候+人口": [
            {"url": gnews_url("Southeast Asia climate change drought flood energy crisis"), "tag": "GNews | SE Asia Climate"},
            {"url": gnews_url("Southeast Asia demographic youth population unemployment"), "tag": "GNews | SE Asia Demo"},
        ],
        "大国关系": [
            {"url": gnews_url("ASEAN US China Japan relations trade investment summit 2026"), "tag": "GNews | ASEAN Powers"},
        ],
        "本地语言搜索": [
            {"url": gnews_url("xuất khẩu thuế quan đầu tư FDI Việt Nam", hl="vi", gl="VN", ceid="VN:vi"), "tag": "GNews | VN Tiếng Việt"},
            {"url": gnews_url("ekspor tarif investasi Indonesia", hl="id", gl="ID", ceid="ID:id"), "tag": "GNews | ID Bahasa"},
            {"url": gnews_url("ส่งออก ภาษี การลงทุน ไทย เศรษฐกิจ", hl="th", gl="TH", ceid="TH:th"), "tag": "GNews | TH ไทย"},
            {"url": gnews_url("Philippines kalakalan pamumuhukan ekonomiya", hl="fil", gl="PH", ceid="PH:fil"), "tag": "GNews | PH Filipino"},
            {"url": gnews_url("Malaysia eksport pelaburan ekonomi perdagangan", hl="ms", gl="MY", ceid="MY:ms"), "tag": "GNews | MY Bahasa Melayu"},
        ],
        "独立RSS源": [
            {"url": "https://e.vnexpress.net/rss/home.rss", "tag": "VN Express EN"},
            {"url": "https://vietnamnet.vn/en/rss/home.xml", "tag": "VietNamNet EN"},
            {"url": "https://en.antaranews.com/rss/terkini.xml", "tag": "Antara News EN"},
        ],
        "信号性查询": [
            {"url": gnews_url('"supply disruption" "force majeure" Southeast Asia manufacturing'), "tag": "GNews | Signal: SE Asia Disrupt"},
            {"url": gnews_url('"unprecedented" "record high" Southeast Asia economy trade'), "tag": "GNews | Signal: SE Asia Record"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
