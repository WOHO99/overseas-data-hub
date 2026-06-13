#!/usr/bin/env python3
"""
gen_unified_html.py v1.0 — 全球视野统一HTML生成器
合并 generate_daily_html.py (仪表盘) + gen_reader_v2.py (懒加载Reader) 为单文件

设计原则：
1. 自包含单文件（数据嵌 <script> JSON 标签，不依赖外部文件）
2. 顶部：6区块仪表盘（态势灯/信号雷达/必读Top10/四新速览/热力图/中企风险）
3. 下方：懒加载文章浏览器（50篇/页+全文展开+source:语法+模块筛选）
4. 侧边栏：模块数据统计 + 信源TOP30
5. 嵌入数据用 minified JSON，JS 懒渲染，8355篇文件约6-7MB（vs 内联HTML 9.4MB）

用法：
  python gen_unified_html.py <data_dir> [output.html]
"""

import json, os, sys, html as html_mod
from pathlib import Path
from datetime import datetime
from collections import Counter

try:
    import yaml
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml", "-q"])
    import yaml

# ── 配置 ──────────────────────────────────────────────────────────

def load_classification(config_path=None):
    if config_path is None:
        script_dir = Path(__file__).resolve().parent
        for candidate in [
            script_dir.parent / "config" / "classification.yaml",
            script_dir / "config" / "classification.yaml",
            Path(r"D:\TeleClaw\overseas-data\config\classification.yaml"),
        ]:
            if candidate.exists():
                config_path = candidate
                break
    if config_path is None or not Path(config_path).exists():
        raise FileNotFoundError("classification.yaml not found")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)

_CFG = load_classification()
MODULE_ORDER = _CFG["modules"]["order"]
MODULE_NAMES = _CFG["modules"]["names"]
SKIP_FILES = set(_CFG["modules"]["skip_files"])
CATEGORY_TO_COUNTRY = _CFG["country"]["category_map"]
COUNTRY_KEYWORDS = _CFG["country"]["keyword_map"]
MODULE_COUNTRY_DEFAULTS = _CFG["country"]["module_defaults"]
CATEGORY_TO_TOPIC = _CFG["topic"]["category_map"]
TOPIC_KEYWORDS = _CFG["topic"]["keyword_map"]
MODULE_TOPIC_DEFAULTS = _CFG["topic"]["module_defaults"]
NEW_MODULES = {"cross_border_ecommerce", "trade_import_export", "global_risk", "chinese_firms_overseas"}
CHINESE_FIRMS_MODULES = {"chinese_firms_overseas", "global_risk"}

# ── 工具函数 ──────────────────────────────────────────────────────

def esc(s):
    return html_mod.escape(str(s))

def classify_country(article):
    cat = article.get("category", "")
    title = article.get("title", "")
    source = article.get("source", "")
    combined = f"{title} {source}"
    if cat in CATEGORY_TO_COUNTRY:
        return CATEGORY_TO_COUNTRY[cat]
    for country, keywords in COUNTRY_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                return country
    return MODULE_COUNTRY_DEFAULTS.get(article.get("_module", ""), "全球")

def classify_topic(article):
    cat = article.get("category", "")
    title = article.get("title", "")
    if cat in CATEGORY_TO_TOPIC:
        return CATEGORY_TO_TOPIC[cat]
    combined = title.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in combined:
                return topic
    return MODULE_TOPIC_DEFAULTS.get(article.get("_module", ""), "综合")

def priority_class(p):
    if p >= 15: return "high"
    if p >= 10: return "medium"
    return "low"

def priority_label(p):
    if p >= 15: return "高"
    if p >= 10: return "中"
    return "低"

def _fmt_pubdate(article):
    pb = article.get("published_beijing", "") if isinstance(article, dict) else ""
    if pb and len(pb) >= 10:
        return pb[:10]
    pub_str = article.get("published", "") if isinstance(article, dict) else ""
    if not pub_str:
        return ""
    for fmt in ["%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"]:
        try:
            return datetime.strptime(pub_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    if len(pub_str) >= 10 and pub_str[4] == "-" and pub_str[7] == "-":
        return pub_str[:10]
    return ""

# ── 主流程 ──────────────────────────────────────────────────────

def generate(data_dir: Path, output_path: Path):
    # 1. 读取index
    idx = {}
    idx_path = data_dir / "index.json"
    if idx_path.exists():
        with open(idx_path, encoding="utf-8") as f:
            idx = json.load(f)
    fetch_date = idx.get("fetch_date_utc", "unknown")
    global_total = idx.get("global_total", "?")
    global_high = idx.get("global_high", "?")
    global_med = idx.get("global_medium", "?")

    # 2. 读取signal_summary
    triggered_signals = []
    sig_path = data_dir / "signal_summary.json"
    if sig_path.exists():
        with open(sig_path, encoding="utf-8") as f:
            sig = json.load(f)
        triggered_signals = [s for s in sig.get("signals", []) if isinstance(s, dict) and s.get("triggered")]

    # 3. 读取所有文章 + 标注
    all_articles = []
    module_list = []
    source_stats = {}

    for mk in MODULE_ORDER:
        jf = data_dir / f"{mk}.json"
        if not jf.exists() or jf.name in SKIP_FILES:
            continue
        with open(jf, encoding="utf-8") as f:
            d = json.load(f)
        articles = d.get("articles", [])
        m_total = d.get("total", len(articles))
        m_hp = d.get("high_priority", 0)
        m_mp = d.get("medium_priority", 0)
        sigs = d.get("signal_alerts", {})
        sig_str = ", ".join(f"{k}({v})" for k, v in sigs.items()) if sigs else ""
        cn = MODULE_NAMES.get(mk, mk)
        module_list.append({"id": mk, "name": cn, "total": m_total, "high": m_hp, "med": m_mp, "signals": sig_str})

        for a in articles:
            a["_module"] = mk
            a["_country"] = classify_country(a)
            a["_topic"] = classify_topic(a)
            all_articles.append(a)
            # 统计信源
            sd = a.get("source_detail", a.get("source", ""))
            if isinstance(sd, dict):
                src_name = sd.get("name", sd.get("url", ""))
            else:
                src_name = str(sd)
            src_base = a.get("source", "")
            display_src = src_name if src_name and src_name != src_base else src_base
            if display_src:
                source_stats[display_src] = source_stats.get(display_src, 0) + 1

    total_articles = len(all_articles)
    high_count = sum(1 for a in all_articles if a.get("priority", 0) >= 15)
    sig_count = len(triggered_signals)

    # 4. 仪表盘数据准备
    # 态势灯
    if sig_count >= 5 or high_count / max(total_articles, 1) > 0.1:
        sit_level, sit_color, sit_desc = "RED", "#ff4d6a", "高风险态势"
    elif sig_count >= 2 or high_count / max(total_articles, 1) > 0.05:
        sit_level, sit_color, sit_desc = "YELLOW", "#f5a623", "关注态势"
    else:
        sit_level, sit_color, sit_desc = "GREEN", "#34d399", "平稳态势"

    # 数据时效
    try:
        fetch_dt = datetime.strptime(fetch_date, "%Y-%m-%d")
        age_h = (datetime.now() - fetch_dt).total_seconds() / 3600
        if age_h <= 24:
            freshness, freshness_text = "fresh", f"{int(age_h)}h前"
        elif age_h <= 72:
            freshness, freshness_text = "aging", f"{int(age_h)}h前"
        else:
            freshness, freshness_text = "stale", f"{int(age_h/24)}天前"
    except ValueError:
        freshness, freshness_text = "unknown", "?"

    # 信号雷达
    radar_data = []
    if triggered_signals:
        max_cnt = max(s.get("today_count", 0) for s in triggered_signals)
        for s in triggered_signals[:10]:
            cnt = s.get("today_count", 0)
            base = s.get("baseline", 3)
            pct = min(cnt / max(max_cnt, 1) * 100, 100)
            base_pct = min(base / max(max_cnt, 1) * 100, 100)
            bar_color = "var(--high)" if cnt >= base * 3 else "var(--signal)" if cnt > base else "var(--text3)"
            radar_data.append({"kw": s.get("keyword", "?"), "cnt": cnt, "base": base,
                               "pct": round(pct), "base_pct": round(base_pct), "color": bar_color})

    # 必读Top10
    top10 = sorted(all_articles, key=lambda x: x.get("priority", 0), reverse=True)[:10]

    # 四新速览
    newmod_data = []
    for mk in NEW_MODULES:
        if mk not in MODULE_NAMES:
            continue
        cn = MODULE_NAMES[mk]
        arts = [a for a in all_articles if a.get("_module") == mk]
        m_high = sum(1 for a in arts if a.get("priority", 0) >= 15)
        m_sig = sum(1 for a in arts if a.get("signal_keywords"))
        top3 = sorted(arts, key=lambda x: x.get("priority", 0), reverse=True)[:3]
        newmod_data.append({"name": cn, "total": len(arts), "high": m_high, "sig": m_sig, "top3": top3})

    # 热力图
    heatmap = []
    for mk in MODULE_ORDER:
        cn = MODULE_NAMES.get(mk, mk)
        arts = [a for a in all_articles if a.get("_module") == mk]
        m_total = len(arts)
        m_high = sum(1 for a in arts if a.get("priority", 0) >= 15)
        m_sig = sum(1 for a in arts if a.get("signal_keywords"))
        if m_total == 0:
            heat = 0
        else:
            heat = min(m_high / max(m_total, 1) * 5, 1.0)
        if m_sig > 0:
            heat = max(heat, 0.5)
        heat_class = "heat-hot" if heat >= 0.7 else "heat-warm" if heat >= 0.4 else "heat-cool" if heat > 0 else "heat-cold"
        is_new = mk in NEW_MODULES
        heatmap.append({"id": mk, "name": cn, "total": m_total, "high": m_high, "sig": m_sig, "heat": heat_class, "is_new": is_new})

    # 中企风险
    risk_arts = sorted(
        [a for a in all_articles if a.get("_module") in CHINESE_FIRMS_MODULES and a.get("priority", 0) >= 10],
        key=lambda x: x.get("priority", 0), reverse=True
    )[:15]

    # 5. 准备JS嵌入数据 (compact JSON for articles)
    articles_compact = []
    fulltexts = {}
    for i, a in enumerate(all_articles):
        pub = a.get("published_beijing", "") or a.get("published", "")
        pri = a.get("priority", 0)
        try:
            pri_val = float(pri)
        except (ValueError, TypeError):
            pri_val = 0
        level = "high" if pri_val >= 15 else ("medium" if pri_val >= 10 else "low")
        ft = a.get("full_text", "")
        has_ft = bool(ft and len(ft) > 100)
        summary = (a.get("summary", "") or "").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ")[:500]
        sd = a.get("source_detail", a.get("source", ""))
        if isinstance(sd, dict):
            src_name = sd.get("name", sd.get("url", ""))
        else:
            src_name = str(sd)
        src_base = a.get("source", "")
        display_src = src_name if src_name and src_name != src_base else src_base

        if has_ft and ft:
            fulltexts[str(i)] = ft
        articles_compact.append({
            "t": a.get("title", ""),
            "s": display_src,
            "p": pub[:16] if pub else "",
            "pr": pri_val,
            "l": level,
            "m": a.get("_module", ""),
            "mc": a.get("_module_cn", ""),
            "cu": a.get("_country", ""),
            "to": a.get("_topic", ""),
            "su": summary,
            "hf": has_ft,
            "lk": a.get("link", "") or a.get("canonical_url", ""),
            "fi": str(i) if has_ft else "",
            "sk": a.get("signal_keywords", [])
        })

    # Escape </script> to prevent premature tag closure in HTML embedding
    def safe_json(obj):
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</script>", "<\\/script>")
    articles_json = safe_json(articles_compact)
    fulltexts_json = safe_json(fulltexts)
    modules_json = safe_json(module_list)
    top_sources = sorted(source_stats.items(), key=lambda x: x[1], reverse=True)[:30]
    sources_json = json.dumps(top_sources, ensure_ascii=False, separators=(",", ":"))

    # 6. 仪表盘HTML段落
    # 态势灯
    sit_html = f'''
    <div class="dash-section" id="sec-situation">
      <h2 class="sec-title">态势灯</h2>
      <div class="situation-grid">
        <div class="sit-light" style="--light-color:{sit_color}">
          <div class="light-dot" style="background:{sit_color};box-shadow:0 0 20px {sit_color}"></div>
          <div class="light-label">{sit_level}</div>
          <div class="light-desc">{sit_desc}</div>
        </div>
        <div class="sit-stats">
          <div class="sit-row"><span class="sit-k">总文章</span><span class="sit-v">{total_articles}</span></div>
          <div class="sit-row"><span class="sit-k">高优先</span><span class="sit-v" style="color:var(--high)">{high_count}</span></div>
          <div class="sit-row"><span class="sit-k">信号触发</span><span class="sit-v" style="color:var(--signal)">{sig_count}</span></div>
          <div class="sit-row"><span class="sit-k">数据时效</span><span class="sit-v freshness-{freshness}">{freshness_text}</span></div>
        </div>
      </div>
    </div>'''

    # 信号雷达
    if radar_data:
        radar_rows = ""
        for r in radar_data:
            radar_rows += f'''<div class="radar-row">
  <span class="radar-kw">{esc(r["kw"])}</span>
  <div class="radar-bar-wrap"><div class="radar-bar" style="width:{r["pct"]}%;background:{r["color"]}"></div><div class="radar-baseline" style="left:{r["base_pct"]}%"></div></div>
  <span class="radar-cnt" style="color:{r["color"]}">{r["cnt"]}</span><span class="radar-base">基线{r["base"]}</span>
</div>'''
        radar_html = f'''<div class="dash-section" id="sec-radar"><h2 class="sec-title">信号雷达</h2><div class="radar-chart">{radar_rows}</div></div>'''
    else:
        radar_html = '''<div class="dash-section" id="sec-radar"><h2 class="sec-title">信号雷达</h2><div class="radar-empty">今日无异常信号</div></div>'''

    # 必读Top10
    top10_rows = ""
    for i, a in enumerate(top10, 1):
        p = a.get("priority", 0)
        pc = priority_class(p)
        top10_rows += f'''<div class="mustread-item">
  <span class="mustread-rank">{i}</span>
  <span class="mustread-badge {pc}">{priority_label(p)} {p:.1f}</span>
  <span class="mustread-date">{_fmt_pubdate(a)}</span>
  <span class="mustread-title">{esc(a.get("title",""))}</span>
  <span class="mustread-source">{esc(a.get("source",""))}</span>
</div>'''
    top10_html = f'''<div class="dash-section" id="sec-mustread"><h2 class="sec-title">必读 Top10</h2><div class="mustread-list">{top10_rows}</div></div>'''

    # 四新速览
    newmod_cards = ""
    for nm in newmod_data:
        top3_rows = ""
        for a in nm["top3"]:
            p = a.get("priority", 0)
            top3_rows += f'''<div class="newmod-item"><span class="newmod-prio {priority_class(p)}">{p:.1f}</span><span class="newmod-date">{_fmt_pubdate(a)}</span><span class="newmod-title">{esc(a.get("title",""))[:70]}</span></div>'''
        newmod_cards += f'''<div class="newmod-card"><div class="newmod-header">{esc(nm["name"])} <span class="newmod-stats">{nm["total"]}篇 | 高{nm["high"]} | 信号{nm["sig"]}</span></div><div class="newmod-items">{top3_rows}</div></div>'''
    newmod_html = f'''<div class="dash-section" id="sec-newmod"><h2 class="sec-title">四新板块速览</h2><div class="newmod-grid">{newmod_cards}</div></div>'''

    # 热力图
    heat_cells = ""
    for h in heatmap:
        nb = " newmod-badge" if h["is_new"] else ""
        heat_cells += f'''<div class="heat-cell {h["heat"]}{nb}" onclick="switchToModule('{h["id"]}')" title="{esc(h["name"])}: {h["total"]}篇, 高{h["high"]}, 信号{h["sig"]}"><div class="heat-name">{esc(h["name"])}</div><div class="heat-count">{h["total"]}</div></div>'''
    heatmap_html = f'''<div class="dash-section" id="sec-heatmap"><h2 class="sec-title">18模块热力图 <span class="sec-hint">点击跳转详情</span></h2><div class="heatmap-grid">{heat_cells}</div>
<div class="heatmap-legend"><span class="legend-item"><span class="legend-dot heat-hot"></span>高热</span><span class="legend-item"><span class="legend-dot heat-warm"></span>温热</span><span class="legend-item"><span class="legend-dot heat-cool"></span>微温</span><span class="legend-item"><span class="legend-dot heat-cold"></span>冷</span><span class="legend-item"><span class="legend-dot newmod-dot"></span>新板块</span></div></div>'''

    # 中企风险
    if risk_arts:
        risk_rows = ""
        for a in risk_arts:
            p = a.get("priority", 0)
            pc = priority_class(p)
            risk_rows += f'''<div class="risk-item"><span class="risk-badge {pc}">{priority_label(p)} {p:.1f}</span><span class="risk-mod">{esc(MODULE_NAMES.get(a.get("_module",""),""))}</span><span class="risk-date">{_fmt_pubdate(a)}</span><span class="risk-title">{esc(a.get("title",""))[:80]}</span><span class="risk-source">{esc(a.get("source",""))}</span></div>'''
        risk_html = f'''<div class="dash-section" id="sec-chinarisk"><h2 class="sec-title">中企风险快讯</h2><div class="risk-list">{risk_rows}</div></div>'''
    else:
        risk_html = '''<div class="dash-section" id="sec-chinarisk"><h2 class="sec-title">中企风险快讯</h2><div class="risk-empty">今日无中企相关风险文章</div></div>'''

    # 7. 侧边栏数据
    mod_stats_rows = ""
    for m in module_list:
        mod_stats_rows += f'<tr><td>{esc(m["name"])}</td><td class="num">{m["total"]}</td><td class="num">{m["high"]}</td><td class="num">{m["med"]}</td><td style="font-size:0.75em;color:var(--dim)">{esc(m["signals"])}</td></tr>\n'
    src_rows = ""
    for i, (s, c) in enumerate(top_sources, 1):
        src_rows += f'<tr><td class="num">{i}</td><td>{esc(str(s)[:45])}</td><td class="num">{c}</td></tr>\n'
    mod_options = "".join(f'<option value="{esc(m["id"])}">{esc(m["name"])}</option>' for m in module_list)

    # 8. 组装完整HTML
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>全球视野日报 | {fetch_date}</title>
<style>
:root{{--bg:#0f1117;--surface:#1a1d27;--surface2:#242838;--card:#161b22;--border:#2e3348;--border2:#30363d;
--text:#e4e6f0;--text2:#9ca3c0;--text3:#6b7294;--dim:#8b949e;
--accent:#6c8cff;--accent2:#4f6ad4;--accent3:#58a6ff;
--high:#ff4d6a;--high-bg:rgba(255,77,106,.1);
--medium:#f5a623;--medium-bg:rgba(245,166,35,.1);--yellow:#d29922;
--low:#4a5078;--low-bg:rgba(74,80,120,.08);
--signal:#a78bfa;--signal-bg:rgba(167,139,250,.12);--purple:#bc8cff;
--tag-country:#34d399;--tag-country-bg:rgba(52,211,153,.1);
--tag-topic:#60a5fa;--tag-topic-bg:rgba(96,165,250,.1);
--green:#3fb950;--red:#f85149;--radius:8px}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--text);line-height:1.6}}
a{{color:var(--accent);text-decoration:none}}a:hover{{text-decoration:underline}}
.container{{max-width:1400px;margin:0 auto;padding:16px}}

/* ── Header ── */
.header{{padding:20px 0 12px;border-bottom:1px solid var(--border);margin-bottom:20px;display:flex;justify-content:space-between;align-items:flex-end}}
.header h1{{font-size:24px;font-weight:700;color:var(--accent3)}}
.header-date{{color:var(--text2);font-size:13px}}

/* ── Dashboard 6-block ── */
.dashboard{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}}
.dash-section{{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:16px}}
.dash-section:nth-child(1){{grid-column:1}}
.dash-section:nth-child(2){{grid-column:2}}
.dash-section:nth-child(n+3){{grid-column:1/-1}}
.sec-title{{font-size:15px;font-weight:700;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--border)}}
.sec-hint{{font-size:11px;font-weight:400;color:var(--text3);margin-left:8px}}

/* 态势灯 */
.situation-grid{{display:flex;align-items:center;gap:24px}}
.sit-light{{text-align:center;min-width:120px}}
.light-dot{{width:64px;height:64px;border-radius:50%;margin:0 auto 8px;animation:pulse 2s infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.7}}}}
.light-label{{font-size:20px;font-weight:800;margin-top:4px}}
.light-desc{{font-size:13px;color:var(--text2)}}
.sit-stats{{flex:1}}
.sit-row{{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.04)}}
.sit-k{{color:var(--text2);font-size:13px}}
.sit-v{{font-weight:600;font-size:15px}}
.freshness-fresh{{color:var(--tag-country)}}.freshness-aging{{color:var(--medium)}}.freshness-stale{{color:var(--high)}}

/* 信号雷达 */
.radar-empty{{color:var(--text3);font-size:14px;text-align:center;padding:20px}}
.radar-chart{{display:flex;flex-direction:column;gap:6px}}
.radar-row{{display:flex;align-items:center;gap:8px}}
.radar-kw{{min-width:80px;font-size:13px;font-weight:600}}
.radar-bar-wrap{{flex:1;height:14px;background:var(--surface2);border-radius:7px;position:relative}}
.radar-bar{{height:100%;border-radius:7px;transition:width .3s}}
.radar-baseline{{position:absolute;top:0;height:100%;width:2px;background:var(--text3);opacity:.5}}
.radar-cnt{{min-width:28px;font-size:14px;font-weight:700;text-align:right}}
.radar-base{{min-width:48px;font-size:11px;color:var(--text3)}}

/* 必读Top10 */
.mustread-list{{display:flex;flex-direction:column;gap:4px}}
.mustread-item{{display:flex;align-items:center;gap:8px;padding:6px 10px;border-radius:6px;background:var(--surface2)}}
.mustread-item:hover{{background:var(--border)}}
.mustread-rank{{min-width:20px;font-size:14px;font-weight:800;color:var(--accent3)}}
.mustread-badge{{font-size:11px;padding:1px 5px;border-radius:3px;font-weight:600;white-space:nowrap}}
.mustread-badge.high{{background:var(--high-bg);color:var(--high)}}
.mustread-badge.medium{{background:var(--medium-bg);color:var(--medium)}}
.mustread-badge.low{{background:var(--low-bg);color:var(--text3)}}
.mustread-title{{flex:1;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.mustread-source{{font-size:11px;color:var(--text3);white-space:nowrap}}
.mustread-date{{font-size:11px;color:var(--text3);white-space:nowrap}}

/* 四新板块速览 */
.newmod-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.newmod-card{{background:var(--surface2);border:1px solid var(--border);border-radius:var(--radius);padding:12px}}
.newmod-header{{font-size:14px;font-weight:700;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid var(--border)}}
.newmod-stats{{font-size:11px;font-weight:400;color:var(--text3);margin-left:6px}}
.newmod-empty{{color:var(--text3);font-size:13px;text-align:center;padding:12px}}
.newmod-items{{display:flex;flex-direction:column;gap:4px}}
.newmod-item{{display:flex;align-items:center;gap:6px;font-size:12px}}
.newmod-prio{{font-size:11px;font-weight:600;min-width:30px}}
.newmod-prio.high{{color:var(--high)}}.newmod-prio.medium{{color:var(--medium)}}.newmod-prio.low{{color:var(--text3)}}
.newmod-title{{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.newmod-date{{font-size:11px;color:var(--text3);white-space:nowrap}}

/* 热力图 */
.heatmap-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(90px,1fr));gap:8px}}
.heat-cell{{padding:10px 8px;border-radius:var(--radius);text-align:center;cursor:pointer;transition:transform .15s,box-shadow .15s;border:1px solid var(--border)}}
.heat-cell:hover{{transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,.3)}}
.heat-name{{font-size:12px;font-weight:600;margin-bottom:2px}}
.heat-count{{font-size:18px;font-weight:800}}
.heat-hot{{background:rgba(255,77,106,.15);border-color:rgba(255,77,106,.3);color:var(--high)}}
.heat-warm{{background:rgba(245,166,35,.1);border-color:rgba(245,166,35,.2);color:var(--medium)}}
.heat-cool{{background:rgba(96,165,250,.08);border-color:rgba(96,165,250,.15);color:var(--tag-topic)}}
.heat-cold{{background:var(--surface2);color:var(--text3)}}
.newmod-badge{{border-top:2px solid var(--signal)}}.newmod-dot{{background:var(--signal)}}
.heatmap-legend{{display:flex;gap:16px;margin-top:10px;font-size:11px;color:var(--text3)}}
.legend-item{{display:flex;align-items:center;gap:4px}}
.legend-dot{{display:inline-block;width:10px;height:10px;border-radius:3px}}
.legend-dot.heat-hot{{background:rgba(255,77,106,.5)}}.legend-dot.heat-warm{{background:rgba(245,166,35,.4)}}
.legend-dot.heat-cool{{background:rgba(96,165,250,.3)}}.legend-dot.heat-cold{{background:var(--surface2);border:1px solid var(--border)}}

/* 中企风险 */
.risk-empty{{color:var(--text3);font-size:14px;text-align:center;padding:20px}}
.risk-list{{display:flex;flex-direction:column;gap:4px}}
.risk-item{{display:flex;align-items:center;gap:8px;padding:6px 10px;border-radius:6px;background:var(--surface2);border-left:3px solid var(--high)}}
.risk-badge{{font-size:11px;padding:1px 5px;border-radius:3px;font-weight:600;white-space:nowrap}}
.risk-badge.high{{background:var(--high-bg);color:var(--high)}}.risk-badge.medium{{background:var(--medium-bg);color:var(--medium)}}
.risk-mod{{font-size:11px;color:var(--signal);white-space:nowrap}}
.risk-title{{flex:1;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.risk-source{{font-size:11px;color:var(--text3);white-space:nowrap}}
.risk-date{{font-size:11px;color:var(--text3);white-space:nowrap}}

/* ── Divider ── */
.divider{{border:none;border-top:1px solid var(--border);margin:24px 0}}
.detail-header{{font-size:18px;font-weight:700;margin-bottom:16px}}

/* ── Reader Layout ── */
.reader{{display:flex;gap:0}}
.sidebar{{width:300px;min-width:260px;border-right:1px solid var(--border);padding:14px;max-height:calc(100vh - 100px);overflow-y:auto;flex-shrink:0;position:sticky;top:80px}}
.sidebar h2{{font-size:0.95em;color:var(--accent3);margin:14px 0 6px;padding-bottom:4px;border-bottom:1px solid var(--border)}}
.sidebar h2:first-child{{margin-top:0}}
.sidebar table{{width:100%;border-collapse:collapse;font-size:0.78em}}
.sidebar th{{text-align:left;color:var(--dim);padding:3px 5px;border-bottom:1px solid var(--border)}}
.sidebar td{{padding:3px 5px;border-bottom:1px solid rgba(48,54,61,0.5)}}
.sidebar .num{{text-align:right;font-variant-numeric:tabular-nums}}
.content-area{{flex:1;padding:14px 16px;max-height:calc(100vh - 100px);overflow-y:auto}}

/* ── Toolbar ── */
.toolbar{{position:sticky;top:0;z-index:99;background:rgba(15,17,23,0.96);border-bottom:1px solid var(--border);padding:10px 20px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:14px}}
.toolbar select,.toolbar input{{background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:6px 10px;font-size:0.85em}}
.toolbar input{{flex:1;min-width:180px}}
.toolbar .count{{color:var(--dim);font-size:0.85em;margin-left:auto;white-space:nowrap}}

/* ── Cards ── */
.card{{background:var(--card);border:1px solid var(--border2);border-radius:8px;padding:12px 14px;margin-bottom:8px;transition:border-color 0.2s}}
.card:hover{{border-color:var(--accent3)}}
.card.high{{border-left:3px solid var(--high)}}
.card.medium{{border-left:3px solid var(--yellow)}}
.card.low{{border-left:3px solid var(--border2)}}
.card.hidden{{display:none!important}}
.card-header{{display:flex;gap:6px;align-items:center;margin-bottom:4px;flex-wrap:wrap}}
.badge{{display:inline-block;padding:1px 6px;border-radius:8px;font-size:0.7em;font-weight:700}}
.badge.high{{background:rgba(248,81,73,0.15);color:var(--high)}}
.badge.medium{{background:rgba(210,153,34,0.15);color:var(--yellow)}}
.badge.low{{background:rgba(139,148,158,0.1);color:var(--dim)}}
.card-time{{color:var(--dim);font-size:0.78em}}
.card-src{{color:var(--purple);font-size:0.78em}}
.card-country{{font-size:0.72em;padding:1px 4px;border-radius:3px;background:var(--tag-country-bg);color:var(--tag-country)}}
.card-topic{{font-size:0.72em;padding:1px 4px;border-radius:3px;background:var(--tag-topic-bg);color:var(--tag-topic)}}
.card-sig{{font-size:0.7em;padding:1px 4px;border-radius:3px;background:var(--signal-bg);color:var(--signal)}}
.card-mod{{color:var(--dim);font-size:0.72em;margin-left:auto}}
.card-title{{font-size:0.92em;font-weight:600;line-height:1.4;margin-bottom:3px}}
.card-summary{{color:var(--dim);font-size:0.82em;line-height:1.5}}
.full-text{{display:none;margin-top:6px;padding:10px 12px;background:rgba(88,166,255,0.05);border-radius:6px;font-size:0.82em;line-height:1.7;white-space:pre-wrap;max-height:400px;overflow-y:auto;color:var(--text)}}
.full-text.open{{display:block}}
.card-actions{{margin-top:5px;display:flex;gap:10px;align-items:center}}
.ft-btn{{background:none;border:1px solid var(--accent3);color:var(--accent3);border-radius:4px;padding:2px 8px;font-size:0.78em;cursor:pointer}}
.ft-btn:hover{{background:rgba(88,166,255,0.1)}}
.src-link{{font-size:0.78em}}
.load-more{{text-align:center;padding:16px;color:var(--dim);font-size:0.85em;cursor:pointer}}
.load-more:hover{{color:var(--accent3)}}

/* ── Responsive ── */
@media(max-width:900px){{.reader{{flex-direction:column}}.sidebar{{width:100%;max-height:260px;border-right:none;border-bottom:1px solid var(--border);position:static}}.content-area{{max-height:none}}}}
@media(max-width:640px){{.container{{padding:10px}}.header h1{{font-size:18px}}.dashboard{{grid-template-columns:1fr}}.newmod-grid{{grid-template-columns:1fr 1fr}}.heatmap-grid{{grid-template-columns:repeat(auto-fill,minmax(70px,1fr))}}}}
@media print{{body{{background:#fff;color:#222}}.toolbar,.sidebar{{display:none}}.reader{{display:block}}.content-area{{max-height:none;overflow:visible}}.dash-section{{border:1px solid #ddd}}.card{{border:1px solid #ddd;break-inside:avoid}}}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>全球视野日报</h1>
    <div class="header-date">{fetch_date} | 18模块 {total_articles}篇 | 高{high_count}+中{sum(1 for a in all_articles if 10<=a.get("priority",0)<15)} | 信号{sig_count}</div>
  </div>

  <div class="dashboard">
    {sit_html}
    {radar_html}
    {top10_html}
    {newmod_html}
    {heatmap_html}
    {risk_html}
  </div>

  <hr class="divider">
  <div class="detail-header">全文浏览</div>

  <div class="toolbar">
    <select id="filterLevel" onchange="applyFilter()">
      <option value="">全部优先级</option>
      <option value="high">高优先级</option>
      <option value="medium">中优先级</option>
      <option value="low">低优先级</option>
    </select>
    <select id="filterModule" onchange="applyFilter()">
      <option value="">全部模块</option>
      {mod_options}
    </select>
    <input type="text" id="searchBox" placeholder="搜索标题/摘要... source:信源名" oninput="applyFilter()">
    <select id="sortOrder" onchange="applySort()">
      <option value="pri_desc">优先级降序</option>
      <option value="time_desc">时间倒序</option>
      <option value="time_asc">时间正序</option>
    </select>
    <span class="count" id="countLabel"></span>
  </div>

  <div class="reader">
    <div class="sidebar">
      <h2>模块数据</h2>
      <table>
        <tr><th>模块</th><th class="num">总计</th><th class="num">高</th><th class="num">中</th><th>信号</th></tr>
        {mod_stats_rows}
      </table>
      <h2>信源 TOP 30</h2>
      <table>
        <tr><th class="num">#</th><th>信源</th><th class="num">篇数</th></tr>
        {src_rows}
      </table>
    </div>
    <div class="content-area" id="content"></div>
  </div>
</div>

<script type="application/json" id="articles-data">{articles_json}</script>
<script type="application/json" id="fulltexts-data">{fulltexts_json}</script>
<script>
var DATA=JSON.parse(document.getElementById("articles-data").textContent);
var FT=JSON.parse(document.getElementById("fulltexts-data").textContent);
var PAGE_SIZE=50;
var filtered=[];
var rendered=0;

filtered=DATA.slice();
applySort();

function esc(s){{return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}}

function renderCard(a){{
  var lc=a.l==="high"?"high":(a.l==="medium"?"medium":"low");
  var ll=a.l==="high"?"高":(a.l==="medium"?"中":"低");
  var ftBtn=a.hf?"<button class='ft-btn' data-fi='"+a.fi+"'>展开全文</button>":"";
  var lnk=a.lk?"<a href='"+esc(a.lk)+"' target='_blank' rel='noopener' class='src-link'>原文</a>":"";
  var sigTags="";
  if(a.sk&&a.sk.length>0){{
    for(var si=0;si<Math.min(a.sk.length,3);si++) sigTags+="<span class='card-sig'>⚡"+esc(a.sk[si])+"</span>";
  }}
  return "<div class='card "+lc+"' data-level='"+a.l+"' data-mod='"+esc(a.m)+"' data-pub='"+esc(a.p)+"' data-pr='"+a.pr+"' data-country='"+esc(a.cu)+"' data-topic='"+esc(a.to)+"'>"
    +"<div class='card-header'><span class='badge "+lc+"'>"+ll+" "+a.pr.toFixed(1)+"</span>"
    +"<span class='card-country'>"+esc(a.cu)+"</span>"
    +"<span class='card-topic'>"+esc(a.to)+"</span>"
    +"<span class='card-time'>"+esc(a.p)+"</span>"
    +"<span class='card-src'>"+esc((a.s||"").substring(0,35))+"</span>"
    +sigTags
    +"<span class='card-mod'>"+esc(a.m)+"</span></div>"
    +"<h3 class='card-title'>"+esc(a.t)+"</h3>"
    +"<p class='card-summary'>"+esc(a.su)+"</p>"
    +(a.hf?"<div class='full-text' id='ft-"+a.fi+"'></div>":"")
    +"<div class='card-actions'>"+ftBtn+lnk+"</div></div>";
}}

function renderBatch(){{
  var con=document.getElementById("content");
  var end=Math.min(rendered+PAGE_SIZE,filtered.length);
  var frag=document.createDocumentFragment();
  for(var i=rendered;i<end;i++){{
    var div=document.createElement("div");
    div.innerHTML=renderCard(filtered[i]);
    frag.appendChild(div.firstChild);
  }}
  var old=con.querySelector(".load-more");if(old)old.remove();
  con.appendChild(frag);
  rendered=end;
  if(rendered<filtered.length){{
    var lm=document.createElement("div");lm.className="load-more";
    lm.textContent="加载更多 ("+(filtered.length-rendered)+"篇剩余)";
    lm.onclick=renderBatch;con.appendChild(lm);
  }}
  updateCount();
}}

function toggleFT(btn){{
  var fi=btn.getAttribute("data-fi");
  var ftDiv=document.getElementById("ft-"+fi);
  if(!ftDiv)return;
  if(ftDiv.classList.contains("open")){{ftDiv.classList.remove("open");btn.textContent="展开全文";}}
  else{{if(!ftDiv.textContent&&FT[fi])ftDiv.textContent=FT[fi];ftDiv.classList.add("open");btn.textContent="收起全文";}}
}}

function applyFilter(){{
  var level=document.getElementById("filterLevel").value;
  var mod=document.getElementById("filterModule").value;
  var raw=document.getElementById("searchBox").value;
  var sourceFilter="";var textFilter="";
  var parts=raw.split(/\\s+/);
  for(var i=0;i<parts.length;i++){{
    if(parts[i].toLowerCase().indexOf("source:")===0)sourceFilter=parts[i].substring(7).toLowerCase();
    else textFilter+=(textFilter?" ":"")+parts[i];
  }}
  textFilter=textFilter.toLowerCase();
  filtered=DATA.filter(function(a){{
    if(level&&a.l!==level)return false;
    if(mod&&a.m!==mod)return false;
    if(sourceFilter&&(a.s||"").toLowerCase().indexOf(sourceFilter)===-1)return false;
    if(textFilter&&a.t.toLowerCase().indexOf(textFilter)===-1&&a.su.toLowerCase().indexOf(textFilter)===-1)return false;
    return true;
  }});
  applySort();
}}

function applySort(){{
  var order=document.getElementById("sortOrder").value;
  filtered.sort(function(a,b){{
    if(order==="pri_desc")return b.pr-a.pr;
    if(order==="time_desc")return(b.p||"").localeCompare(a.p||"");
    if(order==="time_asc")return(a.p||"").localeCompare(b.p||"");
    return 0;
  }});
  var con=document.getElementById("content");con.innerHTML="";rendered=0;renderBatch();
}}

function updateCount(){{document.getElementById("countLabel").textContent="显示 "+rendered+"/"+filtered.length+" 篇";}}

function switchToModule(mk){{
  document.getElementById("filterModule").value=mk;
  applyFilter();
  document.querySelector(".detail-header").scrollIntoView({{behavior:"smooth"}});
}}

// Infinite scroll
document.getElementById("content").addEventListener("scroll",function(){{
  if(this.scrollTop+this.clientHeight>=this.scrollHeight-200){{
    if(rendered<filtered.length)renderBatch();
  }}
}});

// Event delegation for full-text buttons
document.getElementById("content").addEventListener("click",function(e){{
  if(e.target.classList.contains("ft-btn"))toggleFT(e.target);
}});
</script>
</body>
</html>'''

    output_path.write_text(html, encoding="utf-8")
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"统一HTML v1.0 已生成: {output_path} ({size_mb:.1f} MB)")
    print(f"  仪表盘: 态势灯({sit_level})/信号雷达({sig_count})/必读Top10/四新速览/热力图/中企风险")
    print(f"  全文浏览器: {total_articles}篇 懒加载50/页, {len(fulltexts)}篇全文, source:语法")
    print(f"  侧边栏: 模块统计+信源TOP30")
    print(f"  数据嵌入: articles {len(articles_json)//1024}KB + fulltexts {len(fulltexts_json)//1024}KB")


if __name__ == "__main__":
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data")
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else data_dir.parent / "全球视野日报.html"
    generate(data_dir, output_path)
