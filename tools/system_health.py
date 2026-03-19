#!/usr/bin/env python3
"""
system_health.py — AEO 多客戶系統健康儀表板

Usage: python3 system_health.py [--check-live] [--json]
"""

import os, sys, json, sqlite3, argparse, subprocess
from datetime import datetime, date

DB_PATH = os.path.expanduser("~/.openclaw/memory/client_sites.db")


def load_all_sites():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    rows = db.execute("""
        SELECT slug, business_name, industry, template_variant, status, plan_tier,
               chatbot_enabled, tracker_enabled, local_path, site_url,
               last_audit_score, last_audit_grade, deployed_at
        FROM client_sites ORDER BY id
    """).fetchall()
    db.close()
    return [dict(r) for r in rows]


def check_local_files(site: dict) -> dict:
    """Check if AEO files exist locally."""
    path = site.get("local_path") or ""
    path = os.path.expanduser(path)
    results = {}
    for f in ["index.html", "llms.txt", "robots.txt", "sitemap.xml", "BingSiteAuth.xml", "vercel.json"]:
        fp = os.path.join(path, f)
        results[f] = os.path.exists(fp) if path and os.path.isdir(path) else False
    return results


def count_articles(site: dict) -> int:
    path = site.get("local_path") or ""
    path = os.path.expanduser(path)
    articles_dir = os.path.join(path, "articles")
    if os.path.isdir(articles_dir):
        return len([f for f in os.listdir(articles_dir) if f.endswith(".html")])
    return 0


def check_launchagent(slug: str) -> bool:
    agents_dir = os.path.expanduser("~/Library/LaunchAgents")
    for f in os.listdir(agents_dir):
        if slug in f and f.endswith(".plist"):
            return True
    return False


def main():
    parser = argparse.ArgumentParser(description="AEO System Health Dashboard")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--check-live", action="store_true", help="Check live URLs (slower)")
    args = parser.parse_args()

    sites = load_all_sites()
    results = []

    for s in sites:
        files = check_local_files(s)
        articles = count_articles(s)
        has_agent = check_launchagent(s["slug"])

        aeo_score = sum([
            files.get("index.html", False),
            files.get("llms.txt", False),
            files.get("robots.txt", False),
            files.get("sitemap.xml", False),
            files.get("BingSiteAuth.xml", False),
            s.get("chatbot_enabled", False),
            s.get("tracker_enabled", True),
            articles > 0,
        ])
        aeo_pct = int(aeo_score / 8 * 100)

        results.append({
            "slug": s["slug"],
            "name": s["business_name"],
            "industry": s["industry"],
            "template": s.get("template_variant", "?"),
            "status": s["status"],
            "tier": s["plan_tier"],
            "files": files,
            "articles": articles,
            "chatbot": bool(s.get("chatbot_enabled")),
            "tracker": bool(s.get("tracker_enabled", True)),
            "launchagent": has_agent,
            "aeo_score": aeo_pct,
            "deployed_at": s.get("deployed_at", ""),
        })

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    # Pretty print
    print(f"\n{'═' * 100}")
    print(f" 🏥 AEO Multi-Client System Health — {date.today()}")
    print(f"{'═' * 100}")
    print(f"\n{'Slug':<25} {'Template':<10} {'Status':<8} {'AEO':<6} {'Files':<8} {'Articles':<10} {'Bot':<5} {'Agent':<6}")
    print("─" * 100)

    for r in results:
        tpl = {"conversion": "A轉化", "storytelling": "B敘事", "performance": "C效能"}.get(r["template"], r["template"][:6])
        files_ok = sum(r["files"].values())
        total_files = len(r["files"])
        aeo_bar = f"{r['aeo_score']}%"
        bot = "✅" if r["chatbot"] else "—"
        agent = "✅" if r["launchagent"] else "—"
        status_icon = {"active": "🟢", "generating": "🟡", "pending": "⚪", "suspended": "🔴"}.get(r["status"], "❓")

        print(f"{r['slug']:<25} {tpl:<10} {status_icon}{r['status']:<7} {aeo_bar:<6} {files_ok}/{total_files:<5} {r['articles']:<10} {bot:<5} {agent}")

    # Summary
    active = sum(1 for r in results if r["status"] == "active")
    with_bot = sum(1 for r in results if r["chatbot"])
    with_agent = sum(1 for r in results if r["launchagent"])
    total_articles = sum(r["articles"] for r in results)
    avg_aeo = sum(r["aeo_score"] for r in results) // len(results) if results else 0

    print(f"\n{'─' * 100}")
    print(f" 📊 Total: {len(results)} sites | {active} active | {with_bot} chatbot | {with_agent} auto-gen | {total_articles} articles | Avg AEO: {avg_aeo}%")
    print(f"{'═' * 100}\n")


if __name__ == "__main__":
    main()
