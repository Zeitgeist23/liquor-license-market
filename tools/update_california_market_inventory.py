from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from inventory_dedupe import dedupe_cross_source

OUT = Path("data/california-market-inventory.json")
UA = "LiquorLicenseMarket-Inventory/1.0 (+https://www.liquorlicensemarket.com/)"
SOURCES = [
    {"name": "AlcoholPermit.com", "url": "https://alcoholpermit.com/liquor-licenses/california/", "kind": "alcoholpermit"},
    {"name": "Liquor License Marketplace", "url": "https://liquorlicensemarketplace.com/california/", "kind": "marketplace"},
]


def clean(value):
    return re.sub(r"\s+", " ", value or "").strip()


def robots_allows(url):
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        response = requests.get(robots_url, timeout=10, headers={"User-Agent": UA})
        if response.status_code >= 400:
            return True
        rp = robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.parse(response.text.splitlines())
        return rp.can_fetch(UA, url) and rp.can_fetch("*", url)
    except Exception:
        return True


def get_soup(url):
    response = requests.get(url, timeout=20, headers={"User-Agent": UA})
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def money(text):
    match = re.search(r"\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)", text)
    return int(round(float(match.group(1).replace(",", "")))) if match else None


def best_container(link, pattern):
    node = link
    fallback = None
    for _ in range(8):
        node = getattr(node, "parent", None)
        if node is None:
            break
        text = clean(node.get_text(" ", strip=True))
        if 40 <= len(text) <= 1200 and pattern.search(text):
            fallback = node
            if len(text) <= 500:
                return node
    return fallback


def scrape_alcoholpermit(source):
    url = source["url"]
    if not robots_allows(url):
        return [], "robots.txt disallows automated retrieval"
    soup = get_soup(url)
    records = []
    seen = set()
    pattern = re.compile(r"California.*?([A-Za-z .'-]+) County.*?Type\s*(\d+)", re.I)
    for link in soup.find_all("a", href=True):
        if clean(link.get_text(" ", strip=True)).lower() not in {"view details", "details"}:
            continue
        href = urljoin(url, link["href"])
        if href in seen:
            continue
        card = best_container(link, pattern)
        if not card:
            continue
        text = clean(card.get_text(" ", strip=True))
        match = pattern.search(text)
        if not match:
            continue
        county = clean(match.group(1))
        type_code = match.group(2)
        if not county or len(county) > 40:
            continue
        price = money(text)
        private = "private listing" in text.lower() or "unlock the price" in text.lower()
        image = card.find("img", alt=True)
        image_alt = clean(image.get("alt")) if image else ""
        id_match = re.search(r"\bID\s*(\d+)\b", image_alt, re.I)
        title_el = card.find(["h2", "h3", "h4"])
        title = clean(title_el.get_text(" ", strip=True)) if title_el else f"California Type {type_code} Liquor License – {county} County"
        records.append({
            "source": source["name"],
            "sourceKind": "third-party",
            "county": county,
            "typeCode": type_code,
            "typeName": f"Type {type_code}",
            "price": None if private else price,
            "privatePrice": private,
            "listedDate": None,
            "sourceId": id_match.group(1) if id_match else None,
            "title": title,
            "sourceUrl": href,
        })
        seen.add(href)
    return records, None


def scrape_marketplace(source):
    url = source["url"]
    if not robots_allows(url):
        return [], "robots.txt disallows automated retrieval"
    soup = get_soup(url)
    records = []
    seen = set()
    pattern = re.compile(r"([A-Za-z .'-]+) California\s*[–-]\s*Type\s*(\d+).*?Liquor License", re.I)
    for link in soup.find_all("a", href=True):
        if clean(link.get_text(" ", strip=True)).lower() != "view listing":
            continue
        href = urljoin(url, link["href"])
        if href in seen:
            continue
        card = best_container(link, pattern)
        if not card:
            continue
        text = clean(card.get_text(" ", strip=True))
        match = pattern.search(text)
        if not match:
            continue
        county = clean(match.group(1))
        type_code = match.group(2)
        date_match = re.search(r"Listed:\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4})", text)
        price_match = re.search(r"Price:\s*\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)", text)
        price = int(round(float(price_match.group(1).replace(",", "")))) if price_match else None
        records.append({
            "source": source["name"],
            "sourceKind": "third-party",
            "county": county,
            "typeCode": type_code,
            "typeName": f"Type {type_code}",
            "price": price,
            "privatePrice": False,
            "listedDate": date_match.group(1) if date_match else None,
            "sourceId": None,
            "title": clean(match.group(0)),
            "sourceUrl": href,
        })
        seen.add(href)
    return records, None


def load_previous_by_source():
    previous = {source["name"]: [] for source in SOURCES}
    if not OUT.exists():
        return previous
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return previous

    for item in data.get("licenses") or []:
        source_rows = item.get("sourceListings") or [{
            "source": item.get("source"),
            "sourceUrl": item.get("sourceUrl"),
            "sourceId": item.get("sourceId"),
            "listedDate": item.get("listedDate"),
            "price": item.get("price"),
            "privatePrice": item.get("privatePrice", False),
        }]
        for source_row in source_rows:
            name = source_row.get("source")
            if name not in previous:
                continue
            previous[name].append({
                "source": name,
                "sourceKind": "third-party",
                "county": item.get("county"),
                "typeCode": item.get("typeCode"),
                "typeName": item.get("typeName"),
                "price": source_row.get("price"),
                "privatePrice": source_row.get("privatePrice", False),
                "listedDate": source_row.get("listedDate"),
                "sourceId": source_row.get("sourceId"),
                "title": item.get("title"),
                "sourceUrl": source_row.get("sourceUrl"),
            })
    return previous


def main():
    combined = []
    source_status = []
    previous = load_previous_by_source()

    for source in SOURCES:
        try:
            records, note = scrape_alcoholpermit(source) if source["kind"] == "alcoholpermit" else scrape_marketplace(source)
        except Exception as exc:
            records, note = [], f"sync error: {exc}"

        prior = previous.get(source["name"], [])
        retained_previous = False
        if prior:
            # A huge six-hour inventory collapse is overwhelmingly more likely to
            # be a timeout or parser failure than hundreds of licenses vanishing.
            floor = max(10, int(len(prior) * 0.60))
            if len(records) < floor:
                parsed_count = len(records)
                records = prior
                retained_previous = True
                reason = f"retrieval returned {parsed_count}; retained {len(prior)} last-good records"
                note = f"{note}; {reason}" if note else reason

        combined.extend(records)
        status = {
            "source": source["name"],
            "url": source["url"],
            "count": len(records),
            "note": note,
        }
        if retained_previous:
            status["retainedPrevious"] = True
        source_status.append(status)
        print(f"{source['name']}: {len(records)} listings" + (f" ({note})" if note else ""))

    if not combined:
        raise SystemExit("No third-party California inventory was retrieved; refusing to overwrite data.")

    unique, stats = dedupe_cross_source(combined)
    payload = {
        "updatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "sources": source_status,
        "rawRecordCount": stats["rawRecordCount"],
        "uniqueCount": stats["uniqueCount"],
        "duplicatesMerged": stats["duplicatesMerged"],
        "mergedCards": stats["mergedCards"],
        "licenses": unique,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"California dedupe: {stats['rawRecordCount']} raw -> {stats['uniqueCount']} unique; merged {stats['duplicatesMerged']} duplicate records")


if __name__ == "__main__":
    main()
