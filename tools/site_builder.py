#!/usr/bin/env python3
"""
site_builder.py — AEO 多客戶網站 Builder
從 client_sites.db 讀取配置，生成完整站點。

Usage:
  python3 site_builder.py --slug inari-global-foods --preview
  python3 site_builder.py --slug test-cafe --output ~/Documents/test-cafe/
"""

import os, sys, json, sqlite3, html, argparse
from datetime import datetime, date

DB_PATH = os.path.expanduser("~/.openclaw/memory/client_sites.db")
TRACKER_BASE = "https://YOUR_TRACKER.workers.dev"
CHAT_WORKER_BASE = "https://YOUR_CHAT_WORKER.workers.dev"
GITHUB_PAGES_BASE = "https://inari-kira-isla.github.io"
INDEXNOW_KEY = "YOUR_INDEXNOW_KEY"
BING_VERIFICATION = "YOUR_BING_VERIFICATION_CODE"

# ── Industry → Schema.org Type mapping ──
INDUSTRY_SCHEMA = {
    "restaurant": "Restaurant", "cafe": "CafeOrCoffeeShop",
    "food_delivery": "Store", "retail": "Store",
    "beauty": "HealthAndBeautyBusiness", "fitness": "SportsActivityLocation",
    "education": "EducationalOrganization", "consulting": "ProfessionalService",
    "technology": "Organization", "healthcare": "MedicalBusiness",
    "legal": "LegalService", "realestate": "RealEstateAgent",
    "accounting": "AccountingService", "logistics": "MovingCompany",
    "insurance": "InsuranceAgency", "media": "NewsMediaOrganization",
    "wedding": "EventVenue", "pet": "PetStore", "auto": "AutoRepair",
    "home": "HomeAndConstructionBusiness", "hr": "EmploymentAgency",
}

# ── Industry → Default color scheme ──
INDUSTRY_COLORS = {
    "cafe":          {"accent": "#4a7c59", "secondary": "#2d5a3a", "surface": "#0f1a13"},
    "restaurant":    {"accent": "#c4553a", "secondary": "#8b3324", "surface": "#1a0f0c"},
    "food_delivery": {"accent": "#8B7240", "secondary": "#6d5213", "surface": "#141210"},
    "beauty":        {"accent": "#b8628f", "secondary": "#8a4169", "surface": "#1a0f15"},
    "technology":    {"accent": "#3b82f6", "secondary": "#1d4ed8", "surface": "#0f1420"},
    "education":     {"accent": "#6366f1", "secondary": "#4338ca", "surface": "#10102a"},
    "consulting":    {"accent": "#0891b2", "secondary": "#0e7490", "surface": "#0f1a1e"},
    "fitness":       {"accent": "#ef4444", "secondary": "#b91c1c", "surface": "#1a0f0f"},
    "healthcare":    {"accent": "#14b8a6", "secondary": "#0d9488", "surface": "#0f1a19"},
    "default":       {"accent": "#39d2c0", "secondary": "#2ba89a", "surface": "#0f1a18"},
}


def load_site_config(slug: str) -> dict:
    """Load site config from DB."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    row = db.execute("SELECT * FROM client_sites WHERE slug = ?", (slug,)).fetchone()
    db.close()
    if not row:
        raise ValueError(f"Site not found: {slug}")
    return dict(row)


def _e(text: str) -> str:
    """HTML escape."""
    return html.escape(str(text or ""))


def _json_safe(text: str) -> str:
    """JSON string escape for LD-JSON."""
    return json.dumps(str(text or ""), ensure_ascii=False)[1:-1]


# ════════════════════════════════════════
# Section builders
# ════════════════════════════════════════

def build_head(c: dict) -> str:
    site_url = c.get("site_url") or f"{GITHUB_PAGES_BASE}/{c['slug']}"
    schema_type = c.get("schema_type") or INDUSTRY_SCHEMA.get(c["industry"], "Organization")
    colors = INDUSTRY_COLORS.get(c["industry"], INDUSTRY_COLORS["default"])
    accent = c.get("accent_color") or colors["accent"]
    secondary = c.get("secondary_color") or colors["secondary"]
    surface = colors.get("surface", "#141414")

    faq_items = json.loads(c.get("faq_items") or "[]")
    same_as = json.loads(c.get("same_as_urls") or "[]")

    # Schema.org Organization/Store
    org_schema = {
        "@context": "https://schema.org",
        "@type": schema_type,
        "name": c["business_name"],
        "alternateName": c.get("business_name_en") or "",
        "url": site_url,
        "description": c.get("description") or "",
    }
    if c.get("address_street"):
        org_schema["address"] = {
            "@type": "PostalAddress",
            "streetAddress": c["address_street"],
            "addressLocality": c.get("address_city") or "澳門",
            "addressCountry": c.get("address_country") or "MO",
        }
    if c.get("geo_lat") and c.get("geo_lng"):
        org_schema["geo"] = {"@type": "GeoCoordinates", "latitude": c["geo_lat"], "longitude": c["geo_lng"]}
    if c.get("telephone"):
        org_schema["contactPoint"] = [{"@type": "ContactPoint", "telephone": c["telephone"], "contactType": "customer service"}]
    if same_as:
        org_schema["sameAs"] = same_as

    # FAQPage schema
    faq_schema = ""
    if faq_items:
        faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": []}
        for faq in faq_items[:8]:
            faq_ld["mainEntity"].append({
                "@type": "Question", "name": faq.get("q", ""),
                "acceptedAnswer": {"@type": "Answer", "text": faq.get("a", "")}
            })
        faq_schema = f'\n    <script type="application/ld+json">\n    {json.dumps(faq_ld, ensure_ascii=False)}\n    </script>'

    # Breadcrumb
    breadcrumb = json.dumps({
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "CloudPipe", "item": "https://cloudpipe-landing.vercel.app"},
            {"@type": "ListItem", "position": 2, "name": c["business_name"], "item": site_url}
        ]
    }, ensure_ascii=False)

    return f'''<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_e(c["business_name"])} {_e(c.get("business_name_en") or "")} — {_e(c.get("tagline") or c.get("description","")[:60])}</title>
    <meta name="description" content="{_e(c.get("description","")[:160])}">
    <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
    <meta name="msvalidate.01" content="{BING_VERIFICATION}">
    <link rel="canonical" href="{site_url}/">
    <link rel="llms-txt" href="{site_url}/llms.txt">
    <meta property="og:title" content="{_e(c["business_name"])}">
    <meta property="og:description" content="{_e(c.get("description","")[:200])}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{site_url}/">
    <meta property="og:locale" content="zh_TW">
    <meta property="og:site_name" content="{_e(c["business_name"])}">
    <script type="application/ld+json">
    {json.dumps(org_schema, ensure_ascii=False)}
    </script>
    <script type="application/ld+json">
    {breadcrumb}
    </script>{faq_schema}
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --ink: #0d0d0d;
            --surface: {surface};
            --cream: #FAF6F0;
            --accent: {accent};
            --accent-light: {secondary};
            --text-cream: #D4CCC0;
            --text-muted: #6B6560;
        }}
        *, *::before, *::after {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{ font-family:'Noto Sans TC',system-ui,sans-serif; background:var(--ink); color:var(--cream); line-height:1.8; }}
        a {{ color:var(--accent); text-decoration:none; }} a:hover {{ text-decoration:underline; }}
        .w {{ max-width:900px; margin:0 auto; padding:0 24px; }}
        nav {{ position:sticky; top:0; z-index:100; background:rgba(13,13,13,0.95); backdrop-filter:blur(12px); border-bottom:1px solid #222; }}
        nav .w {{ display:flex; align-items:center; justify-content:space-between; height:56px; }}
        nav a {{ color:var(--text-cream); font-size:13px; margin-left:16px; }}
        .brand {{ font-size:18px; font-weight:600; color:var(--cream); }}
        .brand small {{ font-size:11px; color:var(--text-muted); font-weight:300; display:block; margin-top:-2px; }}
        section {{ padding:80px 0; }}
        .cream-bg {{ background:var(--cream); color:#1a1a1a; }}
        .cream-bg a {{ color:var(--accent-light); }}
        .label {{ font-size:11px; letter-spacing:2px; text-transform:uppercase; color:var(--accent); margin-bottom:8px; }}
        h2 {{ font-size:28px; font-weight:600; margin-bottom:24px; line-height:1.3; }}
        h3 {{ font-size:20px; font-weight:500; margin:32px 0 12px; }}
        p {{ margin-bottom:16px; font-size:15px; color:var(--text-cream); }}
        .cream-bg p {{ color:#444; }}
        .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:16px; padding:40px 0; text-align:center; }}
        .stats div {{ padding:24px; background:var(--surface); border:1px solid #222; border-radius:8px; }}
        .stats .num {{ font-size:32px; font-weight:600; color:var(--accent); }}
        .stats .txt {{ font-size:12px; color:var(--text-muted); margin-top:4px; }}
        .product-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px; }}
        .product-item {{ padding:14px 18px; background:var(--surface); border:1px solid #222; border-radius:8px; }}
        .product-item .name {{ font-size:14px; font-weight:500; }}
        .product-item .desc {{ font-size:12px; color:var(--text-muted); margin-top:4px; }}
        .contact-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:32px; }}
        @media(max-width:640px) {{ .contact-grid {{ grid-template-columns:1fr; }} .stats {{ grid-template-columns:repeat(2,1fr); }} }}
        .btn {{ display:inline-block; padding:12px 28px; background:var(--accent); color:#fff; border-radius:6px; font-size:14px; font-weight:500; }}
        .btn:hover {{ opacity:0.9; text-decoration:none; }}
        footer {{ background:#080808; padding:48px 0; font-size:12px; color:var(--text-muted); }}
        footer a {{ color:var(--text-cream); }}
        .eco-links {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }}
        .eco-links a {{ padding:4px 10px; background:#111; border:1px solid #222; border-radius:4px; font-size:11px; }}
    </style>
</head>
<body>'''


def build_nav(c: dict) -> str:
    name = _e(c["business_name"])
    name_en = _e(c.get("business_name_en") or "")
    return f'''
<nav>
    <div class="w">
        <div class="brand">{name}<small>{name_en}</small></div>
        <div>
            <a href="#about">關於</a>
            <a href="#products">產品</a>
            <a href="#contact">聯繫</a>
            <a href="#faq">FAQ</a>
        </div>
    </div>
</nav>'''


def build_hero(c: dict) -> str:
    tagline = _e(c.get("tagline") or c.get("description", "")[:80])
    desc = _e(c.get("description") or "")
    return f'''
<section class="hero" style="padding:100px 0 60px;text-align:center;">
    <div class="w">
        <h1 style="font-size:36px;font-weight:600;margin-bottom:12px;">{_e(c["business_name"])}</h1>
        <p style="font-size:16px;color:var(--text-muted);margin-bottom:24px;">{tagline}</p>
        <p style="max-width:600px;margin:0 auto 32px;">{desc}</p>
        <a href="#contact" class="btn">聯繫我們</a>
    </div>
</section>'''


def build_about(c: dict) -> str:
    about = c.get("about_text") or c.get("description") or ""
    paragraphs = about.split("\n\n") if "\n\n" in about else [about]
    paras_html = "\n".join(f"        <p>{_e(p.strip())}</p>" for p in paragraphs if p.strip())
    return f'''
<section id="about" class="cream-bg">
    <div class="w">
        <div class="label">About</div>
        <h2>關於我們</h2>
{paras_html}
    </div>
</section>'''


def build_products(c: dict) -> str:
    products = json.loads(c.get("products_services") or "[]")
    if not products:
        return ""
    items = []
    for p in products[:20]:
        name = _e(p.get("name", ""))
        desc = _e(p.get("description", ""))
        items.append(f'        <div class="product-item"><div class="name">{name}</div><div class="desc">{desc}</div></div>')
    NL = "\n"
    return f'''
<section id="products">
    <div class="w">
        <div class="label">Products & Services</div>
        <h2>產品與服務</h2>
        <div class="product-grid">
{NL.join(items)}
        </div>
    </div>
</section>'''


def build_faq(c: dict) -> str:
    faqs = json.loads(c.get("faq_items") or "[]")
    if not faqs:
        return ""
    items = []
    for faq in faqs[:10]:
        q = _e(faq.get("q", ""))
        a = _e(faq.get("a", ""))
        items.append(f'''        <details style="margin-bottom:12px;padding:16px;background:var(--surface);border:1px solid #222;border-radius:8px;">
            <summary style="cursor:pointer;font-weight:500;font-size:15px;">{q}</summary>
            <p style="margin-top:12px;font-size:14px;color:var(--text-cream);">{a}</p>
        </details>''')
    return f'''
<section id="faq" class="cream-bg">
    <div class="w">
        <div class="label">FAQ</div>
        <h2>常見問題</h2>
{"chr(10)".join(items)}
    </div>
</section>'''


def build_contact(c: dict) -> str:
    parts = []
    if c.get("address_street"):
        parts.append(f'<div><strong>地址</strong><p>{_e(c["address_street"])}<br>{_e(c.get("address_city",""))}</p></div>')
    if c.get("telephone"):
        parts.append(f'<div><strong>電話</strong><p><a href="tel:{_e(c["telephone"])}">{_e(c["telephone"])}</a></p></div>')
    if c.get("contact_email"):
        parts.append(f'<div><strong>Email</strong><p><a href="mailto:{_e(c["contact_email"])}">{_e(c["contact_email"])}</a></p></div>')

    hours = json.loads(c.get("opening_hours") or "[]")
    if hours:
        hours_str = ", ".join(hours) if isinstance(hours, list) else str(hours)
        parts.append(f'<div><strong>營業時間</strong><p>{_e(hours_str)}</p></div>')

    map_html = ""
    if c.get("geo_lat") and c.get("geo_lng"):
        map_html = f'''
        <div>
            <iframe src="https://www.google.com/maps?q={c["geo_lat"]},{c["geo_lng"]}&z=16&output=embed" width="100%" height="250" style="border:0;border-radius:8px;" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
        </div>'''

    return f'''
<section id="contact">
    <div class="w">
        <div class="label">Contact</div>
        <h2>聯繫我們</h2>
        <div class="contact-grid">
            <div>{"".join(parts)}</div>
            {map_html}
        </div>
    </div>
</section>'''


def build_chatbot_widget(c: dict) -> str:
    if not c.get("chatbot_enabled"):
        return ""
    slug = c["slug"]
    char_name = _e(c.get("chatbot_character_name") or "客服助手")
    char_emoji = c.get("chatbot_character_emoji") or "💬"
    accent = c.get("accent_color") or "#39d2c0"

    return f'''
<div style="position:fixed;bottom:24px;right:24px;z-index:999;">
    <div id="chat-box" style="display:none;width:360px;max-height:500px;background:#0d0d0d;border:1px solid #222;border-radius:10px;overflow:hidden;box-shadow:0 16px 48px rgba(0,0,0,0.5);font-family:'Noto Sans TC',sans-serif;">
        <div style="padding:12px 16px;background:rgba(255,255,255,0.03);border-bottom:1px solid #222;display:flex;justify-content:space-between;align-items:center;">
            <div style="display:flex;align-items:center;gap:10px;">
                <div style="width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,{accent},{accent}88);display:flex;align-items:center;justify-content:center;font-size:16px;">{char_emoji}</div>
                <div style="font-size:13px;font-weight:500;color:#FAF6F0;">{char_name}</div>
            </div>
            <button onclick="document.getElementById('chat-box').style.display='none'" style="background:none;border:none;color:#666;font-size:18px;cursor:pointer;">&times;</button>
        </div>
        <div id="chat-messages" style="height:280px;overflow-y:auto;padding:12px 16px;"></div>
        <div style="padding:10px 12px;border-top:1px solid #222;display:flex;gap:8px;">
            <input id="chat-input" type="text" placeholder="輸入問題..." style="flex:1;background:rgba(255,255,255,0.05);border:1px solid #333;border-radius:6px;padding:8px 12px;color:#FAF6F0;font-size:13px;outline:none;" onkeypress="if(event.key==='Enter')sendChatMsg()">
            <button onclick="sendChatMsg()" style="padding:8px 16px;background:{accent};border:none;border-radius:6px;color:#fff;font-size:13px;cursor:pointer;">發送</button>
        </div>
    </div>
    <button onclick="document.getElementById('chat-box').style.display=document.getElementById('chat-box').style.display==='none'?'block':'none'" style="width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,{accent},{accent}88);border:none;color:#fff;font-size:24px;cursor:pointer;box-shadow:0 4px 24px rgba(0,0,0,0.3);margin-top:12px;">{char_emoji}</button>
</div>
<script>
function addChatMsg(role,text){{var b=document.getElementById('chat-messages'),d=document.createElement('div');d.style.cssText='margin-bottom:10px;padding:8px 12px;border-radius:8px;font-size:13px;max-width:85%;'+(role==='user'?'background:rgba(255,255,255,0.08);margin-left:auto;color:#FAF6F0;':'background:rgba({accent.replace("#","").ljust(6,"0")},0.08);color:var(--text-cream);');d.textContent=text;b.appendChild(d);b.scrollTop=b.scrollHeight;}}
async function sendChatMsg(){{var i=document.getElementById('chat-input'),m=i.value.trim();if(!m)return;addChatMsg('user',m);i.value='';try{{var r=await fetch('{CHAT_WORKER_BASE}/{slug}/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{messages:[{{role:'user',content:m}}],stream:false}})}});if(r.ok){{var d=await r.json(),a=d.choices&&d.choices[0]&&d.choices[0].message?d.choices[0].message.content:'';a=a.replace(/<think>[\\s\\S]*?<\\/think>\\s*/g,'').trim();addChatMsg('bot',a||'感謝您的提問，請直接聯繫我們獲得更多資訊。');}}else{{addChatMsg('bot','暫時無法連線，請直接致電聯繫我們。');}}}}catch(e){{addChatMsg('bot','暫時無法連線，請直接致電聯繫我們。');}}}}
addChatMsg('bot','您好！我是{char_name} {char_emoji} 有什麼可以幫助您的嗎？');
</script>'''


def build_footer(c: dict) -> str:
    site_url = c.get("site_url") or f"{GITHUB_PAGES_BASE}/{c['slug']}"
    # Ecosystem links
    eco_sites = [
        ("CloudPipe", "https://cloudpipe-landing.vercel.app"),
        ("澳門百科", "https://cloudpipe-macao-app.vercel.app"),
        ("企業目錄", "https://cloudpipe-directory.vercel.app"),
        ("AI 學習寶庫", f"{GITHUB_PAGES_BASE}/Openclaw/"),
    ]
    eco_html = "\n".join(f'            <a href="{url}">{name}</a>' for name, url in eco_sites)

    return f'''
<footer>
    <div class="w">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:32px;margin-bottom:32px;">
            <div>
                <strong style="color:var(--cream);">{_e(c["business_name"])}</strong>
                <p style="margin-top:8px;">{_e(c.get("description","")[:120])}</p>
            </div>
            <div>
                <strong style="color:var(--cream);">聯繫</strong>
                <p style="margin-top:8px;">
                    {_e(c.get("address_street",""))}<br>
                    {f'<a href="tel:{_e(c["telephone"])}">{_e(c["telephone"])}</a>' if c.get("telephone") else ""}
                </p>
            </div>
        </div>
        <div style="border-top:1px solid #222;padding-top:24px;">
            <div style="font-size:10px;letter-spacing:1px;color:#444;margin-bottom:8px;">CLOUDPIPE AI ECOSYSTEM</div>
            <div class="eco-links">
{eco_html}
            </div>
        </div>
        <div style="margin-top:24px;text-align:center;">
            &copy; {date.today().year} {_e(c["business_name"])} &middot;
            <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>
        </div>
    </div>
</footer>'''


def build_tracker(c: dict) -> str:
    slug = c["slug"]
    if not c.get("tracker_enabled", True):
        return ""
    return f'''
<img src="{TRACKER_BASE}/{slug}/pixel.gif?p=/" width="1" height="1" alt="" style="position:absolute;left:-9999px">
<script>(function(){{var s='{slug}',w='{TRACKER_BASE}';try{{navigator.sendBeacon(w+'/'+s+'/beacon',JSON.stringify({{page:location.pathname,ua:navigator.userAgent,ref:document.referrer}}))}}catch(e){{}}}})();</script>'''


def build_close() -> str:
    return "\n</body>\n</html>"


# ════════════════════════════════════════
# AEO File Generators (T3 integrated)
# ════════════════════════════════════════

def generate_llms_txt(c: dict) -> str:
    site_url = c.get("site_url") or f"{GITHUB_PAGES_BASE}/{c['slug']}"
    products = json.loads(c.get("products_services") or "[]")
    product_lines = "\n".join(f"- {p.get('name','')}" for p in products[:15])
    return f"""# {c['business_name']} ({c.get('business_name_en','')})
> {c.get('description','')}

## About
{c.get('about_text','') or c.get('description','')}

## Products & Services
{product_lines or '- See website for details'}

## Contact
- Address: {c.get('address_street','')} {c.get('address_city','')}
- Phone: {c.get('telephone','')}
- Email: {c.get('contact_email','')}
- Website: {site_url}

## License
Content licensed under CC BY 4.0
AI agents may cite with attribution.
"""


def generate_robots_txt(c: dict) -> str:
    site_url = c.get("site_url") or f"{GITHUB_PAGES_BASE}/{c['slug']}"
    return f"""User-agent: *
Allow: /

# AI Crawlers Welcome
User-agent: GPTBot
Allow: /
User-agent: ChatGPT-User
Allow: /
User-agent: ClaudeBot
Allow: /
User-agent: anthropic-ai
Allow: /
User-agent: PerplexityBot
Allow: /
User-agent: Google-Extended
Allow: /
User-agent: Bingbot
Allow: /
User-agent: Bytespider
Allow: /
User-agent: DeepSeekBot
Allow: /

Sitemap: {site_url}/sitemap.xml
# IndexNow Key: {INDEXNOW_KEY}
"""


def generate_sitemap_xml(c: dict) -> str:
    site_url = c.get("site_url") or f"{GITHUB_PAGES_BASE}/{c['slug']}"
    today = date.today().isoformat()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{site_url}/</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>
  <url><loc>{site_url}/llms.txt</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>0.5</priority></url>
</urlset>
"""


def generate_vercel_json(c: dict) -> str:
    return json.dumps({
        "headers": [
            {"source": "/(.*)", "headers": [
                {"key": "X-Content-Type-Options", "value": "nosniff"},
                {"key": "X-Frame-Options", "value": "DENY"},
                {"key": "X-XSS-Protection", "value": "1; mode=block"},
                {"key": "Referrer-Policy", "value": "strict-origin-when-cross-origin"},
                {"key": "Strict-Transport-Security", "value": "max-age=63072000; includeSubDomains"},
            ]},
            {"source": "/llms.txt", "headers": [{"key": "Content-Type", "value": "text/plain; charset=utf-8"}]},
            {"source": "/security.txt", "headers": [{"key": "Content-Type", "value": "text/plain; charset=utf-8"}]},
        ],
        "rewrites": [{"source": "/.well-known/security.txt", "destination": "/security.txt"}],
    }, indent=2, ensure_ascii=False)


def generate_bingsiteauth_xml() -> str:
    return f"""<?xml version="1.0"?>
<users>
\t<user>{BING_VERIFICATION}</user>
</users>"""


def generate_indexnow_key_txt() -> str:
    return INDEXNOW_KEY


def generate_security_txt(c: dict) -> str:
    return f"""Contact: {c.get('contact_email','') or 'mailto:info@cloudpipe.io'}
Preferred-Languages: zh-TW, en
Canonical: {c.get('site_url','')}/security.txt
"""


# ════════════════════════════════════════
# Full site build
# ════════════════════════════════════════

def build_full_site(slug: str) -> dict:
    """Build complete site. Returns dict of filename → content."""
    c = load_site_config(slug)
    files = {}

    # index.html
    html_parts = [
        build_head(c),
        build_nav(c),
        build_hero(c),
        build_about(c),
        build_products(c),
        build_faq(c),
        build_contact(c),
        build_chatbot_widget(c),
        build_tracker(c),
        build_footer(c),
        build_close(),
    ]
    files["index.html"] = "\n".join(part for part in html_parts if part)

    # AEO files
    files["llms.txt"] = generate_llms_txt(c)
    files["robots.txt"] = generate_robots_txt(c)
    files["sitemap.xml"] = generate_sitemap_xml(c)
    files["vercel.json"] = generate_vercel_json(c)
    files["BingSiteAuth.xml"] = generate_bingsiteauth_xml()
    files[f"{INDEXNOW_KEY}.txt"] = generate_indexnow_key_txt()
    files["security.txt"] = generate_security_txt(c)

    return files


def write_site(slug: str, output_dir: str):
    """Write all site files to output directory."""
    files = build_full_site(slug)
    os.makedirs(output_dir, exist_ok=True)
    for filename, content in files.items():
        path = os.path.join(output_dir, filename)
        os.makedirs(os.path.dirname(path) or output_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  ✅ {filename} ({len(content):,} bytes)")
    print(f"\n📁 Site written to: {output_dir}")
    print(f"📊 {len(files)} files generated")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AEO Site Builder")
    parser.add_argument("--slug", required=True, help="Site slug from client_sites.db")
    parser.add_argument("--output", help="Output directory")
    parser.add_argument("--preview", action="store_true", help="Print HTML to stdout")
    parser.add_argument("--list", action="store_true", help="List available sites")
    args = parser.parse_args()

    if args.list:
        db = sqlite3.connect(DB_PATH)
        for row in db.execute("SELECT slug, business_name, status FROM client_sites ORDER BY id"):
            print(f"  {row[0]:30s} {row[1]:20s} [{row[2]}]")
        db.close()
        sys.exit(0)

    if args.preview:
        files = build_full_site(args.slug)
        print(files["index.html"])
    elif args.output:
        write_site(args.slug, args.output)
    else:
        files = build_full_site(args.slug)
        for name, content in files.items():
            print(f"  {name}: {len(content):,} bytes")
        print(f"\n使用 --output DIR 寫入檔案，或 --preview 預覽 HTML")
