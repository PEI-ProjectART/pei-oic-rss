from datetime import datetime, timezone
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
import requests

TARGET_URL = (
    "https://www.princeedwardisland.ca/en/publications/orders-in-council"
)
BASE_URL = "https://www.princeedwardisland.ca"

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-CA,en-US;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
})

print(f"Fetching {TARGET_URL}...")
response = session.get(TARGET_URL, timeout=30)
response.raise_for_status()

html = response.text
print(f"Received HTML payload: {len(html)} bytes")

soup = BeautifulSoup(html, "html.parser")

fg = FeedGenerator()
fg.title("PEI Orders in Council Updates")
fg.link(href=TARGET_URL, rel="alternate")
fg.description(
    "Automated feed for newly published Prince Edward Island Orders in Council"
)
fg.language("en")
fg.lastBuildDate(datetime.now(timezone.utc))

# Search for anchor tags containing "Orders in Council" in text or href
entries = []
seen_urls = set()

for a in soup.find_all("a", href=True):
    text = a.get_text(separator=" ", strip=True)
    href = a["href"]

    # Match lines like "Orders in Council September 17, 2026 (897-956)"
    if re.search(r"Orders\s+in\s+Council\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}", text):
        if href in seen_urls:
            continue
        seen_urls.add(href)
        entries.append((text, urljoin(BASE_URL, href), a))

print(f"Matched {len(entries)} OIC publication batches.")

# Fallback check if Drupal wraps links differently
if not entries:
    for a in soup.find_all("a", href=re.compile(r"/publication/orders-in-council")):
        text = a.get_text(strip=True)
        href = a["href"]
        if text and href not in seen_urls:
            seen_urls.add(href)
            entries.append((text, urljoin(BASE_URL, href), a))
    print(f"Fallback matched {len(entries)} links.")

if not entries:
    raise ValueError(
        "Scraper found 0 entries! Check Action logs to inspect HTML response."
    )

for title, full_url, anchor in entries[:25]:
    parent = anchor.find_parent(["div", "li", "article", "td"])
    parent_text = parent.get_text(separator=" ", strip=True) if parent else ""

    pub_date_match = re.search(
        r"Published date:\s*([A-Za-z]+ \d{1,2}, \d{4})", parent_text
    )

    fe = fg.add_entry()
    fe.id(full_url, isPermalink=True)
    fe.title(title)
    fe.link(href=full_url)

    fe.description(
        f"<p><strong>{title}</strong></p>"
        f"<p>Published by Executive Council Office.</p>"
        f"<p><a href='{full_url}'>View Orders in Council Documents on"
        " PEI.ca</a></p>"
    )

    if pub_date_match:
        try:
            dt = datetime.strptime(pub_date_match.group(1), "%B %d, %Y")
            fe.pubDate(dt.replace(tzinfo=timezone.utc))
        except ValueError:
            fe.pubDate(datetime.now(timezone.utc))
    else:
        fe.pubDate(datetime.now(timezone.utc))

fg.rss_file("pei_oic_feed.xml", pretty=True)
print(f"Successfully generated pei_oic_feed.xml with {len(entries[:25])} items.")
