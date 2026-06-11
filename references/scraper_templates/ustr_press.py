#!/usr/bin/env python3
"""
USTR Press Releases 爬虫验证脚本 v0.1
========================================
目的：验证 GitHub Actions 环境能否抓取 USTR Press Releases 页面，
     为 Phase 5 "爬虫脚本模板"路线提供可行性数据。

目标页面：https://ustr.gov/about-us/policy-offices/press-office/press-releases
页面结构：静态HTML，包含日期+标题列表，无需JS渲染（v0.1验证通过）

运行方式：
  python ustr_press.py [--limit N] [--json]

输出：
  --limit N  只显示最近N条（默认10）
  --json     输出JSON格式

依赖：requests, beautifulsoup4（均为 requirements.txt 已有/轻量依赖）
"""

import sys
import json
import re
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: 需要安装 requests 和 beautifulsoup4", file=sys.stderr)
    print("  pip install requests beautifulsoup4", file=sys.stderr)
    sys.exit(1)

URL = "https://ustr.gov/about-us/policy-offices/press-office/press-releases"
TIMEOUT = 15
HEADERS = {
    "User-Agent": "OverseasDataHub/0.1 (https://github.com/WOHO99/overseas-data-hub)",
    "Accept": "text/html",
}


def fetch_ustr_press(limit=10):
    """抓取USTR Press Releases页面，解析返回最近N条。"""
    try:
        resp = requests.get(URL, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        print("ERROR: 请求超时（{}s）".format(TIMEOUT), file=sys.stderr)
        return []
    except requests.exceptions.HTTPError as e:
        print("ERROR: HTTP {} - {}".format(e.response.status_code, e), file=sys.stderr)
        return []
    except requests.exceptions.ConnectionError:
        print("ERROR: 连接失败（可能IP被封或DNS不可达）", file=sys.stderr)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # 页面底部有结构化列表：日期 + 标题
    # 格式：2026-06-10\nTitle Here\n2026-06-09\nAnother Title\n
    # 找到最后一个大的文本块（包含所有日期+标题）
    articles = []

    # 策略：查找所有文本节点中匹配日期模式的
    text_content = soup.get_text(separator="\n")

    # 匹配 "YYYY-MM-DD" 后面跟标题的模式
    pattern = re.compile(r"(\d{4}-\d{2}-\d{2})\s*\n\s*(.+?)(?:\n|$)")
    matches = pattern.findall(text_content)

    for date_str, title in matches:
        title = title.strip()
        if not title or len(title) < 10:  # 过滤掉短噪音
            continue
        if any(skip in title.lower() for skip in ["press office", "internship", "breadcrumb"]):
            continue

        # 去重（同一标题可能匹配多次）
        if articles and articles[-1]["title"] == title:
            continue

        try:
            pub_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            continue

        # 构造链接（USTR URL模式）
        slug = title.lower().replace(" ", "-")[:80]
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        link = f"https://ustr.gov/about-us/policy-offices/press-office/press-releases/{date_str[:4]}/{datetime.strptime(date_str, '%Y-%m-%d').strftime('%B').lower()}/{slug}"

        articles.append({
            "title": title,
            "link": link,
            "published": pub_date,
            "source": "USTR",
        })

    # 按日期降序排序，去重
    seen = set()
    unique = []
    for a in sorted(articles, key=lambda x: x["published"], reverse=True):
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)

    return unique[:limit]


def main():
    limit = 10
    output_json = False

    for arg in sys.argv[1:]:
        if arg == "--json":
            output_json = True
        elif arg == "--limit":
            idx = sys.argv.index(arg)
            if idx + 1 < len(sys.argv):
                limit = int(sys.argv[idx + 1])

    print(f"[INFO] 抓取USTR Press Releases（最近{limit}条）...", file=sys.stderr)
    articles = fetch_ustr_press(limit=limit)

    if not articles:
        print("[WARN] 未抓取到任何条目，可能页面结构变更或网络问题", file=sys.stderr)
        sys.exit(1)

    if output_json:
        print(json.dumps(articles, ensure_ascii=False, indent=2))
    else:
        for i, a in enumerate(articles, 1):
            print(f"{i}. [{a['published']}] {a['title']}")

    # 验证报告
    print(f"\n[验证报告]", file=sys.stderr)
    print(f"  抓取条目数: {len(articles)}", file=sys.stderr)
    print(f"  最新条目: {articles[0]['published']} - {articles[0]['title'][:60]}...", file=sys.stderr)
    print(f"  状态: OK", file=sys.stderr)


if __name__ == "__main__":
    main()
