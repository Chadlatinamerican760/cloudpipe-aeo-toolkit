#!/usr/bin/env python3
"""
site_quality_audit.py — 90 分制 AEO 品質評分器

12 項指標，每站逐項檢查，輸出分數 + 缺失清單。

Usage:
  python3 site_quality_audit.py --slug inari-global-foods
  python3 site_quality_audit.py --all
  python3 site_quality_audit.py --all --json
"""

import os, sys, re, json, glob, argparse

DOCS_DIR = os.path.expanduser("~/Documents")
INDEXNOW_KEY = "YOUR_INDEXNOW_KEY"
INJECT_MARKER = "CLOUDPIPE-INJECT"
TRACKER_DOMAIN = "YOUR_TRACKER.workers.dev"
CHAT_DOMAIN = "YOUR_CHAT_WORKER.workers.dev"


def find_all_sites() -> list:
    """Find all brand + demo site directories."""
    sites = []
    # Brand sites (from client_sites.db known slugs)
    brand_slugs = [
        "inari-global-foods", "sea-urchin-delivery", "after-school-coffee",
        "mind-coffee", "yamanakada", "bni-macau", "test-cafe-demo",
    ]
    for slug in brand_slugs:
        path = os.path.join(DOCS_DIR, slug)
        if os.path.isdir(path) and os.path.exists(os.path.join(path, "index.html")):
            sites.append({"slug": slug, "path": path, "type": "brand"})

    # Demo sites
    for d in sorted(glob.glob(os.path.join(DOCS_DIR, "aeo-demo-*"))):
        if os.path.isdir(d) and os.path.exists(os.path.join(d, "index.html")):
            slug = os.path.basename(d)
            sites.append({"slug": slug, "path": d, "type": "demo"})

    return sites


def _file_exists(path: str, filename: str) -> bool:
    return os.path.exists(os.path.join(path, filename))


def _file_contains(path: str, filename: str, pattern: str) -> bool:
    fp = os.path.join(path, filename)
    if not os.path.exists(fp):
        return False
    try:
        with open(fp, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return bool(re.search(pattern, content, re.IGNORECASE))
    except Exception:
        return False


def _file_size(path: str, filename: str) -> int:
    fp = os.path.join(path, filename)
    return os.path.getsize(fp) if os.path.exists(fp) else 0


def _count_articles(path: str) -> int:
    articles_dir = os.path.join(path, "articles")
    if not os.path.isdir(articles_dir):
        return 0
    return len([f for f in os.listdir(articles_dir) if f.endswith(".html")])


def audit_site(site: dict) -> dict:
    """Run 12-indicator audit on a site. Returns dict with scores and details."""
    path = site["path"]
    slug = site["slug"]
    results = []
    total = 0
    max_total = 0

    def check(name: str, weight: int, passed: bool, detail: str = ""):
        nonlocal total, max_total
        max_total += weight
        if passed:
            total += weight
        results.append({
            "name": name, "weight": weight, "passed": passed,
            "score": weight if passed else 0, "detail": detail
        })

    # 1. index.html exists + renderable (10)
    idx_size = _file_size(path, "index.html")
    check("index.html", 10, idx_size > 1000, f"{idx_size:,} bytes")

    # 2. llms.txt (10)
    check("llms.txt", 10, _file_exists(path, "llms.txt"), "AI crawler discovery")

    # 3. robots.txt with AI bot allow (10)
    has_robots = _file_exists(path, "robots.txt")
    has_ai_allow = _file_contains(path, "robots.txt", r"GPTBot|ClaudeBot|PerplexityBot")
    check("robots.txt (AI-friendly)", 10, has_robots and has_ai_allow,
          "allows AI bots" if has_ai_allow else "missing AI bot rules")

    # 4. sitemap.xml (10)
    check("sitemap.xml", 10, _file_exists(path, "sitemap.xml"), "structured discovery")

    # 5. Schema.org JSON-LD (10)
    has_schema = _file_contains(path, "index.html", r'application/ld\+json')
    schema_count = 0
    if has_schema:
        with open(os.path.join(path, "index.html"), "r", encoding="utf-8", errors="replace") as f:
            schema_count = len(re.findall(r'application/ld\+json', f.read()))
    check("Schema.org JSON-LD", 10, schema_count >= 1, f"{schema_count} blocks")

    # 6. FAQPage Schema (10)
    has_faq = _file_contains(path, "index.html", r'FAQPage')
    check("FAQPage Schema", 10, has_faq, "structured Q&A for AI")

    # 7. OG Meta (5)
    has_og = _file_contains(path, "index.html", r'og:title.*og:description|og:description.*og:title')
    # More lenient check
    if not has_og:
        has_og = (_file_contains(path, "index.html", r'og:title') and
                  _file_contains(path, "index.html", r'og:description'))
    check("Open Graph Meta", 5, has_og, "social sharing")

    # 8. BingSiteAuth.xml (5)
    check("BingSiteAuth.xml", 5, _file_exists(path, "BingSiteAuth.xml"), "Bing verification")

    # 9. Chatbot widget (10)
    has_chatbot = (_file_contains(path, "index.html", rf'{CHAT_DOMAIN}') or
                   _file_contains(path, "index.html", r'chat-widget|chatbot|sendChatMsg|sendMsg|cbSend'))
    check("Chatbot Widget", 10, has_chatbot, "interactive AI assistant")

    # 10. Tracker pixel (5)
    has_tracker = _file_contains(path, "index.html", rf'{TRACKER_DOMAIN}|pixel\.gif|sendBeacon')
    check("AI Tracker", 5, has_tracker, "visit analytics")

    # 11. Content depth ≥5000 bytes (10)
    check("Content Depth", 10, idx_size >= 5000, f"{idx_size:,} bytes (need ≥5000)")

    # 12. IndexNow key file (5)
    check(f"IndexNow Key", 5, _file_exists(path, f"{INDEXNOW_KEY}.txt"), "search engine notification")

    score = int(total / max_total * 100) if max_total > 0 else 0
    grade = "A+" if score >= 95 else "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D" if score >= 60 else "F"

    missing = [r["name"] for r in results if not r["passed"]]

    return {
        "slug": slug,
        "type": site["type"],
        "path": path,
        "score": score,
        "grade": grade,
        "total_points": total,
        "max_points": max_total,
        "checks": results,
        "missing": missing,
        "articles": _count_articles(path),
    }


def print_single(result: dict):
    """Pretty-print single site audit."""
    print(f"\n{'═' * 70}")
    print(f" 📊 {result['slug']} — {result['grade']} ({result['score']}%)")
    print(f"{'═' * 70}")
    for c in result["checks"]:
        icon = "✅" if c["passed"] else "❌"
        pts = f"{c['score']}/{c['weight']}"
        detail = f" — {c['detail']}" if c["detail"] else ""
        print(f"  {icon} {c['name']:<30} {pts:>6}{detail}")
    print(f"\n  📈 Score: {result['total_points']}/{result['max_points']} = {result['score']}% ({result['grade']})")
    if result["missing"]:
        print(f"  ❌ Missing: {', '.join(result['missing'])}")
    if result["articles"]:
        print(f"  📝 Articles: {result['articles']}")


def print_all(results: list):
    """Pretty-print all sites summary."""
    print(f"\n{'═' * 100}")
    print(f" 📊 AEO Quality Audit — {len(results)} Sites")
    print(f"{'═' * 100}")
    print(f"\n{'Slug':<30} {'Type':<6} {'Score':<7} {'Grade':<6} {'Missing'}")
    print("─" * 100)

    passing = 0
    for r in sorted(results, key=lambda x: -x["score"]):
        miss_str = ", ".join(r["missing"][:3])
        if len(r["missing"]) > 3:
            miss_str += f" (+{len(r['missing'])-3})"
        icon = "🟢" if r["score"] >= 90 else "🟡" if r["score"] >= 70 else "🔴"
        print(f"  {r['slug']:<28} {r['type']:<6} {icon}{r['score']:>3}%   {r['grade']:<6} {miss_str}")
        if r["score"] >= 90:
            passing += 1

    avg = sum(r["score"] for r in results) // len(results) if results else 0
    print(f"\n{'─' * 100}")
    print(f" 📈 Average: {avg}% | Passing (≥90): {passing}/{len(results)} | Target: {len(results)}/{len(results)}")
    print(f"{'═' * 100}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AEO 90分制品質評分器")
    parser.add_argument("--slug", help="Single site slug")
    parser.add_argument("--all", action="store_true", help="Audit all sites")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--missing-only", action="store_true", help="Only show sites < 90")
    args = parser.parse_args()

    if args.slug:
        sites = find_all_sites()
        site = next((s for s in sites if s["slug"] == args.slug), None)
        if not site:
            print(f"❌ Site not found: {args.slug}")
            sys.exit(1)
        result = audit_site(site)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print_single(result)

    elif args.all:
        sites = find_all_sites()
        results = [audit_site(s) for s in sites]
        if args.missing_only:
            results = [r for r in results if r["score"] < 90]
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            print_all(results)
    else:
        parser.print_help()
