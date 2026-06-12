#!/usr/bin/env python3
"""
send_report.py — 海外数据日报邮件投送
GitHub Actions 每日运行后，打包 data/*.json + _summary.txt，
通过 Resend SMTP 发送至指定邮箱。

环境变量：
  RESEND_API_KEY  — Resend API Key（也是SMTP密码）
  RECEIVE_EMAIL   — 接收邮箱地址
  SEND_FROM       — 发件人地址（默认 onboarding@resend.dev）
"""

import os
import smtplib
import json
import zipfile
import tempfile
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────────────────
SMTP_HOST = "smtp.resend.com"
SMTP_PORT = 465          # SSL
SMTP_USER = "resend"

SEND_FROM = os.environ.get("SEND_FROM", "onboarding@resend.dev")
RECEIVE_EMAIL = os.environ.get("RECEIVE_EMAIL", "")
API_KEY = os.environ.get("RESEND_API_KEY", "")

DATA_DIR = Path("data")
SUMMARY_FILE = DATA_DIR / "_summary.txt"
ZIP_NAME = "overseas-daily-report.zip"

# ── 生成 _summary.txt ────────────────────────────────────────────
def generate_summary() -> str:
    """读取 index.json 和 signal_summary.json，生成可读摘要。"""
    lines = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"=== 海外数据日报 === {now}\n")

    # 1. 总览（index.json）
    idx_path = DATA_DIR / "index.json"
    if idx_path.exists():
        with open(idx_path, encoding="utf-8") as f:
            idx = json.load(f)
        total = idx.get("global_total", "?")
        high = idx.get("global_high", "?")
        med = idx.get("global_medium", "?")
        new = idx.get("global_new", "?")
        ts = idx.get("updated", idx.get("fetch_date_utc", "?"))
        circuit = idx.get("circuit_breaker_count", 0)
        lines.append(f"总文章数: {total}  |  高优先: {high}  |  中优先: {med}  |  新增: {new}")
        lines.append(f"生成时间: {ts}")
        if circuit > 0:
            lines.append(f"⚠ 熔断源数: {circuit}")
        lines.append("")
        # 各模块概况
        modules = idx.get("modules", {})
        if modules:
            lines.append("模块概况:")
            for mod_name, mod_data in modules.items():
                if isinstance(mod_data, dict):
                    t = mod_data.get("total", 0)
                    h = mod_data.get("high", 0)
                    m = mod_data.get("medium", 0)
                    fail = mod_data.get("fail_feeds", 0)
                    info = f"  [{mod_name}] {t}篇, 高{h}/中{m}"
                    if fail > 0:
                        info += f", ⚠ {fail}源失败"
                    lines.append(info)
            lines.append("")
    else:
        lines.append("[!] index.json 不存在\n")

    # 2. 信号摘要（signal_summary.json）
    sig_path = DATA_DIR / "signal_summary.json"
    if sig_path.exists():
        with open(sig_path, encoding="utf-8") as f:
            sig = json.load(f)
        if isinstance(sig, dict):
            signals = sig.get("signals", [])
            triggered = [s for s in signals if isinstance(s, dict) and s.get("triggered")]
            if triggered:
                lines.append(f"信号告警 ({len(triggered)} 条触发):")
                for s in triggered[:10]:
                    kw = s.get("keyword", "?")
                    cnt = s.get("today_count", "?")
                    base = s.get("baseline", "?")
                    status = s.get("status", "?")
                    lines.append(f"  - {kw}: {cnt}次 (基线{base}, {status})")
                if len(triggered) > 10:
                    lines.append(f"  ... 及另外 {len(triggered)-10} 条")
            else:
                lines.append("信号: 无告警（全部在基线内）")
            lines.append("")
    else:
        lines.append("[!] signal_summary.json 不存在\n")

    # 3. 各模块文件大小
    lines.append("文件清单:")
    json_files = sorted(DATA_DIR.glob("*.json"))
    total_size = 0
    for jf in json_files:
        size_kb = jf.stat().st_size / 1024
        total_size += size_kb
        lines.append(f"  {jf.name:30s}  {size_kb:7.1f} KB")
    lines.append(f"  {'合计':30s}  {total_size:7.1f} KB")
    lines.append("")

    return "\n".join(lines)


# ── 打包 ZIP ─────────────────────────────────────────────────────
def create_zip(summary_text: str, zip_path: str) -> None:
    """将 data/*.json + _summary.txt 打包为 zip。"""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # 写入 _summary.txt
        zf.writestr("_summary.txt", summary_text)
        # 写入所有 JSON
        for jf in sorted(DATA_DIR.glob("*.json")):
            zf.write(jf, f"data/{jf.name}")
    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"[OK] ZIP 已创建: {zip_path} ({size_mb:.2f} MB)")


# ── 发送邮件 ─────────────────────────────────────────────────────
def send_email(zip_path: str, summary_text: str) -> None:
    """通过 Resend SMTP SSL 发送带附件的邮件。"""
    if not API_KEY:
        raise RuntimeError("RESEND_API_KEY 环境变量未设置")
    if not RECEIVE_EMAIL:
        raise RuntimeError("RECEIVE_EMAIL 环境变量未设置")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    subject = f"[海外数据日报] {today}"

    msg = MIMEMultipart()
    msg["From"] = SEND_FROM
    msg["To"] = RECEIVE_EMAIL
    msg["Subject"] = subject

    # 正文 = _summary.txt 内容
    body = summary_text
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # 附件 = ZIP
    with open(zip_path, "rb") as f:
        part = MIMEBase("application", "zip")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        "attachment",
        filename=f"overseas-daily-{today}.zip",
    )
    msg.attach(part)

    # SMTP SSL 发送
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(SMTP_USER, API_KEY)
        server.sendmail(SEND_FROM, [RECEIVE_EMAIL], msg.as_string())

    print(f"[OK] 邮件已发送: {SEND_FROM} → {RECEIVE_EMAIL}")


# ── 主流程 ───────────────────────────────────────────────────────
def main():
    print("=" * 50)
    print("海外数据日报 — 邮件投送")
    print("=" * 50)

    # 1. 生成摘要
    print("[1/3] 生成 _summary.txt ...")
    summary = generate_summary()
    # 同时落盘一份到 data/
    SUMMARY_FILE.write_text(summary, encoding="utf-8")
    print(f"  已写入 {SUMMARY_FILE}")
    print(summary)

    # 2. 打包 ZIP
    print("[2/3] 打包 ZIP ...")
    zip_path = os.path.join(tempfile.gettempdir(), ZIP_NAME)
    create_zip(summary, zip_path)

    # 3. 发送邮件
    print("[3/3] 发送邮件 ...")
    send_email(zip_path, summary)

    print("\n✓ 全部完成")


if __name__ == "__main__":
    main()
