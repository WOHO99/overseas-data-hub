#!/usr/bin/env python3
"""
verify_gnews_params.py — GNews RSS 参数验证脚本
在 GitHub Actions 上运行，验证：
  1. when:7d 编码是否生效
  2. gl/ceid 新组合是否可用
  3. Topic Feed 是否返回数据
  4. 新增直连RSS源是否可达
"""

import feedparser
import urllib.parse
import time
import sys

RESULTS = []


def test_feed(label, url, min_items=1, timeout=20):
    """测试RSS feed是否返回有效数据"""
    t0 = time.time()
    try:
        feed = feedparser.parse(url)
        elapsed = time.time() - t0
        count = len(feed.entries)
        if count >= min_items:
            RESULTS.append((label, "OK", f"{count} items ({elapsed:.1f}s)", url))
            print(f"  [OK] {label}: {count} items ({elapsed:.1f}s)")
            return count
        elif count > 0:
            RESULTS.append((label, "WARN", f"{count} items, expected>={min_items} ({elapsed:.1f}s)", url))
            print(f"  [WARN] {label}: {count} items (low)")
            return count
        else:
            error = getattr(feed, 'bozo_exception', 'empty feed')
            RESULTS.append((label, "FAIL", f"0 items — {str(error)[:80]}", url))
            print(f"  [FAIL] {label}: 0 items")
            return 0
    except Exception as e:
        RESULTS.append((label, "FAIL", str(e)[:100], url))
        print(f"  [FAIL] {label}: {str(e)[:80]}")
        return -1


def search_url(q, hl="en-US", gl="US", ceid="US:en", num=10, when=None):
    base = "https://news.google.com/rss/search"
    q_full = f"{q} when:{when}" if when else q
    q_enc = urllib.parse.quote(q_full, safe=':')
    return f"{base}?q={q_enc}&hl={hl}&gl={gl}&ceid={ceid}&num={num}"


def topic_url(topic, hl="en-US", gl="US", ceid="US:en"):
    t_enc = urllib.parse.quote(topic)
    return f"https://news.google.com/rss/headlines/section/topic/{t_enc}?hl={hl}&gl={gl}&ceid={ceid}"


def main():
    print("=" * 70)
    print("PART 1: when:7d encoding verification")
    print("=" * 70)

    q = "supply chain tariff trade"
    c_no = test_feed("no when", search_url(q, num=10, when=None))
    c_7d = test_feed("when:7d", search_url(q, num=10, when="7d"))
    c_24h = test_feed("when:24h", search_url(q, num=10, when="24h"))
    
    if c_7d > 0:
        print(f"  --> when:7d VALID (returns {c_7d} items)")
    else:
        print(f"  --> when:7d MAY BE BROKEN (0 items)")

    print("\n" + "=" * 70)
    print("PART 2: gl/ceid new combos")
    print("=" * 70)

    valid_gl = []
    combos = [
        ("SG en-US", "Southeast Asia trade investment", "en-US", "SG", "SG:en"),
        ("SG en-SG", "Southeast Asia trade investment", "en-SG", "SG", "SG:en"),
        ("IN en-US", "India trade manufacturing FDI", "en-US", "IN", "IN:en"),
        ("IN en-IN", "India trade manufacturing FDI", "en-IN", "IN", "IN:en"),
        ("AE en-US", "Gulf trade investment economy", "en-US", "AE", "AE:en"),
        ("AE en-AE", "Gulf trade investment economy", "en-AE", "AE", "AE:en"),
        ("JP en-US", "Japan trade export economy", "en-US", "JP", "JP:en"),
        ("JP en-JP", "Japan trade export economy", "en-JP", "JP", "JP:en"),
        ("GB en-GB", "Europe economy trade regulation", "en-GB", "GB", "GB:en"),
        ("MX en-US", "Latin America trade economy", "en-US", "MX", "MX:en"),
        ("MX es-419", "Latin America trade economy", "es-419", "MX", "MX:es-419"),
        ("ZA en-US", "Africa trade investment economy", "en-US", "ZA", "ZA:en"),
        ("ZA en-ZA", "Africa trade investment economy", "en-ZA", "ZA", "ZA:en"),
        ("RU en-US", "Russia economy sanctions trade", "en-US", "RU", "RU:ru"),
        ("RU ru", "Россия экономика санкции", "ru", "RU", "RU:ru"),
    ]

    for tag, q2, hl, gl, ceid in combos:
        c = test_feed(tag, search_url(q2, hl=hl, gl=gl, ceid=ceid, num=10, when="7d"))
        if c > 0:
            valid_gl.append(tag)

    print(f"\n  Valid gl/ceid combos: {valid_gl}")

    print("\n" + "=" * 70)
    print("PART 3: Topic Feeds")
    print("=" * 70)

    topic_tests = [
        ("BUSINESS US", "BUSINESS", "en-US", "US", "US:en"),
        ("BUSINESS SG", "BUSINESS", "en-US", "SG", "SG:en"),
        ("BUSINESS IN", "BUSINESS", "en-US", "IN", "IN:en"),
        ("BUSINESS GB", "BUSINESS", "en-GB", "GB", "GB:en"),
        ("TECHNOLOGY US", "TECHNOLOGY", "en-US", "US", "US:en"),
        ("WORLD US", "WORLD", "en-US", "US", "US:en"),
        ("WORLD GB", "WORLD", "en-GB", "GB", "GB:en"),
        ("WORLD JP", "WORLD", "ja", "JP", "JP:ja"),
        ("WORLD SG", "WORLD", "en-US", "SG", "SG:en"),
        ("WORLD IN", "WORLD", "en-US", "IN", "IN:en"),
        ("WORLD AE", "WORLD", "en-US", "AE", "AE:en"),
        ("WORLD MX", "WORLD", "es-419", "MX", "MX:es-419"),
        ("WORLD ZA", "WORLD", "en-US", "ZA", "ZA:en"),
        ("WORLD RU", "WORLD", "ru", "RU", "RU:ru"),
        ("SCIENCE US", "SCIENCE", "en-US", "US", "US:en"),
        ("HEALTH US", "HEALTH", "en-US", "US", "US:en"),
    ]

    valid_topics = []
    for tag, topic, hl, gl, ceid in topic_tests:
        c = test_feed(tag, topic_url(topic, hl, gl, ceid))
        if c > 0:
            valid_topics.append(tag)

    print(f"\n  Valid Topic Feeds: {valid_topics}")

    print("\n" + "=" * 70)
    print("PART 4: New direct RSS sources")
    print("=" * 70)

    direct_rss = [
        ("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
        ("BBC Business", "http://feeds.bbci.co.uk/news/business/rss.xml"),
        ("BBC Tech", "http://feeds.bbci.co.uk/news/technology/rss.xml"),
        ("BBC Sci/Env", "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
        ("BBC N.America", "http://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml"),
        ("BBC UK", "http://feeds.bbci.co.uk/news/uk/rss.xml"),
        ("CNN World", "http://rss.cnn.com/rss/cnn_world.rss"),
        ("CNN Business", "http://rss.cnn.com/rss/money_news_international.rss"),
        ("CNN Tech", "http://rss.cnn.com/rss/cnn_tech.rss"),
        ("Guardian World", "https://www.theguardian.com/world/rss"),
        ("Guardian Business", "https://www.theguardian.com/business/rss"),
        ("Guardian Tech", "https://www.theguardian.com/technology/rss"),
        ("Guardian Env", "https://www.theguardian.com/environment/rss"),
        ("Guardian US", "https://www.theguardian.com/us-news/rss"),
        ("Guardian UK", "https://www.theguardian.com/uk/rss"),
        ("NPR World", "https://feeds.npr.org/1001/rss.xml"),
        ("Reuters Agency", "https://www.reutersagency.com/feed/?best-regions=world&post_type=best"),
        ("Le Monde", "https://www.lemonde.fr/rss/une.xml"),
        ("Der Spiegel", "http://www.spiegel.de/schlagzeilen/index.rss"),
        ("El Pais EN", "https://feeds.elpais.com/mrss-s/list/ep/site/english.elpais.com/section/section"),
        ("Times of India", "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"),
        ("Mail&Guardian ZA", "https://mg.co.za/feed/"),
    ]

    valid_rss = []
    for tag, url in direct_rss:
        c = test_feed(tag, url)
        if c > 0:
            valid_rss.append(tag)

    print(f"\n  Valid direct RSS: {valid_rss}")

    # 总结
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    ok = sum(1 for r in RESULTS if r[1] == "OK")
    warn = sum(1 for r in RESULTS if r[1] == "WARN")
    fail = sum(1 for r in RESULTS if r[1] == "FAIL")
    print(f"  Total: {len(RESULTS)}  OK: {ok}  WARN: {warn}  FAIL: {fail}")
    print()
    print("  gl/ceid valid combos:", valid_gl)
    print("  Topic Feeds valid:", valid_topics)
    print("  Direct RSS valid:", valid_rss)
    print()
    print("  FAILED items:")
    for label, status, detail, url in RESULTS:
        if status == "FAIL":
            print(f"    - {label}: {detail}")


if __name__ == "__main__":
    main()
