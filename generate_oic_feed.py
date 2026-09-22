import re
from datetime import datetime, timezone
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from playwright.sync_api import sync_playwright

TARGET_URL = "https://www.princeedwardisland.ca/en/publications/orders-in-council"
BASE_URL = "https://www.princeedwardisland.ca"

print(f"Launching browser to fetch {TARGET_URL}...")

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox"
        ]
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        locale="en-CA",
        timezone_id="America/Halifax"
    )
    page = context.new_page()

    # Avoid networkidle hang
    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
    
    # Give the page 5 seconds to run client scripts and render lists
    page.wait_for_timeout(5000)
    
    html = page.content()
    browser.close()

print(f"Successfully retrieved HTML ({len(html)} bytes). Parsing...")

soup = BeautifulSoup(html, "html.parser")

fg = FeedGenerator()
fg.title("PEI Orders in Council Updates")
fg.link(href=TARGET_URL, rel="alternate")
fg.description("Automated feed for newly published Prince Edward Island Orders in Council")
fg.language("en")
fg.lastBuildDate(datetime.now(timezone.utc))

seen_urls = set()
entries = []

for a in soup.find_all("a", href=True):
    href = a.get("href", "").strip()
    raw_text = a.get_text(separator=" ", strip=True)

    if not re.search(r"orders\s+in\s+council\s+[a-z]+\s+\d{1,2}", raw_text, re.I):
        continue
    if "annual index" in raw_text.lower():
        continue
    if href in seen_urls:
        continue

    seen_urls.add(href)
    full_url = urljoin(BASE_URL, href)
    clean_title = re.sub(r"[\s\u2192\u2794\u2022\u2190]+$", "", raw_text).strip()

    parent = a.find_parent(["div", "li", "article"])
    meta_text = parent.get_text(separator=" ", strip=True) if parent else ""
    pub_date_match = re.search(r"Published date:\s*([A-Za-z]+ \d{1,2}, \d{4})", meta_text)

    entries.append({
        "title": clean_title,
        "url": full_url,
        "pub_date_str": pub_date_match.group(1) if pub_date_match else None
    })

print(f"Extracted {len(entries)} OIC batches.")

if not entries:
    # Print page title to check if we hit Cloudflare's "Just a moment..."
    title_tag = soup.find("title")
    print("Page Title was:", title_tag.get_text(strip=True) if title_tag else "No title")
    raise ValueError("Zero entries found. Check page title above.")

for item in entries[:25]:
    fe = fg.add_entry()
    fe.id(item["url"], isPermalink=True)
    fe.title(item["title"])
    fe.link(href=item["url"])
    
    desc_html = (
        f"<p><strong>{item['title']}</strong></p>"
        f"<p>Published by Executive Council Office.</p>"
        f"<p><a href='{item['url']}'>View Orders in Council Documents on PEI.ca</a></p>"
    )
    fe.description(desc_html)

    if item["pub_date_str"]:
        try:
            dt = datetime.strptime(item["pub_date_str"], "%B %d, %Y")
            fe.pubDate(dt.replace(tzinfo=timezone.utc))
        except ValueError:
            fe.pubDate(datetime.now(timezone.utc))
    else:
        fe.pubDate(datetime.now(timezone.utc))

fg.rss_file("pei_oic_feed.xml", pretty=True)
print(f"Generated pei_oic_feed.xml with {len(entries[:25])} items.")
