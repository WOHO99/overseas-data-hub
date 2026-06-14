#!/usr/bin/env python3
"""
global_business.py — 全球商业与产业链重构模块
v3.3: 从"出海商业"升级，不再只看"中国公司出去"
覆盖：全球产业链转移、跨国公司全球布局、各国制造业回流/新兴制造中心
无论是谁在动，只要是产业链在动，就抓
v3.4: Batch A新增1个直连RSS源(Reuters Company)
v3.5: Batch D新增6个直连RSS源(NYT Business/Reuters Top News/Business blogs)
"""

import sys
import os
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import run_module, gnews_url, load_keywords

_config_dir = os.path.join(_scripts_dir, "config")
_module_name = "global_business"
_core_kw, _important_kw, _aux_kw, _signal_kw, _exclude_kw = load_keywords(_config_dir, _module_name)

CONFIG = {
    "name": "全球商业与产业链重构",
    "output_file": "global_business.json",
    "max_articles": 800,
    "core_keywords": _core_kw,
    "important_keywords": _important_kw,
    "aux_keywords": _aux_kw,
    "signal_keywords": _signal_kw,
    "exclude_keywords": _exclude_kw,
    "feeds": {
        "全球财经": [
            {"url": "https://asia.nikkei.com/rss/feed/nar", "tag": "Nikkei Asia"},
            {"url": "https://www.scmp.com/rss/91/feed", "tag": "SCMP Economy"},
            {"url": "https://feeds.feedburner.com/bloomberg-markets-news", "tag": "Bloomberg Markets"},
            {"url": "https://www.reuters.com/rssFeed/businessNews", "tag": "Reuters Business"},
            {"url": "https://rss.cnbc.com/headlines/world/", "tag": "CNBC World"},
            # v3.4 Batch A: Reuters Company直连RSS
            {"url": "http://feeds.reuters.com/reuters/companyNews", "tag": "Reuters Company"},
            {"url": gnews_url("China trade tariff 301 supply chain"), "tag": "GNews | China Trade/Tariff"},
            {"url": gnews_url("global economy recession inflation interest rate 2026"), "tag": "GNews | Global Macro"},
            {"url": gnews_url("commodity price oil copper lithium 2026"), "tag": "GNews | Commodity"},
        ],
        "科技+出海": [
            {"url": "https://techcrunch.com/tag/china/feed/", "tag": "TC | China"},
            {"url": "https://techcrunch.com/tag/southeast-asia/feed/", "tag": "TC | SE Asia"},
            {"url": "https://techcrunch.com/tag/fintech/feed/", "tag": "TC | Fintech"},
            {"url": "https://techcrunch.com/tag/saas/feed/", "tag": "TC | SaaS"},
            {"url": "https://www.scmp.com/rss/92/feed", "tag": "SCMP Tech"},
            {"url": gnews_url("Chinese companies going global overseas expansion"), "tag": "GNews | China Going Global"},
            {"url": gnews_url("Chinese tech overseas TikTok Temu Shein BYD"), "tag": "GNews | Chinese Tech Overseas"},
            {"url": gnews_url("Southeast Asia startup funding VC investment 2026"), "tag": "GNews | SE Asia Startup"},
            {"url": gnews_url("cross-border e-commerce Amazon seller Temu Shein"), "tag": "GNews | Cross-border E-com"},
        ],
        "政策+制裁": [
            {"url": "https://www.federalregister.gov/api/v1/documents.rss?conditions%5Bagencies%5D%5B%5D=office-of-the-united-states-trade-representative&conditions%5Btype%5D%5B%5D=NOTICE", "tag": "FedReg | USTR"},
            {"url": "https://www.federalregister.gov/api/v1/documents.rss?conditions%5Bagencies%5D%5B%5D=department-of-commerce-bureau-of-industry-and-security&conditions%5Btype%5D%5B%5D=RULE", "tag": "FedReg | BIS"},
            {"url": "https://www.federalregister.gov/api/v1/documents.rss?conditions%5Bagencies%5D%5B%5D=department-of-defense&conditions%5Btype%5D%5B%5D=NOTICE", "tag": "FedReg | DoD"},
            {"url": gnews_url("USTR 301 tariff investigation 2026"), "tag": "GNews | USTR 301"},
            {"url": gnews_url("1260H Chinese military companies sanctions"), "tag": "GNews | 1260H"},
            {"url": gnews_url("entity list export control chip ban semiconductor"), "tag": "GNews | Entity List/Chip"},
            {"url": gnews_url("EU regulation digital services act AI act data protection"), "tag": "GNews | EU Regulation"},
            {"url": gnews_url("forced labor Xinjiang UFLPA import ban"), "tag": "GNews | Forced Labor"},
            {"url": gnews_url("CFIUS review foreign investment national security"), "tag": "GNews | CFIUS"},
        ],
        "全球产业链重构": [
            # v3.3新增：全球产业链转移（不限中国视角）
            {"url": gnews_url("global supply chain reshoring nearshoring friendshoring factory relocation"), "tag": "GNews | SC Restructuring"},
            {"url": gnews_url("India manufacturing rise electronic vehicle semiconductor plant"), "tag": "GNews | India Mfg Rise"},
            {"url": gnews_url("Mexico nearshoring manufacturing investment USMCA factory"), "tag": "GNews | Mexico Nearshoring"},
            {"url": gnews_url("global industrial policy CHIPS Act IRA EU Green Deal industrial plan"), "tag": "GNews | Industrial Policy"},
            {"url": gnews_url("multinational supply chain diversification strategy 2026"), "tag": "GNews | MNC Diversification"},
            {"url": gnews_url("Vietnam Indonesia manufacturing hub alternative China"), "tag": "GNews | ASEAN Mfg Hub"},
            {"url": gnews_url("Eastern Europe manufacturing investment Poland Czech Hungary"), "tag": "GNews | E.Europe Mfg"},
        ],
        "东南亚本地": [
            {"url": "https://www.thejakartapost.com/rss", "tag": "Jakarta Post"},
            {"url": "https://www.straitstimes.com/rss/breaking-news", "tag": "Straits Times"},
            {"url": "https://www.bangkokpost.com/rss/data/breakingnews.xml", "tag": "Bangkok Post"},
            {"url": "https://www.thestar.com.my/rss/News", "tag": "The Star MY"},
            {"url": gnews_url("Vietnam export trade tariff manufacturing"), "tag": "GNews | Vietnam Trade"},
            {"url": gnews_url("Indonesia tariff export nickel critical minerals"), "tag": "GNews | Indonesia Trade"},
            {"url": gnews_url("Thailand export manufacturing investment"), "tag": "GNews | Thailand Trade"},
            {"url": gnews_url("Philippines trade export BPO investment 2026"), "tag": "GNews | Philippines"},
            {"url": gnews_url("Malaysia semiconductor trade investment export"), "tag": "GNews | Malaysia"},
            {"url": gnews_url("Cambodia garment manufacturing export tariff"), "tag": "GNews | Cambodia"},
            {"url": gnews_url("ASEAN free trade RCEP CPTPP agreement"), "tag": "GNews | ASEAN FTA"},
        ],
        "本地语言搜索": [
            {"url": gnews_url("关税 制裁 出口管制 供应链 贸易战 301", hl="zh-CN", gl="CN", ceid="CN:zh-Hans"), "tag": "GNews | CN 关税/制裁"},
        ],
        "信号性查询": [
            # v3.3新增：信号性词汇查询
            {"url": gnews_url('"supply disruption" "force majeure" supply chain trade'), "tag": "GNews | Signal: SC Disruption"},
            {"url": gnews_url('"sanctions announced" "new restrictions" trade export control'), "tag": "GNews | Signal: New Sanctions"},
            {"url": gnews_url('"first ever" breakthrough discovery trade technology'), "tag": "GNews | Signal: First Ever"},
        ],
        "专题精选": [
            {"url": gnews_url(topic="BUSINESS"), "tag": "GNews Topic | BUSINESS(US)"},
            {"url": gnews_url(topic="WORLD"), "tag": "GNews Topic | WORLD(US)"},
        ],
        "权威媒体RSS": [
            {"url": "http://feeds.bbci.co.uk/news/world/rss.xml", "tag": "BBC World"},
            {"url": "http://feeds.bbci.co.uk/news/business/rss.xml", "tag": "BBC Business"},
            {"url": "http://rss.cnn.com/rss/cnn_world.rss", "tag": "CNN World"},
            {"url": "https://www.theguardian.com/world/rss", "tag": "Guardian World"},
            {"url": "https://www.theguardian.com/business/rss", "tag": "Guardian Business"},
            {"url": "https://feeds.npr.org/1001/rss.xml", "tag": "NPR World"},
        ],
        "新增直连RSS(D)": [
            # v3.5 Batch D: 6个新增
            {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml", "tag": "NYT Business"},
            {"url": "http://feeds.reuters.com/reuters/topNews", "tag": "Reuters Top News"},
            {"url": "https://bothsidesofthetable.com/feed", "tag": "Both Sides of the Table"},
            {"url": "https://www.ycombinator.com/blog/rss", "tag": "Y Combinator Blog"},
            {"url": "http://marginalrevolution.com/feed/", "tag": "Marginal Revolution"},
            {"url": "https://ritholtz.com/feed/", "tag": "The Big Picture"},
        ],
    },
}

if __name__ == "__main__":
    run_module(CONFIG)
