#!/usr/bin/env python3
"""
cross_border_ecommerce.py — 跨境电商模块
覆盖：平台政策（亚马逊/Temu/SHEIN/TikTok Shop）、关税变动、物流、支付、合规
站在中国企业视角，追踪出海电商全链路风险与机遇
v3.5: Batch E补充6个直连RSS源(Reuters/CNBC/BBC/Guardian/Nikkei/SCMP)
"""

import sys
import os
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_module, gnews_url, load_keywords

_config_dir = os.path.join(_scripts_dir, "config")
_module_name = "cross_border_ecommerce"
_core_kw, _important_kw, _aux_kw, _signal_kw, _exclude_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "跨境电商",
    "output_file": "cross_border_ecommerce.json",
    "max_articles": 300,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "exclude_keywords": _exclude_kw,
    "feeds": {
        "平台政策": [
            {"url": gnews_url("Amazon seller ban suspension policy change 2026"), "tag": "GNews | Amazon Policy"},
            {"url": gnews_url('"Amazon seller ban" account suspended listing removed'), "tag": "GNews | Amazon Ban Signal"},
            {"url": gnews_url("Temu tariff regulation EU US compliance investigation"), "tag": "GNews | Temu Regulation"},
            {"url": gnews_url("SHEIN IPO supply chain compliance forced labor"), "tag": "GNews | SHEIN Compliance"},
            {"url": gnews_url("TikTok Shop ban suspension EU regulation marketplace"), "tag": "GNews | TikTok Shop"},
            {"url": gnews_url("AliExpress Lazada platform policy seller regulation"), "tag": "GNews | AliExpress/Lazada"},
        ],
        "关税+合规": [
            {"url": gnews_url("de minimis repeal small parcel tariff exemption end"), "tag": "GNews | De Minimis Repeal"},
            {"url": gnews_url("EU digital services tax marketplace platform liability"), "tag": "GNews | EU Digital Tax"},
            {"url": gnews_url("VAT cross-border e-commerce retroactive audit seller"), "tag": "GNews | VAT Retroactive"},
            {"url": gnews_url("customs seizure counterfeit product e-commerce import"), "tag": "GNews | Customs Seizure"},
            {"url": gnews_url("product safety recall e-commerce marketplace CPSC"), "tag": "GNews | Product Safety"},
        ],
        "物流+支付": [
            {"url": gnews_url("cross-border logistics shipping cost increase delay 2026"), "tag": "GNews | Logistics Cost"},
            {"url": gnews_url("overseas warehouse fulfillment e-commerce expansion"), "tag": "GNews | Overseas Warehouse"},
            {"url": gnews_url("return rate e-commerce cross-border last mile delivery"), "tag": "GNews | Returns/Last Mile"},
            {"url": gnews_url("payment gateway cross-border fintech remittance regulation"), "tag": "GNews | Cross-border Payment"},
        ],
        "中国卖家视角": [
            {"url": gnews_url("Chinese seller Amazon ban account suspended appeal 2026"), "tag": "GNews | CN Seller Amazon"},
            {"url": gnews_url("China cross-border e-commerce seller EU regulation compliance cost"), "tag": "GNews | CN Seller EU"},
        ],
        "本地语言搜索": [
            {"url": gnews_url("amazon seller suspend ban listing removed policy", hl="en-US", gl="US", ceid="US:en"), "tag": "GNews | US Amazon Seller"},
        ],
        "信号性查询": [
            {"url": gnews_url('"platform ban" "total ban" marketplace seller e-commerce'), "tag": "GNews | Signal: Platform Ban"},
            {"url": gnews_url('"customs detention" "forced recall" "product delisting" import'), "tag": "GNews | Signal: Customs/Recall"},
            {"url": gnews_url('"market exit" "platform shutdown" e-commerce seller'), "tag": "GNews | Signal: Market Exit"},
        ],
        "电商科技RSS": [
            # DEAD: {"url": "https://www.theguardian.com/technology/rss", "tag": "Guardian Tech"},
            {"url": "https://www.reuters.com/rssFeed/businessNews", "tag": "Reuters Business"},
            # DEAD: {"url": "https://rss.cnbc.com/headlines/world/", "tag": "CNBC World"},
            # DEAD: {"url": "http://feeds.bbci.co.uk/news/business/rss.xml", "tag": "BBC Business"},
            {"url": "https://www.theguardian.com/business/rss", "tag": "Guardian Business"},
            # DEAD: {"url": "https://asia.nikkei.com/rss/feed/nar", "tag": "Nikkei Asia"},
            # DEAD: {"url": "https://www.scmp.com/rss/91/feed", "tag": "SCMP Economy"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
