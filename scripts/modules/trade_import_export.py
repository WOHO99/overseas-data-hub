#!/usr/bin/env python3
"""
trade_import_export.py — 进出口贸易模块
覆盖：贸易数据、进出口管制、原产地规则、自贸协定、反倾销
聚焦影响中国企业进出口的政策与事件
与其他模块边界：跨境电商模块管平台合规，本模块管贸易政策/管制/壁垒
"""

import sys
import os
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_module, gnews_url, load_keywords

_config_dir = os.path.join(_scripts_dir, "config")
_module_name = "trade_import_export"
_core_kw, _important_kw, _aux_kw, _signal_kw, _exclude_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "进出口贸易",
    "output_file": "trade_import_export.json",
    "max_articles": 300,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "exclude_keywords": _exclude_kw,
    "feeds": {
        "贸易管制": [
            {"url": gnews_url("Section 301 tariff US China trade war escalation 2026"), "tag": "GNews | Section 301"},
            {"url": gnews_url("Section 232 tariff steel aluminum national security"), "tag": "GNews | Section 232"},
            {"url": gnews_url("anti-dumping countervailing duty investigation China 2026"), "tag": "GNews | Anti-dumping"},
            {"url": gnews_url("export control restriction technology China Russia 2026"), "tag": "GNews | Export Control"},
            {"url": gnews_url("WTO dispute settlement ruling trade complaint"), "tag": "GNews | WTO Dispute"},
        ],
        "自贸协定+原产地": [
            {"url": gnews_url("RCEP implementation trade agreement tariff reduction"), "tag": "GNews | RCEP"},
            {"url": gnews_url("rules of origin transshipment circumvention trade"), "tag": "GNews | Rules of Origin"},
            {"url": gnews_url("FTA bilateral trade agreement negotiation 2026"), "tag": "GNews | FTA"},
            {"url": gnews_url("CPTPP membership application trade access"), "tag": "GNews | CPTPP"},
        ],
        "贸易壁垒+数据": [
            {"url": gnews_url("technical barrier trade TBT SPS import restriction"), "tag": "GNews | TBT/SPS"},
            {"url": gnews_url("import quota license trade restriction emergency 2026"), "tag": "GNews | Quota/License"},
            {"url": gnews_url("customs valuation tariff rate classification dispute"), "tag": "GNews | Customs Valuation"},
            {"url": gnews_url("trade deficit surplus China export import data 2026"), "tag": "GNews | Trade Data CN"},
        ],
        "中国企业视角": [
            {"url": gnews_url("Chinese exporter tariff impact US EU market access 2026"), "tag": "GNews | CN Exporter Impact"},
            {"url": gnews_url("反倾销 出口管制 中国企业 影响 关税", hl="zh-CN", gl="CN", ceid="CN:zh-Hans"), "tag": "GNews | CN 贸易影响 (zh)"},
        ],
        "本地语言搜索": [
            {"url": gnews_url("反倾销 出口管制 自贸协定 进出口 关税", hl="zh-CN", gl="CN", ceid="CN:zh-Hans"), "tag": "GNews | CN 贸易"},
            {"url": gnews_url("反ダンピング 関税 輸出規制 貿易協定 日本", hl="ja", gl="JP", ceid="JP:ja"), "tag": "GNews | JP 貿易"},
            {"url": gnews_url("Anti-Dumping Zoll Exportkontrolle Handelsabkommen Deutschland", hl="de", gl="DE", ceid="DE:de"), "tag": "GNews | DE Handel"},
            {"url": gnews_url("반덤핑 관세 수출통제 무역협정 한국", hl="ko", gl="KR", ceid="KR:ko"), "tag": "GNews | KR 무역"},
            {"url": gnews_url("WTO droit de douane commerce international France", hl="fr", gl="FR", ceid="FR:fr"), "tag": "GNews | FR Commerce"},
        ],
        "信号性查询": [
            {"url": gnews_url('"import ban" "export ban" "emergency restriction" trade'), "tag": "GNews | Signal: Trade Ban"},
            {"url": gnews_url('"trade sanctions" "quota suspension" "mandatory recall" import'), "tag": "GNews | Signal: Trade Sanctions"},
            {"url": gnews_url('"sudden inspection" import export customs seizure'), "tag": "GNews | Signal: Sudden Inspection"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
