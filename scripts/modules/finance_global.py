#!/usr/bin/env python3
"""
finance_global.py — 全球宏观与资本流动全图
v3.3升级：增加系统性风险、全球资本流动异动、前沿市场风险、
去美元化/数字货币/支付体系变革
"""

import sys
import os
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_module, gnews_url, load_keywords

_config_dir = os.path.join(_scripts_dir, "config")
_module_name = "finance_global"
_core_kw, _important_kw, _aux_kw, _signal_kw, _exclude_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "全球宏观与资本流动",
    "output_file": "finance.json",
    "max_articles": 800,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "exclude_keywords": _exclude_kw,
    "feeds": {
        "全球宏观": [
            {"url": gnews_url("Federal Reserve FOMC interest rate decision 2026"), "tag": "GNews | Fed/FOMC"},
            {"url": gnews_url("ECB interest rate monetary policy decision"), "tag": "GNews | ECB"},
            {"url": gnews_url("Bank of Japan monetary policy rate yield curve"), "tag": "GNews | BOJ"},
            {"url": gnews_url("Bank of England interest rate inflation UK"), "tag": "GNews | BOE"},
            {"url": gnews_url("PBOC China monetary policy rate cut reserve ratio"), "tag": "GNews | PBOC/央行"},
            {"url": gnews_url("IMF World Bank global economic outlook forecast"), "tag": "GNews | IMF/World Bank"},
            {"url": gnews_url("global recession risk stagflation 2026"), "tag": "GNews | Global Recession"},
            {"url": gnews_url("US CPI inflation nonfarm payroll employment data"), "tag": "GNews | US CPI/NFP"},
            {"url": gnews_url("Europe inflation GDP PMI economic data"), "tag": "GNews | Euro Economy"},
            {"url": gnews_url("China GDP PMI CPI economic data stimulus"), "tag": "GNews | China Economy"},
        ],
        "系统性风险": [
            # v3.3新增
            {"url": gnews_url("global systemic risk financial stability report IMF BIS"), "tag": "GNews | Systemic Risk"},
            {"url": gnews_url("emerging market debt crisis default restructuring 2026"), "tag": "GNews | EM Debt Crisis"},
            {"url": gnews_url("global liquidity tightening capital outflow emerging market"), "tag": "GNews | Liquidity/Outflow"},
        ],
        "去美元化+数字支付": [
            # v3.3新增
            {"url": gnews_url("de-dollarization central bank digital currency cross-border payment"), "tag": "GNews | De-dollar/CBDC"},
            {"url": gnews_url("BRICS currency alternative settlement system SWIFT"), "tag": "GNews | BRICS Currency"},
            {"url": gnews_url("sovereign wealth fund investment shift allocation 2026"), "tag": "GNews | SWF Shift"},
        ],
        "各国股市": [
            {"url": gnews_url("US stock market S&P 500 Nasdaq Dow regulation SEC"), "tag": "GNews | US Stock/SEC"},
            {"url": gnews_url("Europe stock market regulation ESMA MiFID"), "tag": "GNews | EU Stock/ESMA"},
            {"url": gnews_url("Japan stock market Nikkei regulation FSA"), "tag": "GNews | Japan Stock/FSA"},
            {"url": gnews_url("India stock market Sensex Nifty SEBI regulation"), "tag": "GNews | India Stock/SEBI"},
            {"url": gnews_url("Hong Kong stock market Hang Seng regulation SFC"), "tag": "GNews | HK Stock/SFC"},
            {"url": gnews_url("China A-share stock market CSRC regulation"), "tag": "GNews | A-share/CSRC"},
            {"url": gnews_url("ASEAN stock market Thailand Indonesia Philippines"), "tag": "GNews | ASEAN Stock"},
            {"url": gnews_url("Australia stock market ASX regulation"), "tag": "GNews | AU Stock/ASX"},
            {"url": gnews_url("South Korea stock market KOSPI regulation FSS"), "tag": "GNews | Korea Stock/FSS"},
            {"url": gnews_url("Brazil stock market B3 regulation CVM"), "tag": "GNews | Brazil Stock"},
            {"url": gnews_url("Middle East stock market Saudi Tadawul UAE DFM"), "tag": "GNews | ME Stock"},
            {"url": gnews_url("Russia stock market MOEX regulation"), "tag": "GNews | Russia Stock"},
        ],
        "大宗商品": [
            {"url": gnews_url("crude oil price OPEC production Brent WTI"), "tag": "GNews | Oil/OPEC"},
            {"url": gnews_url("copper price LME demand supply warehouse"), "tag": "GNews | Copper/LME"},
            {"url": gnews_url("gold price COMEX safe haven demand central bank"), "tag": "GNews | Gold"},
            {"url": gnews_url("iron ore price steel demand China Australia Brazil"), "tag": "GNews | Iron Ore"},
            {"url": gnews_url("lithium price battery EV demand supply"), "tag": "GNews | Lithium"},
            {"url": gnews_url("natural gas price LNG Europe Asia pipeline"), "tag": "GNews | Nat Gas/LNG"},
            {"url": gnews_url("rare earth price China export quota critical mineral"), "tag": "GNews | Rare Earth"},
            {"url": gnews_url("wheat corn soybean agriculture commodity price"), "tag": "GNews | Agriculture"},
        ],
        "汇率": [
            {"url": gnews_url("USD dollar index DXY strength weakness"), "tag": "GNews | USD/DXY"},
            {"url": gnews_url("CNY yuan USD exchange rate PBOC midpoint"), "tag": "GNews | CNY/USD"},
            {"url": gnews_url("EUR USD exchange rate euro dollar"), "tag": "GNews | EUR/USD"},
            {"url": gnews_url("JPY yen exchange rate dollar intervention"), "tag": "GNews | JPY"},
            {"url": gnews_url("emerging market currency crisis depreciation"), "tag": "GNews | EM Currency"},
        ],
        "债市+信用": [
            {"url": gnews_url("US treasury yield curve inversion bond market"), "tag": "GNews | US Treasury"},
            {"url": gnews_url("sovereign debt default credit rating downgrade"), "tag": "GNews | Sovereign Debt"},
            {"url": gnews_url("corporate bond yield spread credit risk default"), "tag": "GNews | Corp Bond"},
            {"url": gnews_url("CDS credit default swap spread risk"), "tag": "GNews | CDS"},
        ],
        "资本流动": [
            {"url": gnews_url("FDI foreign direct investment global flow 2026"), "tag": "GNews | FDI Flow"},
            {"url": gnews_url("portfolio investment flow emerging market capital"), "tag": "GNews | Portfolio Flow"},
            {"url": gnews_url("capital control hot money capital flight"), "tag": "GNews | Capital Control"},
            {"url": gnews_url("sovereign wealth fund investment allocation"), "tag": "GNews | SWF"},
        ],
        "本地语言搜索": [
            {"url": gnews_url("日銀 金融政策 金利 円 経済", hl="ja", gl="JP", ceid="JP:ja"), "tag": "GNews | JP 日央行"},
            {"url": gnews_url("央行 货币政策 利率 人民币 经济", hl="zh-CN", gl="CN", ceid="CN:zh-Hans"), "tag": "GNews | CN 央行/经济"},
        ],
        "独立RSS源": [
            {"url": "https://www.ft.com/rss/home", "tag": "FT Home"},
            {"url": "https://feeds.content.dowjones.io/public/rss/RSSWorldNews", "tag": "WSJ World"},
        ],
        "信号性查询": [
            # v3.3新增
            {"url": gnews_url('"emergency meeting" central bank rate decision'), "tag": "GNews | Signal: CB Emergency"},
            {"url": gnews_url('"warning" IMF World Bank BIS financial stability'), "tag": "GNews | Signal: IMF/BIS Warning"},
            {"url": gnews_url('"record high" "record low" market bond yield price'), "tag": "GNews | Signal: Market Record"},
        ],
        "专题精选": [
            {"url": gnews_url(topic="BUSINESS"), "tag": "GNews Topic | BUSINESS(US)"},
            {"url": gnews_url(topic="BUSINESS", hl="en-IN", gl="IN", ceid="IN:en"), "tag": "GNews Topic | BUSINESS(IN)"},
        ],
        "权威财经RSS": [
            {"url": "http://feeds.bbci.co.uk/news/business/rss.xml", "tag": "BBC Business"},
            {"url": "https://www.theguardian.com/business/rss", "tag": "Guardian Business"},
            {"url": "http://rss.cnn.com/rss/money_news_international.rss", "tag": "CNN Business"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
