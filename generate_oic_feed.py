import os
import re
from datetime import datetime, timezone
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

TARGET_URL = "https://www.princeedwardisland.ca/en/publications/orders-in-council"
BASE_URL = "https://www.princeedwardisland.ca"

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-CA,en-US;q=0.9,en;q=0.8"
})

print(f"Fetching {TARGET_URL}...")
response = session.get(TARGET_URL, timeout=30)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

fg = FeedGenerator()
fg.title("PEI Orders in Council Updates")
fg.link(href=TARGET_URL, rel="alternate")
fg.description("Automated feed for newly published Prince Edward Island Orders in Council")
fg.language("en")
fg.lastBuildDate(datetime.now(timezone.utc))

seen_urls = set()
entries = []

# Scan all anchor tags
for a in soup.find_all("a", href=True):
    href = a.get("href", "").strip()
    raw_text = a.get_text(separator=" ", strip=True)
    
    # Strip trailing arrows or icons
    clean_title = re.sub(r"[\s\u2192\u2794\u2022\u2190]+$", "", raw_text).strip()
    
    # Check if this link represents an OIC issue or a publication entry
    is_oic_text = bool(re.search(r"orders\s+in\s+council", clean_title, re.IGNORECASE))
    is_pub_link = "/publication/" in href.lower()
    
    if not (is_oic_text or (is_pub_link and "council" in href.lower())):
        continue

    # Filter out navigation/index headers
    if "annual index" in clean_title.lower() or "search" in clean_title.lower():
        continue
    if len(clean_title) < 5 or href in seen_urls:
        continue

    seen_urls.add(href)
    full_url = urljoin(BASE_URL, href)

    # Walk up the tree to find the row container for publication date
    parent = a.find_parent(["div", "li", "article", "td"])
    meta_text = parent.get_text(separator=" ", strip=True) if parent else ""

    pub_date_match = re.search(r"Published date:\s*([A-Za-z]+ \d{1,2}, \d{4})", meta_text)

    entries.append({
        "title": clean_title,
        "url": full_url,
        "pub_date_str": pub_date_match.group(1) if pub_date_match else None
    })

print(f"Discovered {len(entries)} OIC entries.")

# Fallback in case titles were blank or nested in custom divs
if not entries:
    print("Debug: Dumping top 20 links found in page:")
    for l in soup.find_all("a", href=True)[:20]:
        print(" ->", l.get("href"), "| Text:", l.get_text(strip=True)[:40])
    raise ValueError("Zero entries matched. Inspect debug output above.")

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
print(f"Successfully generated pei_oic_feed.xml with {len(entries[:25])} entries.")
