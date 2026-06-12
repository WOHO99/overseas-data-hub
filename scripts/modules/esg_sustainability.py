#!/usr/bin/env python3
"""
esg_sustainability.py — ESG与可持续发展模块
覆盖：ESG法规、碳信用、可持续供应链、气候风险
欧美市场合规越来越离不开ESG
"""

import sys
import os
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_module, gnews_url, load_keywords

_config_dir = os.path.join(_scripts_dir, "config")
_module_name = "esg_sustainability"
_core_kw, _important_kw, _aux_kw, _signal_kw, _exclude_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "ESG与可持续发展",
    "output_file": "esg_sustainability.json",
    "max_articles": 500,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "exclude_keywords": _exclude_kw,
    "feeds": {
        "ESG法规": [
            {"url": gnews_url("ESG regulation disclosure requirement SEC EU CSRD ISSB 2026"), "tag": "GNews | ESG Regulation"},
            {"url": gnews_url("EU taxonomy sustainable investment classification 2026"), "tag": "GNews | EU Taxonomy"},
            {"url": gnews_url("SEC climate disclosure rule requirement corporate"), "tag": "GNews | SEC Climate Rule"},
            {"url": gnews_url("SFDR sustainable finance disclosure regulation fund"), "tag": "GNews | SFDR"},
        ],
        "碳+绿": [
            {"url": gnews_url("carbon credit offset market price greenwashing investigation"), "tag": "GNews | Carbon Credit"},
            {"url": gnews_url("cap and trade emission trading system carbon price"), "tag": "GNews | Cap & Trade"},
            {"url": gnews_url("green bond sustainable finance investment issuance 2026"), "tag": "GNews | Green Bond"},
            {"url": gnews_url("net zero pledge science based target corporate commitment"), "tag": "GNews | Net Zero"},
        ],
        "可持续供应链": [
            {"url": gnews_url("sustainable supply chain due diligence forced labor regulation"), "tag": "GNews | SC Due Diligence"},
            {"url": gnews_url("EU deforestation regulation EUDR compliance implementation"), "tag": "GNews | EUDR"},
            {"url": gnews_url("conflict mineral responsible sourcing cobalt lithium supply chain"), "tag": "GNews | Conflict Mineral"},
            {"url": gnews_url("scope 3 emission supply chain reporting corporate"), "tag": "GNews | Scope 3"},
            {"url": gnews_url("modern slavery act forced labor import ban enforcement"), "tag": "GNews | Modern Slavery"},
        ],
        "气候风险": [
            {"url": gnews_url("climate risk adaptation insurance loss damage extreme weather"), "tag": "GNews | Climate Risk"},
            {"url": gnews_url("biodiversity loss regulation nature restoration EU"), "tag": "GNews | Biodiversity"},
            {"url": gnews_url("PFAS ban chemical regulation water contamination"), "tag": "GNews | PFAS/Chemical"},
            {"url": gnews_url("circular economy plastic regulation waste reduction"), "tag": "GNews | Circular Econ"},
        ],
        "本地语言搜索": [
            {"url": gnews_url("Nachhaltigkeit ESG Klimaschutz Lieferkette Deutschland", hl="de", gl="DE", ceid="DE:de"), "tag": "GNews | DE ESG/Nachhaltigkeit"},
            {"url": gnews_url("développement durable ESG climat chaîne d'approvisionnement France", hl="fr", gl="FR", ceid="FR:fr"), "tag": "GNews | FR ESG/Durabilité"},
        ],
        "独立RSS源": [
            {"url": "https://www.esgnews.com/rss", "tag": "ESG News"},
        ],
        "信号性查询": [
            {"url": gnews_url('"greenwashing" scandal investigation penalty corporate'), "tag": "GNews | Signal: Greenwash"},
            {"url": gnews_url('"class action" ESG climate environmental lawsuit'), "tag": "GNews | Signal: ESG Lawsuit"},
            {"url": gnews_url('"landmark ruling" climate ESG regulation compliance'), "tag": "GNews | Signal: Landmark"},
        ],
        "专题精选": [
            {"url": gnews_url(topic="SCIENCE"), "tag": "GNews Topic | SCIENCE(US)"},
        ],
        "ESG环境RSS": [
            {"url": "https://www.theguardian.com/environment/rss", "tag": "Guardian Env"},
            {"url": "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "tag": "BBC Sci/Env"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
