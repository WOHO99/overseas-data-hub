#!/usr/bin/env python3
"""
chinese_firms_overseas.py — 中企海外动态模块
覆盖：海外建厂、并购、上市、合规处罚、中标项目、一带一路
核心输入：50家重点企业名单（关键词+GNews精确查询联动）
与global_risk边界：本模块管具体企业事件，global_risk管政策级风险
"""

import sys
import os
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_module, gnews_url, load_keywords

_config_dir = os.path.join(_scripts_dir, "config")
_module_name = "chinese_firms_overseas"
_core_kw, _important_kw, _aux_kw, _signal_kw, _exclude_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "中企海外动态",
    "output_file": "chinese_firms_overseas.json",
    "max_articles": 400,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "exclude_keywords": _exclude_kw,
    "feeds": {
        "新能源车+电池": [
            {"url": gnews_url("BYD factory Europe Hungary Brazil tariff electric vehicle"), "tag": "GNews | BYD Overseas"},
            {"url": gnews_url("CATL battery plant factory Hungary Germany US investment"), "tag": "GNews | CATL Overseas"},
            {"url": gnews_url("Geely overseas acquisition Volvo Lotus electric vehicle"), "tag": "GNews | Geely Overseas"},
            {"url": gnews_url("NIO Europe expansion battery swap station market entry"), "tag": "GNews | NIO Overseas"},
            {"url": gnews_url("XPeng Li Auto overseas Europe market expansion 2026"), "tag": "GNews | XPeng/Li Auto"},
        ],
        "半导体+科技": [
            {"url": gnews_url("Huawei ban overseas contract 5G chip restriction 2026"), "tag": "GNews | Huawei Overseas"},
            {"url": gnews_url("ZTE compliance monitor sanctions overseas contract"), "tag": "GNews | ZTE Overseas"},
            {"url": gnews_url("SMIC YMTC CXMT entity list sanctions chip restriction"), "tag": "GNews | Chip Firms Sanctions"},
            {"url": gnews_url("HiSilicon sanctions semiconductor restriction export control"), "tag": "GNews | HiSilicon"},
        ],
        "跨境电商+互联网": [
            {"url": gnews_url("Temu EU regulation tariff forced labor investigation 2026"), "tag": "GNews | Temu Overseas"},
            {"url": gnews_url("SHEIN IPO supply chain compliance audit regulation"), "tag": "GNews | SHEIN Overseas"},
            {"url": gnews_url("ByteDance TikTok ban EU DSA investigation divestiture"), "tag": "GNews | ByteDance/TikTok"},
            {"url": gnews_url("Alibaba cloud overseas international expansion Lazada"), "tag": "GNews | Alibaba Overseas"},
            {"url": gnews_url("Tencent overseas gaming investment acquisition NetEase miHoYo"), "tag": "GNews | Tencent/NetEase/miHoYo"},
        ],
        "安防+AI": [
            {"url": gnews_url("DJI ban entity list restriction drone regulation 2026"), "tag": "GNews | DJI Overseas"},
            {"url": gnews_url("Hikvision Dahua entity list ban surveillance sanction"), "tag": "GNews | Hikvision/Dahua"},
            {"url": gnews_url("SenseTime Megvii iFlytek entity list sanction AI restriction"), "tag": "GNews | AI Firms Sanctions"},
        ],
        "光伏+新能源": [
            {"url": gnews_url("LONGi JinkoSolar tariff anti-circumvention US EU solar panel"), "tag": "GNews | Solar Firms"},
            {"url": gnews_url("Sungrow inverter overseas storage project Europe"), "tag": "GNews | Sungrow Overseas"},
            {"url": gnews_url("Goldwind Envision Energy overseas wind farm battery project"), "tag": "GNews | Wind Firms"},
        ],
        "基建+工程": [
            {"url": gnews_url("CCCC CRRC CRCC CRECG overseas Belt and Road project contract"), "tag": "GNews | Infrastructure Firms"},
            {"url": gnews_url("ZPMC Sany Heavy Industry overseas port equipment infrastructure"), "tag": "GNews | ZPMC/Sany"},
        ],
        "能源+资源": [
            {"url": gnews_url("PetroChina Sinopec CNOOC overseas refinery investment sanction risk"), "tag": "GNews | Energy Firms"},
            {"url": gnews_url("State Grid overseas acquisition Brazil Philippines power grid"), "tag": "GNews | State Grid"},
        ],
        "制造+消费": [
            {"url": gnews_url("Haier Midea overseas acquisition manufacturing base robotics"), "tag": "GNews | Haier/Midea"},
            {"url": gnews_url("Wanhua Chemical overseas acquisition Hungary anti-dumping"), "tag": "GNews | Wanhua Chemical"},
            {"url": gnews_url("Xiaomi OPPO vivo overseas India Europe patent dispute market"), "tag": "GNews | Phone Firms"},
            {"url": gnews_url("Lenovo overseas server PC market supply chain shift"), "tag": "GNews | Lenovo Overseas"},
            {"url": gnews_url("Weichai Power overseas acquisition MINISO expansion Azure battery"), "tag": "GNews | Other Firms"},
        ],
        "金融": [
            {"url": gnews_url("Bank of China ICBC CCB overseas branch sanctions cross-border RMB"), "tag": "GNews | Bank Firms"},
        ],
        "本地语言搜索": [
            {"url": gnews_url("中国企业 海外建厂 并购 制裁 合规处罚", hl="zh-CN", gl="CN", ceid="CN:zh-Hans"), "tag": "GNews | CN 中企海外"},
            {"url": gnews_url("BYD CATL Huawei 海外 工厂 制裁 关税", hl="zh-CN", gl="CN", ceid="CN:zh-Hans"), "tag": "GNews | CN 重点企业"},
            {"url": gnews_url("BYD CATL Huawei 工廠 制裁 ヨーロッパ", hl="ja", gl="JP", ceid="JP:ja"), "tag": "GNews | JP 中国企業"},
            {"url": gnews_url("BYD CATL Huawei 글로벌 공장 제재 관세", hl="ko", gl="KR", ceid="KR:ko"), "tag": "GNews | KR 중국기업"},
            {"url": gnews_url("BYD Huawei chinesische Firma Investition Sanktionen Deutschland", hl="de", gl="DE", ceid="DE:de"), "tag": "GNews | DE China-Firmen"},
            {"url": gnews_url("Huawei BYD entreprise chinoise investissement sanctions France", hl="fr", gl="FR", ceid="FR:fr"), "tag": "GNews | FR Entreprises CN"},
        ],
        "信号性查询": [
            {"url": gnews_url('"construction halted" "contract terminated" "worker strike" Chinese company'), "tag": "GNews | Signal: Project Halt"},
            {"url": gnews_url('"license revoked" "forced divestiture" "added to list" Chinese firm'), "tag": "GNews | Signal: License/LIST"},
            {"url": gnews_url('"compliance fine" "regulatory penalty" "investigation" Chinese overseas'), "tag": "GNews | Signal: Compliance Penalty"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
