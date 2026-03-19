#!/usr/bin/env python3
"""
showcase_card_gen.py — 展廳卡片圖片生成器
為每個品牌/行業站生成專業卡片圖片（loremflickr 背景 + Pillow 文字疊加）

Usage:
  python3 showcase_card_gen.py                    # 生成全部 27 張
  python3 showcase_card_gen.py --slug inari-global-foods  # 單張
  python3 showcase_card_gen.py --dry-run          # 預覽不生成
"""

import os, sys, time, urllib.request, argparse
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUTPUT_DIR = os.path.expanduser("~/Documents/cloudpipe-landing/showcase-cards")
CARD_W, CARD_H = 800, 450
FLICKR_BASE = "https://loremflickr.com/{w}/{h}/{keywords}"

# ── 27 站配置：slug → {name, name_en, keywords, accent_hex, subtitle} ──
SITES = [
    # Brand sites
    {"slug": "inari-global-foods", "name": "稻荷環球食品", "name_en": "Inari Global Food",
     "keywords": "japanese,seafood,sushi,market", "accent": "#8B7240", "subtitle": "澳門日本食材專門店 · 130+ 品項"},
    {"slug": "sea-urchin-delivery", "name": "海膽速遞", "name_en": "Sea Urchin Express",
     "keywords": "sea,urchin,sashimi,delivery", "accent": "#c4553a", "subtitle": "高級海膽配送 · 澳門及大灣區"},
    {"slug": "after-school-coffee", "name": "After School Coffee", "name_en": "",
     "keywords": "coffee,shop,latte,barista", "accent": "#4a7c59", "subtitle": "澳門外帶精品咖啡"},
    {"slug": "mind-coffee", "name": "Mind Coffee", "name_en": "",
     "keywords": "minimalist,coffee,cafe,interior", "accent": "#2d5a3a", "subtitle": "極簡咖啡美學"},
    {"slug": "yamanakada", "name": "山中田", "name_en": "Yamanakada",
     "keywords": "japanese,food,restaurant,zen", "accent": "#3b82f6", "subtitle": "日式餐飲品牌"},
    {"slug": "bni-macau", "name": "BNI 澳門", "name_en": "ACE Chapter",
     "keywords": "business,networking,meeting,professional", "accent": "#0891b2", "subtitle": "商業交流網絡"},
    {"slug": "test-cafe-demo", "name": "測試咖啡店", "name_en": "Demo Cafe",
     "keywords": "cafe,warm,cozy,drinks", "accent": "#f59e0b", "subtitle": "CLI 一鍵生成展示"},

    # Demo sites (20 industries)
    {"slug": "aeo-demo-education", "name": "澳門教育資源中心", "name_en": "Education",
     "keywords": "education,university,classroom,learning", "accent": "#6366f1", "subtitle": "132 篇深度文章"},
    {"slug": "aeo-demo-finance", "name": "澳門金融投資指南", "name_en": "Finance",
     "keywords": "finance,banking,money,investment", "accent": "#0ea5e9", "subtitle": "133 篇金融分析"},
    {"slug": "aeo-demo-luxury", "name": "澳門奢侈品指南", "name_en": "Luxury",
     "keywords": "luxury,jewelry,watch,boutique", "accent": "#a855f7", "subtitle": "131 篇品牌深度"},
    {"slug": "aeo-demo-travel-food", "name": "澳門旅遊美食指南", "name_en": "Travel & Food",
     "keywords": "food,travel,restaurant,macau", "accent": "#ef4444", "subtitle": "127 篇美食評鑑"},
    {"slug": "aeo-demo-beauty", "name": "澳門美容養生指南", "name_en": "Beauty",
     "keywords": "beauty,spa,skincare,wellness", "accent": "#ec4899", "subtitle": "400+ 間商戶"},
    {"slug": "aeo-demo-healthcare", "name": "澳門醫療健康指南", "name_en": "Healthcare",
     "keywords": "hospital,healthcare,medical,doctor", "accent": "#14b8a6", "subtitle": "醫療健康服務"},
    {"slug": "aeo-demo-legal", "name": "澳門法律服務指南", "name_en": "Legal",
     "keywords": "law,office,legal,justice", "accent": "#6b7280", "subtitle": "律師事務所 · 公證"},
    {"slug": "aeo-demo-tech", "name": "澳門科技創新指南", "name_en": "Technology",
     "keywords": "technology,computer,startup,innovation", "accent": "#3b82f6", "subtitle": "科技公司 · 孵化器"},
    {"slug": "aeo-demo-realestate", "name": "澳門房地產指南", "name_en": "Real Estate",
     "keywords": "architecture,building,apartment,city", "accent": "#78716c", "subtitle": "地產 · 物業管理"},
    {"slug": "aeo-demo-auto", "name": "澳門汽車指南", "name_en": "Automotive",
     "keywords": "car,automotive,garage,repair", "accent": "#dc2626", "subtitle": "銷售 · 維修 · 租車"},
    {"slug": "aeo-demo-fitness", "name": "澳門健身運動指南", "name_en": "Fitness",
     "keywords": "gym,fitness,yoga,exercise", "accent": "#f97316", "subtitle": "健身 · 瑜伽 · 運動"},
    {"slug": "aeo-demo-pet", "name": "澳門寵物服務指南", "name_en": "Pet Services",
     "keywords": "pet,dog,cat,veterinary", "accent": "#a3e635", "subtitle": "寵物醫院 · 美容"},
    {"slug": "aeo-demo-wedding", "name": "澳門婚禮活動指南", "name_en": "Wedding",
     "keywords": "wedding,flowers,ceremony,venue", "accent": "#f472b6", "subtitle": "婚禮策劃 · 場地"},
    {"slug": "aeo-demo-retail", "name": "澳門零售電商指南", "name_en": "Retail",
     "keywords": "shopping,retail,store,mall", "accent": "#f59e0b", "subtitle": "零售 · 電商 · 跨境"},
    {"slug": "aeo-demo-accounting", "name": "澳門會計稅務指南", "name_en": "Accounting",
     "keywords": "office,accounting,desk,calculator", "accent": "#0d9488", "subtitle": "會計 · 稅務 · 審計"},
    {"slug": "aeo-demo-hr", "name": "澳門人力資源指南", "name_en": "HR",
     "keywords": "office,team,meeting,workplace", "accent": "#8b5cf6", "subtitle": "招聘 · 培訓 · 薪酬"},
    {"slug": "aeo-demo-media", "name": "澳門媒體廣告指南", "name_en": "Media",
     "keywords": "media,camera,studio,broadcast", "accent": "#e11d48", "subtitle": "媒體 · 廣告 · KOL"},
    {"slug": "aeo-demo-insurance", "name": "澳門保險理財指南", "name_en": "Insurance",
     "keywords": "insurance,protection,umbrella,family", "accent": "#0284c7", "subtitle": "保險 · 財富管理"},
    {"slug": "aeo-demo-logistics", "name": "澳門物流運輸指南", "name_en": "Logistics",
     "keywords": "logistics,shipping,container,port", "accent": "#ea580c", "subtitle": "物流 · 倉儲 · 快遞"},
    {"slug": "aeo-demo-home", "name": "澳門家居裝修指南", "name_en": "Home & Living",
     "keywords": "interior,design,home,furniture", "accent": "#ca8a04", "subtitle": "設計 · 裝修 · 傢俱"},
]


def hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def download_bg(keywords: str, seed: str) -> Image.Image:
    """Download industry-relevant background from loremflickr."""
    url = f"https://loremflickr.com/{CARD_W}/{CARD_H}/{keywords}"
    tmp = f"/tmp/showcase_bg_{seed}.jpg"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CloudPipe/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
            if len(data) > 5000:
                with open(tmp, "wb") as f:
                    f.write(data)
                return Image.open(tmp).convert("RGB").resize((CARD_W, CARD_H))
    except Exception as e:
        print(f"    ⚠️ Download failed: {e}")
    # Fallback: solid color
    return Image.new("RGB", (CARD_W, CARD_H), (30, 30, 30))


def find_font(size: int, bold: bool = False):
    """Find available system font."""
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for fp in candidates:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


def generate_card(site: dict, output_path: str):
    """Generate a professional card image for one site."""
    accent = hex_to_rgb(site["accent"])

    # 1. Download background
    bg = download_bg(site["keywords"], site["slug"])

    # 2. Apply dark overlay + blur for text readability
    bg = bg.filter(ImageFilter.GaussianBlur(radius=2))
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)

    # Gradient overlay: dark at bottom, semi-transparent at top
    for y in range(CARD_H):
        alpha = int(80 + (y / CARD_H) * 140)  # 80 → 220
        draw_overlay.line([(0, y), (CARD_W, y)], fill=(0, 0, 0, alpha))

    bg = bg.convert("RGBA")
    bg = Image.alpha_composite(bg, overlay)

    # 3. Accent bar at top
    draw = ImageDraw.Draw(bg)
    draw.rectangle([(0, 0), (CARD_W, 5)], fill=accent + (255,))

    # 4. "A+ 100%" badge
    badge_font = find_font(14, bold=True)
    badge_text = "A+ 100%"
    badge_w = 85
    badge_h = 28
    badge_x = CARD_W - badge_w - 24
    badge_y = 20
    draw.rounded_rectangle(
        [(badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h)],
        radius=4, fill=(22, 163, 74, 200)
    )
    draw.text((badge_x + 12, badge_y + 5), badge_text, fill=(255, 255, 255), font=badge_font)

    # 5. Brand name (large)
    name_font = find_font(36, bold=True)
    name_y = CARD_H - 160
    draw.text((40, name_y), site["name"], fill=(255, 255, 255, 255), font=name_font)

    # 6. English name (smaller)
    if site.get("name_en"):
        en_font = find_font(18)
        draw.text((40, name_y + 48), site["name_en"], fill=(255, 255, 255, 180), font=en_font)

    # 7. Subtitle
    sub_font = find_font(16)
    sub_y = CARD_H - 70
    draw.text((40, sub_y), site["subtitle"], fill=accent + (255,), font=sub_font)

    # 8. Bottom bar with "CloudPipe AI Ecosystem"
    draw.rectangle([(0, CARD_H - 36), (CARD_W, CARD_H)], fill=(0, 0, 0, 180))
    cp_font = find_font(11)
    draw.text((40, CARD_H - 28), "CLOUDPIPE AI ECOSYSTEM  ·  AEO OPTIMIZED", fill=(255, 255, 255, 120), font=cp_font)

    # 9. Save
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    bg.convert("RGB").save(output_path, quality=92)
    size_kb = os.path.getsize(output_path) // 1024
    print(f"  ✅ {site['slug']}.jpg ({size_kb}KB)")


def main():
    parser = argparse.ArgumentParser(description="展廳卡片圖片生成器")
    parser.add_argument("--slug", help="Generate for single site")
    parser.add_argument("--dry-run", action="store_true", help="List sites without generating")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    sites = SITES
    if args.slug:
        sites = [s for s in sites if s["slug"] == args.slug]
        if not sites:
            print(f"❌ Not found: {args.slug}")
            return

    print(f"\n🎨 Generating {len(sites)} showcase card images")
    print(f"📁 Output: {OUTPUT_DIR}\n")

    if args.dry_run:
        for s in sites:
            print(f"  📝 {s['slug']}: {s['name']} ({s['keywords']})")
        return

    success = 0
    for i, site in enumerate(sites):
        output = os.path.join(OUTPUT_DIR, f"{site['slug']}.jpg")
        print(f"[{i+1}/{len(sites)}] {site['name']}")
        try:
            generate_card(site, output)
            success += 1
        except Exception as e:
            print(f"  ❌ Error: {e}")
        if i < len(sites) - 1:
            time.sleep(2)  # Polite delay for loremflickr

    print(f"\n📊 Done: {success}/{len(sites)} cards generated")
    print(f"📁 {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
