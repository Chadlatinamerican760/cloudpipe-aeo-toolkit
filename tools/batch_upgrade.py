#!/usr/bin/env python3
"""
batch_upgrade.py — 批量 AEO 注入引擎
掃描所有站點缺失項，用 marker 注入 chatbot/tracker/AEO 檔案。
冪等：可重複執行，已有組件不重複注入。

Usage:
  python3 batch_upgrade.py --dry-run          # 只報告，不修改
  python3 batch_upgrade.py --execute          # 執行補全
  python3 batch_upgrade.py --execute --brands # 只處理品牌站
  python3 batch_upgrade.py --execute --demos  # 只處理 demo 站
"""

import os, sys, re, json, argparse

sys.path.insert(0, os.path.dirname(__file__))
from site_quality_audit import find_all_sites, audit_site

INDEXNOW_KEY = "YOUR_INDEXNOW_KEY"
BING_VERIFICATION = "YOUR_BING_VERIFICATION_CODE"
TRACKER_BASE = "https://YOUR_TRACKER.workers.dev"
CHAT_WORKER_BASE = "https://YOUR_CHAT_WORKER.workers.dev"
INJECT_START = "<!-- CLOUDPIPE-INJECT-START -->"
INJECT_END = "<!-- CLOUDPIPE-INJECT-END -->"


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _write(path: str, content: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _file_exists(site_path: str, filename: str) -> bool:
    return os.path.exists(os.path.join(site_path, filename))


# ════════════════════════════════════════
# AEO file generators
# ════════════════════════════════════════

def gen_bingsiteauth() -> str:
    return f'<?xml version="1.0"?>\n<users>\n\t<user>{BING_VERIFICATION}</user>\n</users>'


def gen_indexnow_key() -> str:
    return INDEXNOW_KEY


def gen_security_txt(slug: str) -> str:
    return f"Contact: mailto:info@cloudpipe.ai\nPreferred-Languages: zh-TW, en\nCanonical: https://inari-kira-isla.github.io/{slug}/security.txt\n"


# ════════════════════════════════════════
# HTML injection (before </body>)
# ════════════════════════════════════════

def build_inject_block(slug: str, site_type: str) -> str:
    """Build the chatbot + tracker injection block."""
    # Determine chatbot brand — use slug for brands, 'default' for demos
    chat_brand = slug if site_type == "brand" else "default"

    # Industry-aware emoji for demos
    emoji_map = {
        "education": "📚", "finance": "💰", "luxury": "💎", "travel-food": "🍜",
        "beauty": "💄", "healthcare": "🏥", "legal": "⚖️", "tech": "💻",
        "auto": "🚗", "fitness": "💪", "pet": "🐾", "wedding": "💒",
        "realestate": "🏠", "accounting": "📊", "hr": "👥", "media": "📺",
        "logistics": "📦", "insurance": "🛡️", "home": "🏡", "retail": "🛍️",
    }
    # Extract industry from slug like "aeo-demo-beauty" → "beauty"
    industry = slug.replace("aeo-demo-", "") if slug.startswith("aeo-demo-") else ""
    emoji = emoji_map.get(industry, "💬")
    char_name = "CloudPipe AI 助手"

    block = f"""{INJECT_START}
<!-- AI Chatbot -->
<div style="position:fixed;bottom:20px;right:20px;z-index:9999;">
<div id="cp-chat" style="display:none;width:340px;max-height:460px;background:#fff;border:1px solid #e0e0e0;border-radius:12px;overflow:hidden;box-shadow:0 12px 40px rgba(0,0,0,0.12);font-family:system-ui,sans-serif;">
<div style="padding:10px 14px;background:#f8f8f8;border-bottom:1px solid #eee;display:flex;justify-content:space-between;align-items:center;">
<div style="display:flex;align-items:center;gap:8px;"><span style="font-size:18px;">{emoji}</span><span style="font-size:12px;font-weight:600;">{char_name}</span></div>
<button onclick="document.getElementById('cp-chat').style.display='none'" style="background:none;border:none;font-size:16px;cursor:pointer;color:#999;">&times;</button>
</div>
<div id="cp-msgs" style="height:240px;overflow-y:auto;padding:10px 14px;"></div>
<div style="padding:8px 10px;border-top:1px solid #eee;display:flex;gap:6px;">
<input id="cp-in" type="text" placeholder="輸入問題..." style="flex:1;border:1px solid #ddd;border-radius:6px;padding:7px 10px;font-size:12px;outline:none;" onkeypress="if(event.key==='Enter')cpS()">
<button onclick="cpS()" style="padding:7px 12px;background:#111;color:#fff;border:none;border-radius:6px;font-size:12px;cursor:pointer;">發送</button>
</div>
</div>
<button onclick="var c=document.getElementById('cp-chat');c.style.display=c.style.display==='none'?'block':'none'" style="width:48px;height:48px;border-radius:50%;background:#111;border:none;color:#fff;font-size:20px;cursor:pointer;box-shadow:0 4px 16px rgba(0,0,0,0.15);margin-top:8px;">{emoji}</button>
</div>
<script>
function cpA(r,t){{var m=document.getElementById('cp-msgs'),d=document.createElement('div');d.style.cssText='margin-bottom:8px;padding:7px 10px;border-radius:8px;font-size:12px;max-width:85%;line-height:1.5;'+(r==='u'?'background:#f0f0f0;margin-left:auto;':'background:#f8f8f8;');d.textContent=t;m.appendChild(d);m.scrollTop=m.scrollHeight;}}
async function cpS(){{var i=document.getElementById('cp-in'),m=i.value.trim();if(!m)return;cpA('u',m);i.value='';try{{var r=await fetch('{CHAT_WORKER_BASE}/{chat_brand}/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{messages:[{{role:'user',content:m}}],stream:false}})}});if(r.ok){{var d=await r.json(),a=d.choices&&d.choices[0]&&d.choices[0].message?d.choices[0].message.content:'';a=a.replace(/<think>[\\s\\S]*?<\\/think>\\s*/g,'').trim();cpA('b',a||'請直接聯繫我們了解更多。');}}else cpA('b','暫時無法連線，請稍後再試。');}}catch(e){{cpA('b','暫時無法連線，請稍後再試。');}}}}
cpA('b','您好！{emoji} 我是 AI 助手，有什麼可以幫助您？');
</script>
<!-- AI Tracker -->
<img src="{TRACKER_BASE}/{slug}/pixel.gif?p=/" width="1" height="1" alt="" style="position:absolute;left:-9999px">
<script>(function(){{try{{navigator.sendBeacon('{TRACKER_BASE}/{slug}/beacon',JSON.stringify({{page:location.pathname,ua:navigator.userAgent,ref:document.referrer}}))}}catch(e){{}}}})();</script>
{INJECT_END}"""
    return block


def inject_into_html(site_path: str, slug: str, site_type: str, dry_run: bool) -> list:
    """Inject chatbot + tracker into index.html. Returns list of actions taken."""
    actions = []
    html_path = os.path.join(site_path, "index.html")
    if not os.path.exists(html_path):
        return actions

    content = _read(html_path)

    # Check if already injected
    if INJECT_START in content:
        if dry_run:
            actions.append("  ⏭️ Already injected (marker found)")
        else:
            # Remove old injection, re-inject (idempotent)
            content = re.sub(
                rf'{re.escape(INJECT_START)}.*?{re.escape(INJECT_END)}',
                '', content, flags=re.DOTALL
            ).strip()
            # Re-inject
            block = build_inject_block(slug, site_type)
            content = content.replace("</body>", f"\n{block}\n</body>")
            _write(html_path, content)
            actions.append("  🔄 Re-injected (updated)")
        return actions

    # Check what's missing
    has_chatbot = bool(re.search(r'client-chat-worker|cbSend|cpS\(\)|sendChatMsg|chat-widget', content))
    has_tracker = bool(re.search(r'client-ai-tracker|pixel\.gif|sendBeacon', content))

    if has_chatbot and has_tracker:
        actions.append("  ⏭️ Chatbot + Tracker already present (no marker)")
        return actions

    # Inject
    block = build_inject_block(slug, site_type)
    if "</body>" in content:
        if dry_run:
            missing = []
            if not has_chatbot:
                missing.append("chatbot")
            if not has_tracker:
                missing.append("tracker")
            actions.append(f"  📝 Would inject: {', '.join(missing)}")
        else:
            content = content.replace("</body>", f"\n{block}\n</body>")
            _write(html_path, content)
            actions.append("  ✅ Injected chatbot + tracker")
    else:
        actions.append("  ⚠️ No </body> tag found!")

    return actions


def write_missing_files(site_path: str, slug: str, dry_run: bool) -> list:
    """Write missing AEO files. Returns list of actions."""
    actions = []

    files_to_check = {
        "BingSiteAuth.xml": gen_bingsiteauth(),
        f"{INDEXNOW_KEY}.txt": gen_indexnow_key(),
        "security.txt": gen_security_txt(slug),
    }

    for filename, content in files_to_check.items():
        if not _file_exists(site_path, filename):
            if dry_run:
                actions.append(f"  📝 Would create: {filename}")
            else:
                _write(os.path.join(site_path, filename), content)
                actions.append(f"  ✅ Created: {filename}")
        # Don't report already-existing files to keep output clean

    return actions


def process_site(site: dict, dry_run: bool) -> dict:
    """Process a single site. Returns summary."""
    slug = site["slug"]
    path = site["path"]
    site_type = site["type"]

    actions = []

    # 1. Write missing AEO files
    actions.extend(write_missing_files(path, slug, dry_run))

    # 2. Inject chatbot + tracker into HTML
    actions.extend(inject_into_html(path, slug, site_type, dry_run))

    # 3. Audit after changes
    if not dry_run:
        result = audit_site(site)
        score = result["score"]
    else:
        result = audit_site(site)
        # Estimate score after fixes
        missing_fixable = {"BingSiteAuth.xml": 5, "Chatbot Widget": 10, "AI Tracker": 5, "IndexNow Key": 5}
        bonus = sum(v for k, v in missing_fixable.items() if k in result["missing"])
        score = min(100, result["score"] + int(bonus / result["max_points"] * 100))

    return {
        "slug": slug,
        "type": site_type,
        "actions": actions,
        "score_before": result["score"] if dry_run else score,
        "score_after": score,
        "grade": "A+" if score >= 95 else "A" if score >= 90 else "B" if score >= 80 else "C",
    }


def main():
    parser = argparse.ArgumentParser(description="批量 AEO 注入引擎")
    parser.add_argument("--dry-run", action="store_true", help="只報告，不修改")
    parser.add_argument("--execute", action="store_true", help="執行補全")
    parser.add_argument("--brands", action="store_true", help="只處理品牌站")
    parser.add_argument("--demos", action="store_true", help="只處理 demo 站")
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        parser.print_help()
        print("\n❌ Specify --dry-run or --execute")
        return

    sites = find_all_sites()
    if args.brands:
        sites = [s for s in sites if s["type"] == "brand"]
    elif args.demos:
        sites = [s for s in sites if s["type"] == "demo"]

    mode = "DRY RUN" if args.dry_run else "EXECUTE"
    print(f"\n{'═' * 70}")
    print(f" 🔧 Batch AEO Upgrade — {mode} — {len(sites)} sites")
    print(f"{'═' * 70}")

    results = []
    for site in sites:
        print(f"\n📌 {site['slug']} ({site['type']})")
        r = process_site(site, args.dry_run)
        results.append(r)
        for action in r["actions"]:
            print(action)
        icon = "🟢" if r["score_after"] >= 90 else "🟡"
        label = f"estimated" if args.dry_run else "actual"
        print(f"  {icon} Score: {r['score_after']}% ({r['grade']}) [{label}]")

    # Summary
    passing = sum(1 for r in results if r["score_after"] >= 90)
    print(f"\n{'═' * 70}")
    print(f" 📊 Result: {passing}/{len(results)} sites ≥ 90%")
    if not args.dry_run:
        print(f" 💾 All changes written to disk")
        print(f" 📌 Next: git add + commit + push for each site")
    print(f"{'═' * 70}\n")


if __name__ == "__main__":
    main()
