#!/usr/bin/env python3
"""
region_east_asia.py — 东亚深度模块（日韩朝）
v3.3升级：增加政治稳定、基础设施、科技、气候、人口、大国关系+日/韩语搜索
"""

import sys
import os
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_module, gnews_url, load_keywords

_config_dir = os.path.join(_scripts_dir, "config")
_module_name = "region_east_asia"
_core_kw, _important_kw, _aux_kw, _signal_kw, _exclude_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "东亚深度",
    "output_file": "east_asia.json",
    "max_articles": 300,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "exclude_keywords": _exclude_kw,
    "feeds": {
        "日本": [
            {"url": "https://asia.nikkei.com/rss/feed/nar", "tag": "Nikkei Asia"},
            {"url": gnews_url("Japan semiconductor chip export control equipment restriction"), "tag": "GNews | JP Chip/Export"},
            {"url": gnews_url("Japan trade tariff manufacturing supply chain reshoring"), "tag": "GNews | JP Trade/SCM"},
            {"url": gnews_url("Japan economy BOJ monetary policy yen GDP 2026"), "tag": "GNews | JP Economy/BOJ"},
        ],
        "韩国": [
            {"url": gnews_url("South Korea semiconductor chip export restriction trade K-CHIPS"), "tag": "GNews | KR Chip/Export"},
            {"url": gnews_url("South Korea trade tariff manufacturing battery EV shipbuilding"), "tag": "GNews | KR Trade/Mfg"},
            {"url": gnews_url("South Korea economy GDP Bank of Korea rate inflation"), "tag": "GNews | KR Economy"},
        ],
        "朝鲜半岛": [
            {"url": gnews_url("North Korea sanctions trade missile nuclear China Russia"), "tag": "GNews | DPRK Sanctions"},
        ],
        "政治+社会": [
            {"url": gnews_url("Japan political stability election policy LDP 2026"), "tag": "GNews | JP Politics"},
            {"url": gnews_url("South Korea political crisis election protest 2026"), "tag": "GNews | KR Politics"},
            {"url": gnews_url("Taiwan Strait military tension China patrol 2026"), "tag": "GNews | Taiwan/SCS"},
        ],
        "基础设施+科技": [
            {"url": gnews_url("Japan chip fab semiconductor factory TSMC Kumamoto Rapidus"), "tag": "GNews | JP Chip Fab"},
            {"url": gnews_url("South Korea technology hub semiconductor Samsung SK Hynix"), "tag": "GNews | KR Tech Hub"},
        ],
        "气候+人口": [
            {"url": gnews_url("Japan Korea typhoon earthquake climate disaster 2026"), "tag": "GNews | JK Climate"},
            {"url": gnews_url("Japan Korea demographic aging low birth rate population"), "tag": "GNews | JK Demo"},
            {"url": gnews_url("Japan Korea energy import dependency nuclear LNG"), "tag": "GNews | JK Energy"},
        ],
        "大国关系": [
            {"url": gnews_url("US Japan Korea trilateral security trade summit 2026"), "tag": "GNews | US-JK Trilateral"},
            {"url": gnews_url("China Japan relation trade tension historical dispute"), "tag": "GNews | CN-JP"},
            {"url": gnews_url("China Korea relation trade THAAD dispute"), "tag": "GNews | CN-KR"},
        ],
        "本地语言搜索": [
            {"url": gnews_url("日本 輸出 貿易 規制 経済", hl="ja", gl="JP", ceid="JP:ja"), "tag": "GNews | JP 日本語"},
            {"url": gnews_url("한국 수출 무역 투자 경제", hl="ko", gl="KR", ceid="KR:ko"), "tag": "GNews | KR 한국어"},
            {"url": gnews_url("中国 关税 制裁 出口管制 供应链 贸易", hl="zh-CN", gl="CN", ceid="CN:zh-Hans"), "tag": "GNews | CN 中文"},
        ],
        "独立RSS源": [
            {"url": "https://www3.nhk.or.jp/nhkworld/rss/news/headline.xml", "tag": "NHK World"},
            {"url": "http://www.chinadaily.com.cn/rss/china_rss.xml", "tag": "China Daily"},
        ],
        "信号性查询": [
            {"url": gnews_url('"military escalation" "first ever" Japan Korea Taiwan'), "tag": "GNews | Signal: JK Military"},
            {"url": gnews_url('"supply disruption" "breakthrough" Japan Korea semiconductor'), "tag": "GNews | Signal: JK Chip"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
