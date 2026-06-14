#!/usr/bin/env python3
"""
signal_dashboard.py v1.0 — 信号看板 + 选题候选看板 生成器
从本地JSON数据中提取国家×行业信号，生成统一HTML看板

产出：
  1. signals.json  — 结构化信号数据
  2. topics.json   — 选题候选数据(12字段)
  3. dashboard.html — 统一看板(信号+选题+反馈)

用法：
  python signal_dashboard.py [data_dir] [--date YYYY-MM-DD]
"""
import json
import sys
import re
import html as html_lib
from pathlib import Path
from datetime import datetime
from collections import defaultdict

try:
    import yaml
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml", "-q"])
    import yaml


# ── 加载配置 ──────────────────────────────────────────────────────
def load_config(config_path=None):
    if config_path is None:
        script_dir = Path(__file__).resolve().parent
        for c in [
            script_dir.parent / "config" / "classification.yaml",
            script_dir / "config" / "classification.yaml",
            script_dir / "classification.yaml",
        ]:
            if c.exists():
                config_path = c
                break
    if config_path is None or not Path(config_path).exists():
        raise FileNotFoundError("classification.yaml 未找到")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


CFG = load_config()
MODULE_NAMES = CFG["modules"]["names"]
SKIP_FILES = set(CFG["modules"]["skip_files"])
COUNTRY_CFG = CFG.get("country", {})
TOPIC_CFG = CFG.get("topic", {})
COUNTRY_CATEGORY_MAP = COUNTRY_CFG.get("category_map", {})
COUNTRY_MODULE_DEFAULTS = COUNTRY_CFG.get("module_defaults", {})
COUNTRY_KEYWORD_MAP = COUNTRY_CFG.get("keyword_map", {})
TOPIC_CATEGORY_MAP = TOPIC_CFG.get("category_map", {})
TOPIC_MODULE_DEFAULTS = TOPIC_CFG.get("module_defaults", {})
TOPIC_KEYWORD_MAP = TOPIC_CFG.get("keyword_map", {})


# ── 国家提取 ──────────────────────────────────────────────────────
def extract_country(article: dict, module_key: str) -> list:
    """从category、title中提取国家标签。"""
    countries = []
    # 1. category直接映射
    cat = article.get("category", "")
    if cat in COUNTRY_CATEGORY_MAP:
        countries.append(COUNTRY_CATEGORY_MAP[cat])
    # 2. title关键词
    title = article.get("title", "")
    for country, keywords in COUNTRY_KEYWORD_MAP.items():
        if country in countries:
            continue
        for kw in keywords:
            if kw in title:
                countries.append(country)
                break
    # 3. 模块默认
    if not countries and module_key in COUNTRY_MODULE_DEFAULTS:
        countries.append(COUNTRY_MODULE_DEFAULTS[module_key])
    return countries or ["全球"]


# ── 主题提取 ──────────────────────────────────────────────────────
def extract_topics(article: dict, module_key: str) -> list:
    """从category、title中提取主题标签。"""
    topics = []
    # 1. category直接映射
    cat = article.get("category", "")
    if cat in TOPIC_CATEGORY_MAP:
        topics.append(TOPIC_CATEGORY_MAP[cat])
    # 2. title关键词（小写匹配）
    title_lower = article.get("title", "").lower()
    for topic, keywords in TOPIC_KEYWORD_MAP.items():
        if topic in topics:
            continue
        for kw in keywords:
            kw_lower = kw.lower()
            # 关键词以空格结尾的做精确匹配，否则做包含匹配
            if kw.endswith(" ") and kw_lower.rstrip() in title_lower.split():
                topics.append(topic)
                break
            elif not kw.endswith(" ") and kw_lower in title_lower:
                topics.append(topic)
                break
    # 3. 模块默认
    if not topics and module_key in TOPIC_MODULE_DEFAULTS:
        topics.append(TOPIC_MODULE_DEFAULTS[module_key])
    return topics or ["综合"]


# ── 信号强度计算 ──────────────────────────────────────────────────
def calc_signal_strength(article: dict) -> float:
    """信号强度 = priority权重 + full_text加成 + source_tier加成"""
    base = article.get("priority", 0)
    has_text = 1.0 if article.get("full_text") else 0.0
    source_detail = article.get("source_detail", {})
    source_name = source_detail.get("name", "") if isinstance(source_detail, dict) else ""
    # 权威源加成
    authority_sources = {
        "Reuters": 2.0, "Bloomberg": 2.0, "Financial Times": 2.0,
        "The Economist": 2.0, "BBC": 1.5, "The Guardian": 1.5,
        "The New York Times": 1.5, "The Wall Street Journal": 2.0,
        "Nikkei Asia": 1.5, "South China Morning Post": 1.5,
    }
    auth_bonus = 0.0
    for auth_src, bonus in authority_sources.items():
        if auth_src.lower() in source_name.lower():
            auth_bonus = bonus
            break
    return round(base + has_text * 2.0 + auth_bonus, 1)


# ── 信号提取主流程 ────────────────────────────────────────────────
def extract_signals(data_dir: Path, target_date: str) -> list:
    """从所有模块JSON中提取信号。"""
    signals = []
    signal_id = 0

    for jf in sorted(data_dir.glob("*.json")):
        if jf.name in SKIP_FILES:
            continue
        module_key = jf.stem
        with open(jf, encoding="utf-8") as f:
            data = json.load(f)
        articles = data.get("articles", [])
        for a in articles:
            signal_id += 1
            countries = extract_country(a, module_key)
            topics = extract_topics(a, module_key)
            strength = calc_signal_strength(a)

            # 清理summary中的HTML实体
            summary = a.get("summary", "").strip()
            summary = html_lib.unescape(summary)
            summary = re.sub(r'<[^>]+>', '', summary)
            if len(summary) > 300:
                summary = summary[:300] + "..."

            # 清理full_text（如有）
            full_text = a.get("full_text", "")
            if full_text:
                full_text = html_lib.unescape(full_text)
                full_text = re.sub(r'<[^>]+>', '', full_text)
                if len(full_text) > 500:
                    full_text = full_text[:500] + "..."

            signals.append({
                "id": f"S{signal_id:04d}",
                "title": a.get("title", ""),
                "summary": summary,
                "full_text_preview": full_text[:200] if full_text else "",
                "countries": countries,
                "topics": topics,
                "module": module_key,
                "module_cn": MODULE_NAMES.get(module_key, module_key),
                "source": a.get("source", ""),
                "source_detail": a.get("source_detail", {}),
                "published": a.get("published", ""),
                "published_beijing": a.get("published_beijing", ""),
                "link": a.get("link", ""),
                "canonical_url": a.get("canonical_url", ""),
                "priority": a.get("priority", 0),
                "signal_strength": strength,
                "has_full_text": bool(a.get("full_text")),
                "_incremental": a.get("_incremental", ""),
                # 预留企业级匹配扩展位
                "enterprise_id": None,
                "enterprise_name": None,
            })

    # 按signal_strength降序排列
    signals.sort(key=lambda x: x["signal_strength"], reverse=True)
    return signals


# ── 选题候选生成 ──────────────────────────────────────────────────
def generate_topic_candidates(signals: list, target_date: str) -> list:
    """从信号中生成选题候选（12字段）。"""
    candidates = []
    for s in signals:
        # 只取signal_strength >= 8的作为选题候选
        if s["signal_strength"] < 8:
            continue

        # 预计字数：有full_text的1500-2500，没有的800-1500
        est_words = "1500-2500" if s["has_full_text"] else "800-1500"

        # 推荐理由：国家×主题组合
        country_str = "/".join(s["countries"])
        topic_str = "/".join(s["topics"])
        reason = f"{country_str}·{topic_str}方向信号，强度{s['signal_strength']}"

        # 紧急度：基于信号强度
        urgency = "高" if s["signal_strength"] >= 15 else "中" if s["signal_strength"] >= 10 else "低"

        # 信号强度分级
        strength_label = "强" if s["signal_strength"] >= 15 else "中" if s["signal_strength"] >= 10 else "弱"

        # 截止日期：新闻类3天内
        from datetime import timedelta
        deadline = (datetime.strptime(target_date, "%Y-%m-%d") + timedelta(days=2)).strftime("%Y-%m-%d")

        # 备选角度
        alt_angles = []
        if len(s["countries"]) > 0 and s["countries"][0] != "全球":
            alt_angles.append(f"从{s['countries'][0]}本土视角切入")
        if len(s["topics"]) > 0:
            alt_angles.append(f"聚焦{s['topics'][0]}产业链影响")
        if s["has_full_text"]:
            alt_angles.append("深度解读模式")

        candidates.append({
            "id": s["id"],
            "标题": s["title"][:60],
            "摘要": s["summary"],
            "来源": s["source"],
            "链接": s.get("canonical_url") or s["link"],
            "板块": s["module_cn"],
            "紧急度": urgency,
            "预计字数": est_words,
            "推荐理由": reason,
            "信号强度": strength_label,
            "截止日期": deadline,
            "关联国家行业": f"{country_str}×{topic_str}",
            "备选角度": alt_angles,
        })

    return candidates[:30]  # 最多30个候选


# ── HTML看板生成 ──────────────────────────────────────────────────
def generate_dashboard_html(signals: list, topics: list, target_date: str, output_path: Path):
    """生成统一HTML看板（信号+选题+反馈）。"""

    # 统计
    country_stats = defaultdict(int)
    topic_stats = defaultdict(int)
    country_topic_matrix = defaultdict(lambda: defaultdict(int))
    for s in signals:
        for c in s["countries"]:
            country_stats[c] += 1
        for t in s["topics"]:
            topic_stats[t] += 1
        for c in s["countries"]:
            for t in s["topics"]:
                country_topic_matrix[c][t] += 1

    top_countries = sorted(country_stats.items(), key=lambda x: -x[1])[:15]
    top_topics = sorted(topic_stats.items(), key=lambda x: -x[1])[:15]

    # 信号表格行
    signal_rows = []
    for s in signals[:100]:  # 最多显示100条
        country_badges = "".join(f'<span class="badge country">{html_lib.escape(c)}</span>' for c in s["countries"])
        topic_badges = "".join(f'<span class="badge topic">{html_lib.escape(t)}</span>' for t in s["topics"])
        strength_class = "strong" if s["signal_strength"] >= 15 else "medium" if s["signal_strength"] >= 10 else "weak"
        new_badge = '<span class="badge new">NEW</span>' if s.get("_incremental") == "new" else ""
        ft_icon = "&#128196;" if s["has_full_text"] else ""

        signal_rows.append(f"""
        <tr data-sid="{s['id']}">
          <td class="col-id">{s['id']}</td>
          <td class="col-title" title="{html_lib.escape(s['title'])}">
            <a href="{html_lib.escape(s.get('canonical_url') or s['link'])}" target="_blank" rel="noopener">{html_lib.escape(s['title'][:80])}</a>
            {new_badge} {ft_icon}
          </td>
          <td class="col-badges">{country_badges}{topic_badges}</td>
          <td class="col-source">{html_lib.escape(s.get('source_detail',{}).get('name','') if isinstance(s.get('source_detail'),dict) else s.get('source',''))}</td>
          <td class="col-strength"><span class="strength {strength_class}">{s['signal_strength']}</span></td>
          <td class="col-date">{s.get('published_beijing','')[:16] or s.get('published','')[:16]}</td>
          <td class="col-actions">
            <button class="btn-feedback useful" onclick="feedback('{s['id']}','useful')">有用</button>
            <button class="btn-feedback noise" onclick="feedback('{s['id']}','noise')">噪声</button>
          </td>
        </tr>""")

    # 选题候选行
    topic_rows = []
    for t in topics:
        topic_rows.append(f"""
        <tr data-tid="{t['id']}">
          <td>{t['id']}</td>
          <td class="col-title" title="{html_lib.escape(t['标题'])}">{html_lib.escape(t['标题'])}</td>
          <td>{html_lib.escape(t['板块'])}</td>
          <td><span class="badge urgency-{t['紧急度'][0]}">{t['紧急度']}</span></td>
          <td>{html_lib.escape(t['预计字数'])}</td>
          <td class="col-reason">{html_lib.escape(t['推荐理由'])}</td>
          <td>{html_lib.escape(t['关联国家行业'])}</td>
          <td>
            <button class="btn-select" onclick="selectTopic('{t['id']}')">选用</button>
          </td>
        </tr>""")

    # 热力图
    matrix_headers = "".join(f"<th>{html_lib.escape(t)}</th>" for t, _ in top_topics)
    matrix_rows = []
    for c, _ in top_countries:
        cells = "".join(f"<td>{country_topic_matrix[c].get(t, 0) or ''}</td>" for t, _ in top_topics)
        if any(country_topic_matrix[c].get(t, 0) for t, _ in top_topics):
            matrix_rows.append(f"<tr><th>{html_lib.escape(c)}</th>{cells}</tr>")

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>信号看板 | {target_date}</title>
<style>
  :root {{ --bg: #0d1117; --surface: #161b22; --border: #30363d; --text: #e6edf3; --text2: #8b949e;
    --accent: #58a6ff; --green: #3fb950; --red: #f85149; --yellow: #d29922; --orange: #db6d28; }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    background: var(--bg); color: var(--text); line-height:1.5; padding: 20px; }}
  h1 {{ font-size: 1.6em; margin-bottom: 4px; }}
  h2 {{ font-size: 1.2em; color: var(--accent); margin: 24px 0 12px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }}
  .meta {{ color: var(--text2); margin-bottom: 16px; }}
  .stats {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }}
  .stat-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 12px 18px; min-width: 120px; }}
  .stat-card .num {{ font-size: 1.8em; font-weight: 700; color: var(--accent); }}
  .stat-card .label {{ font-size: 0.85em; color: var(--text2); }}

  table {{ width: 100%; border-collapse: collapse; font-size: 0.85em; margin-bottom: 24px; }}
  th {{ background: var(--surface); color: var(--text2); text-align: left; padding: 8px 10px;
    border-bottom: 2px solid var(--border); position: sticky; top: 0; white-space: nowrap; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }}
  tr:hover {{ background: rgba(88,166,255,0.06); }}
  .col-id {{ width: 60px; color: var(--text2); font-family: monospace; }}
  .col-title {{ max-width: 400px; }}
  .col-title a {{ color: var(--text); text-decoration: none; }}
  .col-title a:hover {{ color: var(--accent); text-decoration: underline; }}
  .col-badges {{ white-space: nowrap; }}
  .col-source {{ color: var(--text2); white-space: nowrap; }}
  .col-strength {{ text-align: center; }}
  .col-date {{ color: var(--text2); white-space: nowrap; font-size: 0.9em; }}
  .col-actions {{ white-space: nowrap; }}
  .col-reason {{ max-width: 200px; font-size: 0.85em; color: var(--text2); }}

  .badge {{ display: inline-block; padding: 1px 7px; border-radius: 10px; font-size: 0.8em; margin: 1px 2px; }}
  .badge.country {{ background: rgba(88,166,255,0.15); color: var(--accent); }}
  .badge.topic {{ background: rgba(210,153,34,0.15); color: var(--yellow); }}
  .badge.new {{ background: rgba(63,185,80,0.2); color: var(--green); }}
  .badge.urgency-高 {{ background: rgba(248,81,73,0.2); color: var(--red); }}
  .badge.urgency-中 {{ background: rgba(210,153,34,0.2); color: var(--yellow); }}
  .badge.urgency-低 {{ background: rgba(139,148,158,0.15); color: var(--text2); }}

  .strength {{ display: inline-block; min-width: 36px; text-align: center; padding: 2px 6px; border-radius: 4px; font-weight: 600; font-size: 0.9em; }}
  .strength.strong {{ background: rgba(248,81,73,0.2); color: var(--red); }}
  .strength.medium {{ background: rgba(210,153,34,0.2); color: var(--yellow); }}
  .strength.weak {{ background: rgba(139,148,158,0.1); color: var(--text2); }}

  .btn-feedback, .btn-select {{ border: 1px solid var(--border); border-radius: 4px; padding: 2px 10px;
    font-size: 0.85em; cursor: pointer; background: transparent; color: var(--text2); transition: all 0.15s; }}
  .btn-feedback:hover {{ border-color: var(--accent); color: var(--accent); }}
  .btn-feedback.active-useful {{ background: rgba(63,185,80,0.2); border-color: var(--green); color: var(--green); }}
  .btn-feedback.active-noise {{ background: rgba(248,81,73,0.2); border-color: var(--red); color: var(--red); }}
  .btn-select {{ background: rgba(88,166,255,0.1); color: var(--accent); border-color: var(--accent); }}
  .btn-select:hover {{ background: rgba(88,166,255,0.25); }}

  .matrix {{ border-collapse: collapse; font-size: 0.85em; }}
  .matrix th, .matrix td {{ padding: 4px 8px; text-align: center; border: 1px solid var(--border); }}
  .matrix th {{ background: var(--surface); color: var(--text2); }}
  .matrix td {{ color: var(--text); font-weight: 500; }}
  .matrix td:has(>3) {{ background: rgba(88,166,255,0.15); }}

  .filter-bar {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; align-items: center; }}
  .filter-bar select, .filter-bar input {{ background: var(--surface); color: var(--text); border: 1px solid var(--border);
    border-radius: 4px; padding: 4px 8px; font-size: 0.9em; }}
  .filter-bar label {{ color: var(--text2); font-size: 0.85em; }}

  .section {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 20px; }}
  .table-wrap {{ max-height: 600px; overflow: auto; }}

  @media print {{ body {{ background: white; color: black; }} .btn-feedback, .btn-select {{ display: none; }} }}
</style>
</head>
<body>

<h1>信号看板</h1>
<p class="meta">{target_date} | {len(signals)} 条信号 | {len(topics)} 个选题候选</p>

<div class="stats">
  <div class="stat-card"><div class="num">{len(signals)}</div><div class="label">总信号</div></div>
  <div class="stat-card"><div class="num">{sum(1 for s in signals if s['signal_strength']>=15)}</div><div class="label">强信号</div></div>
  <div class="stat-card"><div class="num">{len(topics)}</div><div class="label">选题候选</div></div>
  <div class="stat-card"><div class="num">{sum(1 for s in signals if s['has_full_text'])}</div><div class="label">有全文</div></div>
  <div class="stat-card"><div class="num">{sum(1 for s in signals if s.get('_incremental')=='new')}</div><div class="label">新增</div></div>
</div>

<h2>国家×行业热力图</h2>
<div class="section">
<table class="matrix">
  <tr><th>国家</th>{matrix_headers}</tr>
  {"".join(matrix_rows)}
</table>
</div>

<h2>信号列表</h2>
<div class="section">
<div class="filter-bar">
  <label>国家：</label><select id="f-country"><option value="">全部</option>{"".join(f'<option value="{html_lib.escape(c)}">{html_lib.escape(c)} ({n})</option>' for c,n in top_countries)}</select>
  <label>行业：</label><select id="f-topic"><option value="">全部</option>{"".join(f'<option value="{html_lib.escape(t)}">{html_lib.escape(t)} ({n})</option>' for t,n in top_topics)}</select>
  <label>强度：</label><select id="f-strength"><option value="">全部</option><option value="strong">强(≥15)</option><option value="medium">中(10-15)</option><option value="weak">弱(&lt;10)</option></select>
</div>
<div class="table-wrap">
<table id="signal-table">
  <tr><th>ID</th><th>标题</th><th>国家/行业</th><th>来源</th><th>强度</th><th>时间</th><th>反馈</th></tr>
  {"".join(signal_rows)}
</table>
</div>
</div>

<h2>选题候选</h2>
<div class="section">
<div class="table-wrap">
<table id="topic-table">
  <tr><th>ID</th><th>标题</th><th>板块</th><th>紧急度</th><th>字数</th><th>推荐理由</th><th>国家×行业</th><th>操作</th></tr>
  {"".join(topic_rows)}
</table>
</div>
</div>

<script>
// 筛选功能
function applyFilters() {{
  const fc = document.getElementById('f-country').value;
  const ft = document.getElementById('f-topic').value;
  const fs = document.getElementById('f-strength').value;
  const rows = document.querySelectorAll('#signal-table tr[data-sid]');
  rows.forEach(r => {{
    let show = true;
    // 国家筛选通过badge文本
    if (fc) {{
      const badges = r.querySelectorAll('.badge.country');
      show = show && Array.from(badges).some(b => b.textContent === fc);
    }}
    if (ft) {{
      const badges = r.querySelectorAll('.badge.topic');
      show = show && Array.from(badges).some(b => b.textContent === ft);
    }}
    if (fs) {{
      const s = r.querySelector('.strength');
      show = show && s && s.classList.contains(fs);
    }}
    r.style.display = show ? '' : 'none';
  }});
}}
document.getElementById('f-country').addEventListener('change', applyFilters);
document.getElementById('f-topic').addEventListener('change', applyFilters);
document.getElementById('f-strength').addEventListener('change', applyFilters);

// 反馈按钮
const feedbackData = {{}};
function feedback(sid, type) {{
  const row = document.querySelector(`tr[data-sid="${{sid}}"]`);
  const btns = row.querySelectorAll('.btn-feedback');
  btns.forEach(b => b.classList.remove('active-useful','active-noise'));
  if (type === 'useful') {{
    row.querySelector('.btn-feedback.useful').classList.add('active-useful');
    feedbackData[sid] = 'useful';
  }} else {{
    row.querySelector('.btn-feedback.noise').classList.add('active-noise');
    feedbackData[sid] = 'noise';
  }}
  // 保存到本地
  localStorage.setItem('signal_feedback_' + new Date().toISOString().slice(0,10), JSON.stringify(feedbackData));
}}

// 选用按钮
function selectTopic(tid) {{
  const row = document.querySelector(`tr[data-tid="${{tid}}"]`);
  const btn = row.querySelector('.btn-select');
  btn.textContent = '已选';
  btn.style.background = 'rgba(63,185,80,0.2)';
  btn.style.color = '#3fb950';
  btn.style.borderColor = '#3fb950';
  // TODO: 后续接入选题包模板填充
  alert('选题 ' + tid + ' 已选用，后续将自动填充选题包模板。');
}}

// 加载已有反馈
const saved = localStorage.getItem('signal_feedback_' + '{target_date}');
if (saved) {{
  try {{
    const data = JSON.parse(saved);
    Object.entries(data).forEach(([sid, type]) => {{
      const row = document.querySelector(`tr[data-sid="${{sid}}"]`);
      if (row) {{
        if (type === 'useful') row.querySelector('.btn-feedback.useful')?.classList.add('active-useful');
        else row.querySelector('.btn-feedback.noise')?.classList.add('active-noise');
        feedbackData[sid] = type;
      }}
    }});
  }} catch(e) {{}}
}}
</script>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    return len(signals)


# ── 主流程 ────────────────────────────────────────────────────────
def main():
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data")
    target_date = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--date" and i < len(sys.argv) - 1:
            target_date = sys.argv[i + 1]

    if not target_date:
        idx_path = data_dir / "index.json"
        if idx_path.exists():
            with open(idx_path, encoding="utf-8") as f:
                idx = json.load(f)
            target_date = idx.get("fetch_date_utc", datetime.now().strftime("%Y-%m-%d"))
        if not target_date:
            target_date = datetime.now().strftime("%Y-%m-%d")

    print(f"信号看板生成 | {target_date}")
    print(f"数据目录: {data_dir}")

    # 1. 提取信号
    print("[1/4] 提取信号 ...")
    signals = extract_signals(data_dir, target_date)
    print(f"      {len(signals)} 条信号")
    strong = sum(1 for s in signals if s["signal_strength"] >= 15)
    print(f"      强信号(≥15): {strong}  中(10-15): {sum(1 for s in signals if 10<=s['signal_strength']<15)}  弱(<10): {sum(1 for s in signals if s['signal_strength']<10)}")

    # 2. 生成选题候选
    print("[2/4] 生成选题候选 ...")
    topics = generate_topic_candidates(signals, target_date)
    print(f"      {len(topics)} 个选题候选")

    # 3. 保存JSON
    print("[3/4] 保存数据 ...")
    signals_path = data_dir / "signals.json"
    topics_path = data_dir / "topics.json"
    with open(signals_path, "w", encoding="utf-8") as f:
        json.dump({"date": target_date, "total": len(signals), "signals": signals}, f, ensure_ascii=False, indent=2)
    with open(topics_path, "w", encoding="utf-8") as f:
        json.dump({"date": target_date, "total": len(topics), "topics": topics}, f, ensure_ascii=False, indent=2)
    print(f"      signals.json ({len(signals)} 条)")
    print(f"      topics.json ({len(topics)} 条)")

    # 4. 生成HTML看板
    print("[4/4] 生成HTML看板 ...")
    dashboard_path = data_dir / f"信号看板_{target_date}.html"
    count = generate_dashboard_html(signals, topics, target_date, dashboard_path)
    print(f"      {dashboard_path.name} ({count} 条信号)")

    # 复制一份到工作目录
    work_copy = Path.home() / ".temp" / dashboard_path.name
    work_copy.parent.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy2(dashboard_path, work_copy)
    print(f"      工作副本: {work_copy}")

    print(f"\n完成: {len(signals)} 信号 + {len(topics)} 选题候选 → {dashboard_path}")


if __name__ == "__main__":
    main()
