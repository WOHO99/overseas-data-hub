#!/usr/bin/env python3
"""
cross_border_ecommerce.py — 跨境电商模块
覆盖：平台政策（亚马逊/Temu/SHEIN/TikTok Shop）、关税变动、物流、支付、合规
站在中国企业视角，追踪出海电商全链路风险与机遇
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
            {"url": gnews_url("中国卖家 亚马逊 封号 资金冻结 申诉", hl="zh-CN", gl="CN", ceid="CN:zh-Hans"), "tag": "GNews | CN Seller Ban (zh)"},
        ],
        "本地语言搜索": [
            {"url": gnews_url("跨境电商 合规 关税 平台 海外仓", hl="zh-CN", gl="CN", ceid="CN:zh-Hans"), "tag": "GNews | CN 跨境电商"},
            {"url": gnews_url("amazon seller suspend ban listing removed policy", hl="en-US", gl="US", ceid="US:en"), "tag": "GNews | US Amazon Seller"},
            {"url": gnews_url("Temu SHEIN Zoll Steuer EU Regulierung", hl="de", gl="DE", ceid="DE:de"), "tag": "GNews | DE E-commerce"},
            {"url": gnews_url("Temu SHEIN droits de douane régulation UE", hl="fr", gl="FR", ceid="FR:fr"), "tag": "GNews | FR E-commerce"},
            {"url": gnews_url("越境EC 関税 コンプライアンス Amazon Temu", hl="ja", gl="JP", ceid="JP:ja"), "tag": "GNews | JP E-commerce"},
            {"url": gnews_url("직구 해외직구 관세 테무 쉬인", hl="ko", gl="KR", ceid="KR:ko"), "tag": "GNews | KR E-commerce"},
        ],
        "信号性查询": [
            {"url": gnews_url('"platform ban" "total ban" marketplace seller e-commerce'), "tag": "GNews | Signal: Platform Ban"},
            {"url": gnews_url('"customs detention" "forced recall" "product delisting" import'), "tag": "GNews | Signal: Customs/Recall"},
            {"url": gnews_url('"market exit" "platform shutdown" e-commerce seller'), "tag": "GNews | Signal: Market Exit"},
        ],
        "电商科技RSS": [
            {"url": "https://www.theguardian.com/technology/rss", "tag": "Guardian Tech"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
