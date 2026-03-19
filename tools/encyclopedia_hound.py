#!/usr/bin/env python3
"""
encyclopedia_hound.py — 百科 24/7 獵犬監控
每小時自動檢查 5 百科進度、worker 健康、錯誤模式，Telegram 告警。

Usage:
  python3 encyclopedia_hound.py --status     # 即時狀態表格
  python3 encyclopedia_hound.py --check      # 健康檢查 + 自動修復 + 告警
  python3 encyclopedia_hound.py --report     # 發送 Telegram 日報
  python3 encyclopedia_hound.py --test-alert # 發送測試告警
"""

import os, sys, json, sqlite3, time, subprocess, argparse, urllib.request, urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

# ── Config ──
ENCY_DIR = os.path.expanduser("~/.openclaw/encyclopedia")
DB_DIR = os.path.join(ENCY_DIR, "db")
LOG_DIR = os.path.join(ENCY_DIR, "logs")
HEARTBEAT_FILE = os.path.join(LOG_DIR, "heartbeat")
STATE_FILE = os.path.join(LOG_DIR, "worker-state.json")
HOUND_STATE = os.path.join(LOG_DIR, "hound-state.json")

TG_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TG_CHAT_ID = "YOUR_CHAT_ID"

WORKER_LABEL = "ai.openclaw.encyclopedia-worker"
HEARTBEAT_TIMEOUT = 900  # 15 minutes
ALERT_COOLDOWN = 14400   # 4 hours

REGIONS = {
    "japan":    {"db": "japan.db",    "name": "日本百科",  "site": "japan-encyclopedia"},
    "hongkong": {"db": "hongkong.db", "name": "香港百科",  "site": "hongkong-encyclopedia"},
    "taiwan":   {"db": "taiwan.db",   "name": "台灣百科",  "site": "taiwan-encyclopedia"},
    "macau":    {"db": "macau.db",    "name": "澳門百科",  "site": "macau-encyclopedia"},
}

SITE_DIRS = {
    "japan-encyclopedia": os.path.expanduser("~/Documents/japan-encyclopedia"),
    "hongkong-encyclopedia": os.path.expanduser("~/Documents/hongkong-encyclopedia"),
    "taiwan-encyclopedia": os.path.expanduser("~/Documents/taiwan-encyclopedia"),
    "macau-encyclopedia": os.path.expanduser("~/Documents/macau-encyclopedia"),
    "world-encyclopedia": os.path.expanduser("~/Documents/world-encyclopedia"),
}


# ── Hound State (cooldown tracking) ──
def _load_hound_state() -> dict:
    if os.path.exists(HOUND_STATE):
        try:
            with open(HOUND_STATE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"alerts": {}, "last_check": None, "last_report": None}


def _save_hound_state(state: dict):
    with open(HOUND_STATE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _can_alert(state: dict, alert_type: str) -> bool:
    """Check cooldown: same alert type within 4 hours = suppress."""
    last = state.get("alerts", {}).get(alert_type)
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
        return (datetime.now() - last_dt).total_seconds() > ALERT_COOLDOWN
    except Exception:
        return True


def _mark_alerted(state: dict, alert_type: str):
    if "alerts" not in state:
        state["alerts"] = {}
    state["alerts"][alert_type] = datetime.now().isoformat()


# ── Telegram ──
def send_telegram(text: str, parse_mode: str = "HTML"):
    """Send message via Kira bot."""
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": "true",
    }).encode()
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"  ⚠️ TG send failed: {e}")
        return False


# ── Data Collection ──
def get_heartbeat_age() -> float:
    """Returns seconds since last heartbeat."""
    if not os.path.exists(HEARTBEAT_FILE):
        return 99999
    try:
        with open(HEARTBEAT_FILE) as f:
            ts = f.read().strip()
        last = datetime.fromisoformat(ts)
        return (datetime.now() - last).total_seconds()
    except Exception:
        return 99999


def get_worker_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def get_db_stats(region: str) -> dict:
    """Get article stats from SQLite DB."""
    db_file = os.path.join(DB_DIR, REGIONS[region]["db"])
    if not os.path.exists(db_file):
        return {"total": 0, "published": 0, "today": 0}
    try:
        con = sqlite3.connect(db_file, timeout=10)
        total = con.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        published = con.execute("SELECT COUNT(*) FROM articles WHERE status='published'").fetchone()[0]
        today = datetime.now().strftime("%Y-%m-%d")
        today_count = con.execute(
            "SELECT COUNT(*) FROM articles WHERE status='published' AND date(created_at)=?",
            (today,)
        ).fetchone()[0]
        con.close()
        return {"total": total, "published": published, "today": today_count}
    except Exception as e:
        return {"total": 0, "published": 0, "today": 0, "error": str(e)}


def get_site_article_count(site_name: str) -> int:
    """Count HTML files in articles/ directory."""
    site_dir = SITE_DIRS.get(site_name, "")
    articles_dir = os.path.join(site_dir, "articles") if site_dir else ""
    if not os.path.isdir(articles_dir):
        # Try root level HTML files
        if os.path.isdir(site_dir):
            return len([f for f in os.listdir(site_dir) if f.endswith(".html") and f != "index.html"])
        return 0
    return len([f for f in os.listdir(articles_dir) if f.endswith(".html")])


def is_worker_running() -> bool:
    """Check if encyclopedia-worker LaunchAgent is running."""
    try:
        result = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{WORKER_LABEL}"],
            capture_output=True, text=True, timeout=5
        )
        return "state = running" in result.stdout.lower() or "pid =" in result.stdout.lower()
    except Exception:
        return False


def get_recent_errors(n: int = 5) -> list:
    """Get last N error patterns from worker.log."""
    log_file = os.path.join(LOG_DIR, "worker.log")
    if not os.path.exists(log_file):
        return []
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        errors = [l.strip() for l in lines if "FAILED" in l or "失敗" in l or "error" in l.lower()]
        return errors[-n:]
    except Exception:
        return []


# ── Health Checks ──
def run_health_checks() -> list:
    """Run all health checks. Returns list of {type, severity, message}."""
    issues = []

    # 1. Heartbeat check
    hb_age = get_heartbeat_age()
    if hb_age > HEARTBEAT_TIMEOUT:
        minutes = int(hb_age // 60)
        issues.append({
            "type": "heartbeat_dead",
            "severity": "critical",
            "message": f"Worker 心跳停止 {minutes} 分鐘（門檻 15 分鐘）",
            "auto_fix": "restart_worker"
        })

    # 2. Worker process check
    if not is_worker_running():
        issues.append({
            "type": "worker_dead",
            "severity": "critical",
            "message": "Worker 進程未運行",
            "auto_fix": "restart_worker"
        })

    # 3. Worker state check
    ws = get_worker_state()
    if ws:
        # Consecutive failure check
        total_fail = ws.get("total_failures", 0)
        total_articles = ws.get("total_articles", 0)
        if total_articles > 0:
            fail_rate = total_fail / (total_fail + total_articles)
            if fail_rate > 0.8:
                issues.append({
                    "type": "high_failure_rate",
                    "severity": "warning",
                    "message": f"失敗率 {fail_rate:.0%}（{total_fail} 失敗 / {total_articles} 成功）",
                })

        # Dedup streak check
        dedup = ws.get("dedup_streaks", {})
        for key, streak in dedup.items():
            if streak >= 5:
                region = key.replace("_dedup_streak", "")
                issues.append({
                    "type": f"dedup_streak_{region}",
                    "severity": "warning",
                    "message": f"{region} 重複文章連續 {streak} 次",
                })

        # Today output check (if past 10:00 and 0 articles)
        now = datetime.now()
        if now.hour >= 10 and ws.get("today_articles", 0) == 0:
            issues.append({
                "type": "zero_today",
                "severity": "warning",
                "message": f"今日 0 篇文章（已過 {now.hour}:00）",
            })

    # 4. DB accessibility
    for region, info in REGIONS.items():
        db_path = os.path.join(DB_DIR, info["db"])
        if not os.path.exists(db_path):
            issues.append({
                "type": f"db_missing_{region}",
                "severity": "error",
                "message": f"{info['name']} DB 不存在: {info['db']}",
            })

    return issues


def auto_fix(issue: dict) -> bool:
    """Attempt automatic fix. Returns True if fixed."""
    fix = issue.get("auto_fix")
    if fix == "restart_worker":
        print(f"  🔧 Auto-fix: restarting {WORKER_LABEL}...")
        try:
            uid = os.getuid()
            subprocess.run(["launchctl", "bootout", f"gui/{uid}/{WORKER_LABEL}"],
                          capture_output=True, timeout=10)
            time.sleep(3)
            plist = os.path.expanduser(f"~/Library/LaunchAgents/{WORKER_LABEL}.plist")
            if os.path.exists(plist):
                subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", plist],
                              capture_output=True, timeout=10)
                time.sleep(5)
                if is_worker_running():
                    print(f"  ✅ Worker restarted successfully")
                    return True
            print(f"  ❌ Worker restart failed")
        except Exception as e:
            print(f"  ❌ Auto-fix error: {e}")
    return False


# ── Output Formatters ──
def print_status():
    """Print comprehensive status table."""
    ws = get_worker_state()
    hb_age = get_heartbeat_age()
    running = is_worker_running()

    print(f"\n{'═' * 80}")
    print(f" 🐺 百科獵犬 — Encyclopedia Hound Status")
    print(f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═' * 80}")

    # Worker health
    hb_str = f"{int(hb_age)}s ago" if hb_age < 9999 else "N/A"
    hb_icon = "🟢" if hb_age < HEARTBEAT_TIMEOUT else "🔴"
    run_icon = "🟢" if running else "🔴"
    print(f"\n Worker: {run_icon} {'Running' if running else 'STOPPED'}  |  "
          f"Heartbeat: {hb_icon} {hb_str}  |  "
          f"Rounds: {ws.get('total_rounds', '?')}  |  "
          f"Today: +{ws.get('today_articles', '?')} 篇")

    # Per-region table
    print(f"\n{'Region':<12} {'DB Total':<10} {'Published':<10} {'Today':<8} {'Site HTML':<10} {'Rounds':<8}")
    print("─" * 80)

    total_pub = 0
    total_today = 0
    for region, info in REGIONS.items():
        stats = get_db_stats(region)
        site_count = get_site_article_count(info["site"])
        r_state = ws.get("regions", {}).get(region, {})
        rounds = r_state.get("rounds", 0)

        total_pub += stats["published"]
        total_today += stats["today"]

        print(f"  {info['name']:<10} {stats['total']:<10} {stats['published']:<10} "
              f"+{stats['today']:<7} {site_count:<10} {rounds}")

    # World encyclopedia (no DB, static)
    world_count = get_site_article_count("world-encyclopedia")
    print(f"  {'世界百科':<10} {'—':<10} {'—':<10} {'—':<7} {world_count:<10} {'—'}")

    print(f"\n  {'TOTAL':<10} {'—':<10} {total_pub:<10} +{total_today:<7}")

    # Error summary
    errors = get_recent_errors(3)
    if errors:
        print(f"\n  ⚠️ Recent errors:")
        for e in errors:
            print(f"    {e[:100]}")

    print(f"\n{'═' * 80}\n")


def format_telegram_report() -> str:
    """Format daily Telegram report."""
    ws = get_worker_state()
    hb_age = get_heartbeat_age()
    running = is_worker_running()

    lines = ["🐺 <b>百科獵犬日報</b>", f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]

    # Worker status
    lines.append(f"⚙️ Worker: {'🟢 Running' if running else '🔴 STOPPED'}")
    lines.append(f"💓 Heartbeat: {int(hb_age)}s ago")
    lines.append(f"🔄 Total rounds: {ws.get('total_rounds', '?')}")
    lines.append(f"📝 Today: +{ws.get('today_articles', '?')} 篇")
    lines.append("")

    # Per region
    total_pub = 0
    for region, info in REGIONS.items():
        stats = get_db_stats(region)
        total_pub += stats["published"]
        lines.append(f"{'🇯🇵' if region=='japan' else '🇭🇰' if region=='hongkong' else '🇹🇼' if region=='taiwan' else '🇲🇴'} "
                     f"{info['name']}: {stats['published']} 篇 (+{stats['today']})")

    world_count = get_site_article_count("world-encyclopedia")
    lines.append(f"🌍 世界百科: {world_count} 篇")
    lines.append(f"\n📊 <b>Total: {total_pub} published</b>")

    # Issues
    issues = run_health_checks()
    if issues:
        lines.append(f"\n⚠️ <b>Issues ({len(issues)}):</b>")
        for iss in issues:
            sev = {"critical": "🔴", "error": "🟠", "warning": "🟡"}.get(iss["severity"], "⚪")
            lines.append(f"  {sev} {iss['message']}")
    else:
        lines.append(f"\n✅ <b>All checks passed</b>")

    return "\n".join(lines)


def format_alert(issues: list) -> str:
    """Format alert message for critical issues."""
    lines = ["🚨 <b>百科獵犬告警</b>", ""]
    for iss in issues:
        sev = {"critical": "🔴 CRITICAL", "error": "🟠 ERROR", "warning": "🟡 WARNING"}.get(iss["severity"], "")
        lines.append(f"{sev}: {iss['message']}")
    return "\n".join(lines)


# ── Main Commands ──
def cmd_status():
    print_status()


def cmd_check():
    """Run health checks, auto-fix, alert."""
    print("🐺 Running health checks...")
    state = _load_hound_state()
    issues = run_health_checks()

    if not issues:
        print("  ✅ All checks passed")
        state["last_check"] = datetime.now().isoformat()
        _save_hound_state(state)
        return

    critical = [i for i in issues if i["severity"] == "critical"]
    warnings = [i for i in issues if i["severity"] != "critical"]

    for iss in issues:
        sev = {"critical": "🔴", "error": "🟠", "warning": "🟡"}.get(iss["severity"], "")
        print(f"  {sev} {iss['message']}")

    # Auto-fix critical issues
    for iss in critical:
        if iss.get("auto_fix"):
            fixed = auto_fix(iss)
            if fixed:
                iss["message"] += " → ✅ Auto-fixed"

    # Telegram alert (with cooldown)
    alert_issues = [i for i in issues if i["severity"] in ("critical", "error")]
    if alert_issues:
        # Group by type for cooldown
        unsuppressed = []
        for iss in alert_issues:
            if _can_alert(state, iss["type"]):
                unsuppressed.append(iss)
                _mark_alerted(state, iss["type"])

        if unsuppressed:
            msg = format_alert(unsuppressed)
            sent = send_telegram(msg)
            print(f"  {'📨' if sent else '❌'} Telegram alert sent ({len(unsuppressed)} issues)")
        else:
            print(f"  🔇 Alerts suppressed (cooldown)")

    state["last_check"] = datetime.now().isoformat()
    _save_hound_state(state)


def cmd_report():
    """Send Telegram daily report."""
    msg = format_telegram_report()
    print(msg.replace("<b>", "").replace("</b>", ""))
    sent = send_telegram(msg)
    print(f"\n{'📨 Sent' if sent else '❌ Failed'}")

    state = _load_hound_state()
    state["last_report"] = datetime.now().isoformat()
    _save_hound_state(state)


def cmd_test_alert():
    """Send test alert."""
    msg = "🐺 <b>百科獵犬測試</b>\n\n✅ 告警系統正常運作\n" + format_telegram_report()
    sent = send_telegram(msg)
    print(f"{'📨 Test alert sent' if sent else '❌ Failed'}")


def main():
    parser = argparse.ArgumentParser(description="🐺 百科獵犬監控")
    parser.add_argument("--status", action="store_true", help="即時狀態表格")
    parser.add_argument("--check", action="store_true", help="健康檢查 + 自動修復 + 告警")
    parser.add_argument("--report", action="store_true", help="發送 Telegram 日報")
    parser.add_argument("--test-alert", action="store_true", help="發送測試告警")
    args = parser.parse_args()

    if args.status:
        cmd_status()
    elif args.check:
        cmd_check()
    elif args.report:
        cmd_report()
    elif args.test_alert:
        cmd_test_alert()
    else:
        # Default: check (for LaunchAgent cron)
        cmd_check()


if __name__ == "__main__":
    main()
