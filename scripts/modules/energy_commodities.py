#!/usr/bin/env python3
"""
energy_commodities.py — 全球能源与大宗商品模块
覆盖：能源安全、关键矿产争夺、粮食安全、气候政策冲击
物理维度而非价格维度（价格归金融模块）
"""

import sys
import os
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_module, gnews_url, load_keywords

_config_dir = os.path.join(_scripts_dir, "config")
_module_name = "energy_commodities"
_core_kw, _important_kw, _aux_kw, _signal_kw, _exclude_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "全球能源与大宗商品",
    "output_file": "energy_commodities.json",
    "max_articles": 350,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "exclude_keywords": _exclude_kw,
    "feeds": {
        "油气": [
            {"url": gnews_url("OPEC+ oil output quota production cut price war"), "tag": "GNews | OPEC+ Quota"},
            {"url": gnews_url("crude oil supply disruption production outage pipeline"), "tag": "GNews | Oil Disruption"},
            {"url": gnews_url("strategic petroleum reserve release drawdown"), "tag": "GNews | SPR"},
            {"url": gnews_url("LNG export terminal capacity expansion project"), "tag": "GNews | LNG Expansion"},
        ],
        "关键矿产": [
            {"url": gnews_url("critical mineral lithium cobalt nickel rare earth supply chain"), "tag": "GNews | Critical Minerals"},
            {"url": gnews_url("lithium mining project battery metal demand supply"), "tag": "GNews | Lithium Mine"},
            {"url": gnews_url("cobalt Congo DRC mining ethical supply chain"), "tag": "GNews | Cobalt/DRC"},
            {"url": gnews_url("rare earth China export quota processing strategic"), "tag": "GNews | Rare Earth/China"},
            {"url": gnews_url("mine nationalization export ban mineral Indonesia Chile"), "tag": "GNews | Mineral Nat'l/Ban"},
            {"url": gnews_url("copper mining supply demand electrification grid"), "tag": "GNews | Copper"},
        ],
        "粮食安全": [
            {"url": gnews_url("global food price crisis grain export ban wheat corn rice"), "tag": "GNews | Food Crisis"},
            {"url": gnews_url("fertilizer shortage supply export restriction Russia"), "tag": "GNews | Fertilizer"},
            {"url": gnews_url("drought crop failure agriculture climate 2026"), "tag": "GNews | Drought/Crop"},
        ],
        "能源转型+碳": [
            {"url": gnews_url("EU carbon border tax CBAM steel aluminum fertilizer import"), "tag": "GNews | CBAM"},
            {"url": gnews_url("energy transition fossil fuel divestment renewable investment"), "tag": "GNews | Energy Transition"},
            {"url": gnews_url("solar manufacturing capacity global overcapacity China"), "tag": "GNews | Solar Mfg"},
            {"url": gnews_url("nuclear energy renaissance reactor SMR project 2026"), "tag": "GNews | Nuclear"},
            {"url": gnews_url("hydrogen green blue project investment policy"), "tag": "GNews | Hydrogen"},
        ],
        "本地语言搜索": [
            {"url": gnews_url("ekspor mineral kritis nikel energi Indonesia", hl="id", gl="ID", ceid="ID:id"), "tag": "GNews | ID Energi/Mineral"},
            {"url": gnews_url("exportação mineral crítico petróleo energia Brasil", hl="pt-BR", gl="BR", ceid="BR:pt-419"), "tag": "GNews | BR Energia/Mineral"},
        ],
        "独立RSS源": [
            {"url": "https://www.spglobal.com/rss", "tag": "S&P Global"},
            {"url": "https://oilprice.com/rss/main", "tag": "OilPrice.com"},
        ],
        "信号性查询": [
            {"url": gnews_url('"supply disruption" energy commodity oil gas mineral'), "tag": "GNews | Signal: Energy Disruption"},
            {"url": gnews_url('"force majeure" oil gas mining production'), "tag": "GNews | Signal: Force Majeure"},
            {"url": gnews_url('"export ban" "record high" commodity food energy'), "tag": "GNews | Signal: Export Ban/Record"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
