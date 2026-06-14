#!/usr/bin/env python3
"""
download_daily.py v2.0 — 通过gh CLI自动下载GitHub Actions artifact
v1.0: 基础版，下载→归档→同步→清理
v2.0: 适配v6.0增量采集架构
  - 新增seen_index artifact下载
  - 用增量增量数据+seen_index构建本地完整库
  - 保留7天→30天历史归档

前置条件：
  - gh CLI 已安装且已认证 (gh auth login)
  - 网络可访问 github.com API

用法：
  python download_daily.py                    # 下载最新成功运行的artifact
  python download_daily.py --run-id 12345     # 下载指定run
  python download_daily.py --dry-run          # 只显示不下载

流程：
  1. gh api 获取最新成功run的artifact信息
  2. gh run download 下载json-outputs + seen-index artifacts
  3. 从index.json读取日期
  4. 复制到 data/YYYY-MM-DD/ （日期子目录）
  5. 同步到 data/ flat目录（含seen_index.json）
  6. 清理30天前的子目录
  7. 生成 _summary.txt
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

REPO = "WOHO99/overseas-data-hub"
DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
ARTIFACT_PREFIX = "json-outputs-"
SEEN_INDEX_PREFIX = "seen-index-"
RETENTION_DAYS = 30
SKIP_DIRS = {"archive"}


def run_gh(args: list, check=True) -> subprocess.CompletedProcess:
    """执行gh CLI命令。"""
    cmd = ["gh"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if check and result.returncode != 0:
        print(f"[!] gh命令失败: {' '.join(cmd)}")
        print(f"    stderr: {result.stderr.strip()}")
        raise RuntimeError(f"gh CLI错误 (exit {result.returncode})")
    return result


def get_latest_successful_run() -> dict:
    """获取最新成功完成的workflow run。"""
    result = run_gh([
        "run", "list",
        "--repo", REPO,
        "--status", "completed",
        "--limit", "5",
        "--json", "databaseId,conclusion,createdAt,displayTitle"
    ])
    runs = json.loads(result.stdout)
    for r in runs:
        if r.get("conclusion") == "success":
            return r
    raise RuntimeError("最近5次运行中没有成功的run")


def get_artifact_names(run_id: str) -> dict:
    """获取指定run的artifact名称（json-outputs + seen-index）"""
    result = run_gh([
        "api", f"repos/{REPO}/actions/runs/{run_id}/artifacts"
    ])
    data = json.loads(result.stdout)
    names = {}
    for art in data.get("artifacts", []):
        name = art.get("name", "")
        if art.get("expired", True):
            continue
        if name.startswith(ARTIFACT_PREFIX):
            names["json-outputs"] = name
        elif name.startswith(SEEN_INDEX_PREFIX):
            names["seen-index"] = name
    if "json-outputs" not in names:
        raise RuntimeError(f"Run {run_id} 没有找到 {ARTIFACT_PREFIX}* artifact")
    return names


def download_artifact(run_id: str, artifact_name: str, dest_dir: Path) -> int:
    """下载指定artifact到dest_dir。"""
    dest_dir.mkdir(parents=True, exist_ok=True)
    run_gh([
        "run", "download", run_id,
        "--repo", REPO,
        "--name", artifact_name,
        "--dir", str(dest_dir)
    ])
    count = len(list(dest_dir.glob("*.json")))
    return count


def detect_date_from_data(data_dir: Path) -> str:
    """从index.json读取fetch_date_utc。"""
    idx_path = data_dir / "index.json"
    if idx_path.exists():
        with open(idx_path, encoding="utf-8") as f:
            idx = json.load(f)
        fetch_date = idx.get("fetch_date_utc", "")
        if fetch_date:
            return fetch_date[:10]
    return datetime.now().strftime("%Y-%m-%d")


def generate_summary(data_dir: Path) -> str:
    """生成_summary.txt（与send_report.py格式一致）。"""
    lines = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"=== 海外数据日报 === {now}\n")

    idx_path = data_dir / "index.json"
    if idx_path.exists():
        with open(idx_path, encoding="utf-8") as f:
            idx = json.load(f)
        total = idx.get("global_total", "?")
        high = idx.get("global_high", "?")
        med = idx.get("global_medium", "?")
        new = idx.get("global_new", "?")
        ts = idx.get("updated", idx.get("fetch_date_utc", "?"))
        lines.append(f"总文章数: {total}  |  高优先: {high}  |  中优先: {med}  |  新增: {new}")
        lines.append(f"生成时间: {ts}")
        lines.append("")
    else:
        lines.append("[!] index.json 不存在\n")

    sig_path = data_dir / "signal_summary.json"
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
            else:
                lines.append("信号: 无告警")
            lines.append("")

    lines.append("文件清单:")
    total_size = 0
    for jf in sorted(data_dir.glob("*.json")):
        size_kb = jf.stat().st_size / 1024
        total_size += size_kb
        lines.append(f"  {jf.name:30s}  {size_kb:7.1f} KB")
    lines.append(f"  {'合计':30s}  {total_size:7.1f} KB")
    return "\n".join(lines)


def copy_to_date_dir(source_dir: Path, date_str: str) -> int:
    """将source_dir的文件复制到 data/YYYY-MM-DD/。"""
    date_dir = DATA_ROOT / date_str
    date_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in source_dir.iterdir():
        if f.is_file():
            shutil.copy2(f, date_dir / f.name)
            count += 1
    # 生成_summary.txt
    summary = generate_summary(date_dir)
    (date_dir / "_summary.txt").write_text(summary, encoding="utf-8")
    return count


def sync_to_flat(date_str: str) -> int:
    """将 data/YYYY-MM-DD/ 同步到 data/ flat目录。"""
    date_dir = DATA_ROOT / date_str
    if not date_dir.exists():
        return 0
    count = 0
    for f in date_dir.iterdir():
        if f.is_file() and (f.suffix == ".json" or f.name == "_summary.txt"):
            shutil.copy2(f, DATA_ROOT / f.name)
            count += 1
    return count


def cleanup_old_dirs() -> list:
    """清理超过RETENTION_DAYS天的日期子目录。"""
    cutoff = (datetime.now() - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
    removed = []
    for d in DATA_ROOT.iterdir():
        if not d.is_dir() or d.name in SKIP_DIRS:
            continue
        if len(d.name) == 10 and d.name[4] == "-" and d.name[7] == "-":
            if d.name < cutoff:
                shutil.rmtree(d, ignore_errors=True)
                removed.append(d.name)
    return removed


def main():
    dry_run = "--dry-run" in sys.argv
    run_id_override = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--run-id" and i < len(sys.argv) - 1:
            run_id_override = sys.argv[i + 1]

    print("=" * 50)
    print("海外数据日报 — gh CLI 自动下载")
    print("=" * 50)

    # 1. 获取run信息
    if run_id_override:
        run_id = run_id_override
        print(f"[1/6] 使用指定run: {run_id}")
    else:
        run_info = get_latest_successful_run()
        run_id = str(run_info["databaseId"])
        created = run_info.get("createdAt", "?")
        print(f"[1/6] 最新成功run: {run_id} ({created})")

    # 2. 获取artifact名称
    artifact_names = get_artifact_names(run_id)
    print(f"[2/7] Artifacts: {artifact_names}")

    if dry_run:
        print("\n[dry-run] 停止，不执行下载")
        return

    # 3. 下载json-outputs artifact
    temp_dir = DATA_ROOT.parent / ".temp" / "gh_download"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    print(f"[3/7] 下载JSON数据 ...")
    count = download_artifact(run_id, artifact_names["json-outputs"], temp_dir)
    print(f"      下载 {count} 个JSON文件")

    # 4. 下载seen-index artifact（如有）
    seen_index_path = DATA_ROOT / "seen_index.json"
    if "seen-index" in artifact_names:
        print(f"[4/7] 下载seen_index ...")
        si_temp = DATA_ROOT.parent / ".temp" / "gh_seen_index"
        if si_temp.exists():
            shutil.rmtree(si_temp)
        si_temp.mkdir(parents=True, exist_ok=True)
        run_gh([
            "run", "download", run_id,
            "--repo", REPO,
            "--name", artifact_names["seen-index"],
            "--dir", str(si_temp)
        ])
        # 移动seen_index.json到正式位置
        si_file = si_temp / "seen_index.json"
        if si_file.exists():
            shutil.copy2(si_file, seen_index_path)
            print(f"      seen_index.json 已更新")
        shutil.rmtree(si_temp, ignore_errors=True)
    else:
        print(f"[4/7] 无seen-index artifact（跳过）")

    # 5. 检测日期并复制到日期子目录
    date_str = detect_date_from_data(temp_dir)
    print(f"[5/7] 日期: {date_str}，归档到 data/{date_str}/ ...")
    archive_count = copy_to_date_dir(temp_dir, date_str)
    print(f"      归档 {archive_count} 个文件 + _summary.txt")

    # 6. 同步到flat目录
    print("[6/7] 同步到 data/ flat目录 ...")
    sync_count = sync_to_flat(date_str)
    print(f"      同步 {sync_count} 个文件")

    # 7. 清理过期目录
    print(f"[7/7] 清理 >{RETENTION_DAYS}天的目录 ...")
    removed = cleanup_old_dirs()
    if removed:
        print(f"      清理 {len(removed)} 个: {removed}")
    else:
        print("      无过期目录")

    # 清理临时下载目录
    shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"\n完成: data/{date_str}/ + data/ flat 已更新")


if __name__ == "__main__":
    main()
