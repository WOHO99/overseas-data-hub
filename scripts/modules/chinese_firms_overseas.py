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
        "Track17重点27股监控": [
            # v3.4新增(07/21): Track17 A股27股池海外情报主动监控
            # 高价值4只(扩展查询,补全海外事件最新关键词)
            {"url": gnews_url("BYD overseas factory Hungary Brazil Turkey Europe tariff EV export 2026"), "tag": "GNews | BYD T17"},
            {"url": gnews_url("CATL battery plant Hungary Germany Indonesia Morocco US investment 2026"), "tag": "GNews | CATL T17"},
            {"url": gnews_url("ZTE Nvidia H200 chip license US export restriction sanctions 2026"), "tag": "GNews | ZTE T17"},
            {"url": gnews_url("SMIC foundry entity list sanctions equipment ASML Chip supply 2026"), "tag": "GNews | SMIC T17"},
            # 中价值9只(新增主动查询)
            {"url": gnews_url("Gree Electric overseas air conditioner Midea Haier market expansion acquisition"), "tag": "GNews | Gree T17"},
            {"url": gnews_url("Cambricon AI chip entity list US sanction China 2026"), "tag": "GNews | Cambricon T17"},
            {"url": gnews_url("Loongson CPU architecture China domestic semiconductor MIPS x86 2026"), "tag": "GNews | Loongson T17"},
            {"url": gnews_url("Trina Solar tariff anti-circumvention US EU panel module 2026"), "tag": "GNews | Trina T17"},
            {"url": gnews_url("Will Semiconductor OmniVision image sensor CIS smartphone 2026"), "tag": "GNews | Will Semi T17"},
            {"url": gnews_url("Hygon DCU AI chip sanction entity list AMD x86 license China 2026"), "tag": "GNews | Hygon T17"},
            {"url": gnews_url("Naura Technology semiconductor equipment Chinese domestic ASML 2026"), "tag": "GNews | Naura T17"},
            {"url": gnews_url("JCET Chiplet HBM packaging test China semiconductor 2026"), "tag": "GNews | JCET T17"},
            {"url": gnews_url("Sugon server entity list supercomputer HPC China 2026"), "tag": "GNews | Sugon T17"},
        ],
        "Track17行业竞争维度": [
            # v3.4新增(07/21): 7大板块产业级新闻(含中企+国际同行)
            # 比单查公司更高效,能抓到关税/管制/产业政策级别的新闻
            # 板块1: 电动车整车(影响比亚迪)
            {"url": gnews_url("Chinese EV maker Europe tariff BYD NIO XPeng Li Auto Geely SAIC Chery 2026"), "tag": "GNews | T17 EV板块"},
            {"url": gnews_url("Chinese EV maker US Mexico factory BYD Geely tariff anti-dumping"), "tag": "GNews | T17 EV北美"},
            # 板块2: 动力电池(影响宁德时代、比亚迪)
            {"url": gnews_url("Chinese battery maker Europe plant CATL BYD CALB Sunwoda LG Energy Samsung SDI 2026"), "tag": "GNews | T17 电池板块"},
            {"url": gnews_url("LFP lithium iron phosphate battery cost market share CATL BYD 2026"), "tag": "GNews | T17 LFP技术"},
            # 板块3: 风电(影响金风/明阳/泰胜)
            {"url": gnews_url("Chinese wind turbine maker overseas Goldwind Mingyang Envision Vestas Siemens Gamesa GE Vernova 2026"), "tag": "GNews | T17 风电板块"},
            {"url": gnews_url("offshore wind farm China Goldwind Mingyang export contract Vietnam India"), "tag": "GNews | T17 海上风电"},
            # 板块4: 光伏(影响天合/奥特维/正泰光伏)
            {"url": gnews_url("Chinese solar panel maker tariff anti-circumvention Trina JinkoSolar JA Solar LONGi Canadian Solar First Solar 2026"), "tag": "GNews | T17 光伏板块"},
            {"url": gnews_url("solar cell TOPCon HJT technology Trina JinkoSolar LONGi efficiency record"), "tag": "GNews | T17 光伏技术"},
            # 板块5: 晶圆代工+封测(影响中芯/长电)
            {"url": gnews_url("China foundry SMIC Hua Hong 7nm 5nm breakthrough TSMC UMC GlobalFoundries 2026"), "tag": "GNews | T17 代工板块"},
            {"url": gnews_url("JCET ASE Amkor Chiplet HBM advanced packaging China 2026"), "tag": "GNews | T17 封测板块"},
            # 板块6: 半导体设备+存储(影响北方华创/兆易)
            {"url": gnews_url("Chinese semiconductor equipment Naura AMEC Piotech domestic Applied Materials ASML Lam Research 2026"), "tag": "GNews | T17 半导体设备"},
            {"url": gnews_url("GigaDevice NAND flash MCU GD32 Samsung SK Hynix Micron China 2026"), "tag": "GNews | T17 存储板块"},
            # 板块7: AI芯片+CPU+GPU(影响寒武纪/海光/龙芯/景嘉微/韦尔)
            {"url": gnews_url("Chinese AI chip Cambricon Hygon Biren Moore Threads Huawei Ascend NVIDIA AMD sanction 2026"), "tag": "GNews | T17 AI芯片板块"},
            {"url": gnews_url("Chinese CPU Loongson Phytium Zhaoxin Intel AMD ARM domestic substitution 2026"), "tag": "GNews | T17 国产CPU"},
            {"url": gnews_url("Chinese GPU JingJia Micro Moore Threads Intel NVIDIA AMD domestic 2026"), "tag": "GNews | T17 国产GPU"},
            {"url": gnews_url("image sensor CIS OmniVision Will Semiconductor Sony Samsung smartphone 2026"), "tag": "GNews | T17 CIS板块"},
            # 板块8: 网安+CDN+量子+服务器(影响奇安信/网宿/国盾/曙光)
            {"url": gnews_url("Chinese cybersecurity firm Qi An Xin Palo Alto Fortinet CrowdStrike enterprise 2026"), "tag": "GNews | T17 网安板块"},
            {"url": gnews_url("China CDN edge computing Wangsu Akamai Cloudflare 5G 2026"), "tag": "GNews | T17 CDN板块"},
            {"url": gnews_url("quantum communication QKD China QuantumCTek ID Quantique IBM network 2026"), "tag": "GNews | T17 量子板块"},
            {"url": gnews_url("China AI server Sugon Inspur Lenovo NVIDIA H100 H200 restriction 2026"), "tag": "GNews | T17 AI服务器板块"},
            # 板块9: 家电+电力+科创生物(影响格力/长江电力/立新能源/正泰低压/键凯/药康)
            {"url": gnews_url("Chinese home appliance maker Gree Midea Haier overseas acquisition Daikin LG 2026"), "tag": "GNews | T17 家电板块"},
            {"url": gnews_url("China hydropower utility Yangtze River Three Gorges Huaneng Power CGN renewable IPP 2026"), "tag": "GNews | T17 电力板块"},
            {"url": gnews_url("Chint low voltage electrical Schneider ABB Siemens overseas 2026"), "tag": "GNews | T17 低压电器板块"},
            {"url": gnews_url("PEGylation JenKem Nektar polymer drug conjugate China 2026"), "tag": "GNews | T17 PEG生物板块"},
            {"url": gnews_url("GemPharmatech animal model CRO Charles River Jackson Laboratory WuXi 2026"), "tag": "GNews | T17 实验动物板块"},
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
