from datetime import datetime
import os
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
import requests

TARGET_URL = (
    "https://www.princeedwardisland.ca/en/publications/orders-in-council"
)
BASE_URL = "https://www.princeedwardisland.ca"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

print(f"Fetching {TARGET_URL}...")
response = requests.get(TARGET_URL, headers=headers)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

fg = FeedGenerator()
fg.title("PEI Orders in Council Updates")
fg.link(href=TARGET_URL, rel="alternate")
fg.description(
    "Automated feed for newly published Prince Edward Island Orders in Council"
)
fg.language("en")

links = soup.select("a[href*='/publication/orders-in-council']")
seen_urls = set()

for link in links:
    href = link.get("href")
    title = link.get_text(strip=True)

    if not href or not title or href in seen_urls:
        continue
    if "index" in title.lower() and "annual" in title.lower():
        continue

    seen_urls.add(href)
    full_url = urljoin(BASE_URL, href)

    parent = link.find_parent(["div", "li", "article"])
    meta_text = parent.get_text(separator=" ", strip=True) if parent else ""

    pub_date_match = re.search(
        r"Published date:\s*([A-Za-z]+ \d{1,2}, \d{4})", meta_text
    )

    fe = fg.add_entry()
    fe.id(full_url)
    fe.title(title)
    fe.link(href=full_url)
    fe.description(f"{title} — Published by Executive Council Office.")

    if pub_date_match:
        try:
            parsed_date = datetime.strptime(
                pub_date_match.group(1), "%B %d, %Y"
            )
            fe.pubDate(parsed_date.strftime("%a, %d %b %Y 12:00:00 -0300"))
        except ValueError:
            pass

    if len(seen_urls) >= 20:
        break

fg.rss_file("pei_oic_feed.xml", pretty=True)
print("Successfully generated pei_oic_feed.xml")
