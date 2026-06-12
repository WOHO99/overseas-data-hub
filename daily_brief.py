#!/usr/bin/env python3
"""
daily_brief.py v1.1 — 海外情报每日简报（主动推送心脏）
v1.1 变更：加载uri_map，必读TOP5标题加Obsidian链接
在 GitHub Actions 数据采集成功后运行，读取 index.json 生成精简简报，
通过 Resend SMTP 推送到邮箱。

环境变量：
  RESEND_API_KEY  — Resend API Key（也是SMTP密码）
  RECEIVE_EMAIL   — 接收邮箱地址
  SEND_FROM       — 发件人地址（默认 onboarding@resend.dev）
"""

import os
import json
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────────────────
SMTP_HOST = "smtp.resend.com"
SMTP_PORT = 465
SMTP_USER = "resend"

SEND_FROM = os.environ.get("SEND_FROM", "onboarding@resend.dev")
RECEIVE_EMAIL = os.environ.get("RECEIVE_EMAIL", "")
API_KEY = os.environ.get("RESEND_API_KEY", "")

DATA_DIR = Path("data")

# 模块中文名映射
MODULE_NAMES = {
    "global_business": "全球商业与产业链",
    "finance_global": "全球宏观与资本",
    "tech_industry": "全球科技与工业",
    "energy_commodities": "全球能源与大宗",
    "geopolitics_risk": "全球治理与地缘",
    "esg_sustainability": "ESG与可持续发展",
    "region_se_asia": "东南亚",
    "region_south_asia": "南亚",
    "region_middle_east": "中东",
    "region_latin_america": "拉美",
    "region_africa": "非洲",
    "region_europe": "欧洲",
    "region_cis": "独联体",
    "region_east_asia": "东亚(日韩)",
}


# ── 数据读取 ────────────────────────────────────────────────────
def load_index() -> dict:
    """读取 index.json，失败返回空dict。"""
    idx_path = DATA_DIR / "index.json"
    if idx_path.exists():
        with open(idx_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_uri_map(idx: dict) -> dict:
    """加载 obsidian URI 映射。Actions环境里uri_map在 uri_map/ 下。"""
    fetch_date = idx.get("fetch_date_utc", "")
    if not fetch_date:
        return {}
    # Actions环境：脚本在项目根目录，uri_map在 uri_map/ 下
    uri_map_path = Path("uri_map") / f"{fetch_date}.json"
    if uri_map_path.exists():
        with open(uri_map_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


# ── 态势判定 ────────────────────────────────────────────────────
def judge_posture(idx: dict) -> tuple[str, str, str]:
    """
    判定全局态势：(标签, 颜色CSS, 描述)
    红=有信号词触发  黄=无信号但high>100  绿=平稳
    """
    alerts = idx.get("global_signal_alerts", {})
    alert_count = len(alerts) if isinstance(alerts, dict) else 0
    global_high = idx.get("global_high", 0) or 0

    if alert_count > 0:
        severity = sum(alerts.values()) if isinstance(alerts, dict) else 0
        if severity >= 10 or alert_count >= 3:
            return ("高关注", "#dc2626", f"{alert_count}个信号词触发，强度{severity}")
        else:
            return ("需留意", "#d97706", f"{alert_count}个信号词触发，强度{severity}")
    elif global_high > 100:
        return ("需留意", "#d97706", f"无异常信号，但high priority文章{global_high}篇偏多")
    else:
        return ("态势平稳", "#16a34a", f"无异常信号，high priority {global_high}篇")


# ── 简报生成 ────────────────────────────────────────────────────
def generate_brief(idx: dict) -> tuple[str, str]:
    """
    生成简报。返回 (subject, html_body)。
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fetch_ts = idx.get("updated", idx.get("fetch_date_utc", today))
    global_total = idx.get("global_total", 0) or 0
    global_high = idx.get("global_high", 0) or 0
    global_medium = idx.get("global_medium", 0) or 0
    alerts = idx.get("global_signal_alerts", {})
    baselines = idx.get("signal_baselines", {})
    modules = idx.get("modules", {})
    top_articles = idx.get("high_priority_articles", [])

    # 态势
    posture_label, posture_color, posture_desc = judge_posture(idx)

    # 邮件主题
    has_signal = isinstance(alerts, dict) and len(alerts) > 0
    if has_signal:
        n = len(alerts)
        subject = f"Daily Brief: {today} - {n}个异常信号"
    else:
        subject = f"Daily Brief: {today} - 态势平稳"

    # ── HTML 构建 ────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;margin:0;padding:16px;background:#f5f5f5;color:#1a1a1a}}
.container{{max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1)}}
.header{{padding:20px 24px;border-bottom:1px solid #e5e5e5}}
.header h1{{margin:0;font-size:20px;font-weight:600}}
.header .meta{{margin-top:4px;font-size:13px;color:#666}}
.section{{padding:16px 24px;border-bottom:1px solid #f0f0f0}}
.section h2{{margin:0 0 12px;font-size:15px;font-weight:600;color:#333}}
.posture-badge{{display:inline-block;padding:3px 10px;border-radius:4px;color:#fff;font-size:13px;font-weight:600}}
.signal-item{{padding:6px 0;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #f5f5f5}}
.signal-item:last-child{{border-bottom:none}}
.signal-kw{{font-weight:500;font-size:14px}}
.signal-cnt{{font-size:13px;color:#666}}
.module-row{{display:flex;justify-content:space-between;padding:4px 0;font-size:13px}}
.module-name{{color:#333}}
.module-count{{font-weight:500}}
.article{{padding:8px 0;border-bottom:1px solid #f5f5f5}}
.article:last-child{{border-bottom:none}}
.article-title{{font-size:14px;font-weight:500;line-height:1.4}}
.article-meta{{font-size:12px;color:#888;margin-top:2px}}
.footer{{padding:16px 24px;font-size:11px;color:#999;text-align:center}}
table{{width:100%;border-collapse:collapse}}
th,td{{text-align:left;padding:6px 8px;font-size:13px;border-bottom:1px solid #f0f0f0}}
th{{color:#666;font-weight:500;font-size:12px}}
</style></head><body>
<div class="container">
<div class="header">
<h1>全球商业情报简报</h1>
<div class="meta">{fetch_ts} | 共{global_total}篇 | High {global_high} / Medium {global_medium}</div>
</div>
"""

    # ── 1. 全局态势 ─────────────────────────────────────────
    html += f"""
<div class="section">
<h2>全局态势</h2>
<span class="posture-badge" style="background:{posture_color}">{posture_label}</span>
<span style="margin-left:8px;font-size:14px">{posture_desc}</span>
</div>
"""

    # ── 2. 信号词雷达 ───────────────────────────────────────
    html += '<div class="section"><h2>信号词雷达</h2>'
    if isinstance(alerts, dict) and len(alerts) > 0:
        sorted_signals = sorted(alerts.items(), key=lambda x: x[1], reverse=True)
        html += '<table><tr><th>信号词</th><th>今日次数</th><th>基线</th><th>偏离</th></tr>'
        for kw, cnt in sorted_signals:
            base = baselines.get(kw, "?")
            try:
                deviation = f"+{cnt - base}" if isinstance(base, int) and cnt > base else str(cnt)
            except TypeError:
                deviation = str(cnt)
            html += f'<tr><td class="signal-kw">{kw}</td><td style="font-weight:600">{cnt}</td><td style="color:#888">{base}</td><td>{deviation}</td></tr>'
        html += '</table>'
    else:
        html += '<p style="font-size:14px;color:#666;margin:0">无异常信号，全部在基线内。</p>'
    html += '</div>'

    # ── 3. 赛道热度 ─────────────────────────────────────────
    html += '<div class="section"><h2>赛道热度 TOP 5</h2><table>'
    html += '<tr><th>赛道</th><th>High</th><th>Medium</th><th>总计</th></tr>'
    mod_list = []
    for mod_key, mod_data in modules.items():
        if isinstance(mod_data, dict):
            mod_list.append((
                MODULE_NAMES.get(mod_key, mod_key),
                mod_data.get("high", 0) or 0,
                mod_data.get("medium", 0) or 0,
                mod_data.get("total", 0) or 0,
            ))
    mod_list.sort(key=lambda x: x[1], reverse=True)
    for name, h, m, t in mod_list[:5]:
        html += f'<tr><td class="module-name">{name}</td><td class="module-count">{h}</td><td>{m}</td><td>{t}</td></tr>'
    html += '</table></div>'

    # ── 4. 必读 Top 5 ────────────────────────────────────────
    # 加载uri_map（Actions环境里uri_map在同级目录uri_map/下）
    uri_map = load_uri_map(idx)
    html += '<div class="section"><h2>必读标题 TOP 5</h2>'
    sorted_articles = sorted(top_articles, key=lambda x: x.get("priority", 0), reverse=True)
    for i, art in enumerate(sorted_articles[:5], 1):
        title = art.get("title", "")
        source = art.get("source", "")
        priority = art.get("priority", 0)
        category = art.get("category", "")
        link = art.get("link", "")
        # Obsidian链接
        obsidian_html = ""
        if link and link in uri_map:
            obsidian_uri = uri_map[link].get("obsidian_uri", "")
            if obsidian_uri:
                obsidian_html = f' <a href="{obsidian_uri}" style="font-size:11px;color:#16a34a;text-decoration:none">📂Obsidian</a>'
        html += f"""<div class="article">
<div class="article-title">{i}. {title}{obsidian_html}</div>
<div class="article-meta">{source} | P{priority:.0f} | {category}</div>
</div>"""
    html += '</div>'

    # ── 底部 ────────────────────────────────────────────────
    html += f"""
<div class="footer">
数据源：GitHub Actions overseas-data-hub | 本信息仅供参考，不构成任何投资、法律或商业决策建议
</div>
</div></body></html>"""

    return subject, html


# ── 发送邮件 ────────────────────────────────────────────────────
def send_brief(subject: str, html_body: str) -> None:
    """发送HTML简报邮件。"""
    if not API_KEY:
        raise RuntimeError("RESEND_API_KEY 环境变量未设置")
    if not RECEIVE_EMAIL:
        raise RuntimeError("RECEIVE_EMAIL 环境变量未设置")

    msg = MIMEMultipart("alternative")
    msg["From"] = SEND_FROM
    msg["To"] = RECEIVE_EMAIL
    msg["Subject"] = subject

    # 纯文本备选（简易去HTML标签）
    import re
    plain = re.sub(r'<[^>]+>', '', html_body)
    plain = re.sub(r'\n{3,}', '\n\n', plain)

    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(SMTP_USER, API_KEY)
        server.sendmail(SEND_FROM, [RECEIVE_EMAIL], msg.as_string())

    print(f"[OK] 简报邮件已发送: {SEND_FROM} -> {RECEIVE_EMAIL}")
    print(f"     主题: {subject}")


# ── 主流程 ───────────────────────────────────────────────────────
def main():
    print("=" * 50)
    print("海外情报每日简报 — 主动推送")
    print("=" * 50)

    # 1. 读取数据
    print("[1/2] 读取 index.json 生成简报 ...")
    idx = load_index()
    if not idx:
        print("[WARN] index.json 不存在或为空，跳过简报生成")
        return

    subject, html_body = generate_brief(idx)
    print(f"  主题: {subject}")

    # 2. 发送
    print("[2/2] 发送简报邮件 ...")
    send_brief(subject, html_body)

    print("\n简报推送完成")


if __name__ == "__main__":
    main()
