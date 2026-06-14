#!/usr/bin/env python3
"""
global_risk.py — 国际风险模块
覆盖：企业面临的跨境风险（制裁清单/外资审查/征用/资本管制/主权违约）
互斥边界：不含国家间军事冲突（geopolitics_risk管）、不含宏观金融（finance管）
与跨境电商模块边界：本模块管制裁/审查/征收等政策级风险，跨境电商模块管平台合规
v3.2: Batch D新增8个安全/隐私直连RSS源
"""

import sys
import os
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_module, gnews_url, load_keywords

_config_dir = os.path.join(_scripts_dir, "config")
_module_name = "global_risk"
_core_kw, _important_kw, _aux_kw, _signal_kw, _exclude_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "国际风险",
    "output_file": "global_risk.json",
    "max_articles": 300,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "exclude_keywords": _exclude_kw,
    "feeds": {
        "制裁+清单": [
            {"url": gnews_url("OFAC sanctions list designation entity update 2026"), "tag": "GNews | OFAC"},
            {"url": gnews_url("BIS entity list addition export control US 2026"), "tag": "GNews | BIS Entity List"},
            {"url": gnews_url("EU sanctions package Russia China designation 2026"), "tag": "GNews | EU Sanctions"},
            {"url": gnews_url("asset freeze designated national financial blockade"), "tag": "GNews | Asset Freeze"},
        ],
        "外资审查+征收": [
            {"url": gnews_url("CFIUS review block acquisition national security 2026"), "tag": "GNews | CFIUS"},
            {"url": gnews_url("EU FDI screening investment review regulation 2026"), "tag": "GNews | EU FDI Screening"},
            {"url": gnews_url("expropriation nationalization foreign investment sovereign risk"), "tag": "GNews | Expropriation"},
            {"url": gnews_url("forced divestiture sell-off foreign company order"), "tag": "GNews | Forced Divestiture"},
        ],
        "资本管制+主权风险": [
            {"url": gnews_url("capital controls foreign exchange restriction currency inconvertibility"), "tag": "GNews | Capital Controls"},
            {"url": gnews_url("sovereign default debt restructuring emerging market 2026"), "tag": "GNews | Sovereign Default"},
            {"url": gnews_url("payment freeze license revocation compliance penalty"), "tag": "GNews | Payment/Compliance"},
        ],
        "供应链风险+FCPA": [
            {"url": gnews_url("supply chain disruption force majeure political risk insurance"), "tag": "GNews | SC Disruption"},
            {"url": gnews_url("FCPA anticorruption enforcement compliance penalty 2026"), "tag": "GNews | FCPA/Compliance"},
        ],
        "中国企业视角": [
            {"url": gnews_url("Chinese company sanctions designation entity list investment blocked 2026"), "tag": "GNews | CN Company Sanctions"},
            {"url": gnews_url("中国企业 制裁清单 实体清单 投资被阻 合规处罚", hl="zh-CN", gl="CN", ceid="CN:zh-Hans"), "tag": "GNews | CN 制裁/风险 (zh)"},
        ],
        "本地语言搜索": [
            {"url": gnews_url("制裁清单 资产冻结 外资审查 征收 资本管制", hl="zh-CN", gl="CN", ceid="CN:zh-Hans"), "tag": "GNews | CN 制裁/风险"},
            {"url": gnews_url("санкции список замораживание активов иностранные инвестиции", hl="ru", gl="RU", ceid="RU:ru"), "tag": "GNews | RU Санкции/Риск"},
            {"url": gnews_url("Sanktionen Liste Investitionsprüfung Enteignung Deutschland", hl="de", gl="DE", ceid="DE:de"), "tag": "GNews | DE Sanktionen"},
            {"url": gnews_url("sanctions liste contrôle investissements expropriation France", hl="fr", gl="FR", ceid="FR:fr"), "tag": "GNews | FR Sanctions"},
        ],
        "信号性查询": [
            {"url": gnews_url('"blacklisted" "freeze order" "forced expropriation" sanction'), "tag": "GNews | Signal: Sanctions Action"},
            {"url": gnews_url('"capital controls imposed" "default declared" "force majeure invoked"'), "tag": "GNews | Signal: Risk Escalation"},
            {"url": gnews_url('"investment blocked" "deal blocked" national security review'), "tag": "GNews | Signal: Deal Blocked"},
        ],
        "风险情报RSS": [
            {"url": "https://feeds.npr.org/1001/rss.xml", "tag": "NPR World"},
            {"url": "https://www.theguardian.com/world/rss", "tag": "Guardian World"},
        ],
        "安全与隐私RSS(D)": [
            # v3.2 Batch D: 8个安全/隐私直连RSS
            {"url": "https://www.schneier.com/feed/atom/", "tag": "Schneier on Security"},
            {"url": "https://krebsonsecurity.com/feed/", "tag": "Krebs on Security"},
            {"url": "https://www.troyhunt.com/rss/", "tag": "Troy Hunt"},
            {"url": "https://www.hackerfactor.com/blog/index.php?/feeds/index.rss2", "tag": "Hacker Factor"},
            {"url": "https://www.eff.org/rss/updates.xml", "tag": "EFF Updates"},
            {"url": "https://isc.sans.edu/rssfeed_full.xml", "tag": "SANS ISC Diary"},
            {"url": "https://feeds.feedburner.com/TheHackersNews", "tag": "The Hacker News"},
            {"url": "https://grahamcluley.com/feed/", "tag": "Graham Cluley"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
