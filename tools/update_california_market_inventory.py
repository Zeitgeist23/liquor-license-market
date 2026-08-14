from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

OUT = Path("data/california-market-inventory.json")
UA = "LiquorLicenseMarket-Inventory/1.0 (+https://www.liquorlicensemarket.com/)"
SOURCES = [
    {
        "name": "AlcoholPermit.com",
        "url": "https://alcoholpermit.com/liquor-licenses/california/",
        "kind": "alcoholpermit",
    },
    {
        "name": "Liquor License Marketplace",
        "url": "https://liquorlicensemarketplace.com/california/",
        "kind": "marketplace",
    },
]


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def robots_allows(url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        response = requests.get(robots_url, timeout=20, headers={"User-Agent": UA})
        if response.status_code >= 400:
            return True
        rp = robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.parse(response.text.splitlines())
        return rp.can_fetch(UA, url) and rp.can_fetch("*", url)
    except Exception:
        return True


def get_soup(url: str) -> BeautifulSoup:
    response = requests.get(url, timeout=45, headers={"User-Agent": UA})
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def money(text: str):
    match = re.search(r"\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)", text)
    if not match:
        return None
    return int(round(float(match.group(1).replace(",", ""))))


def best_container(link, pattern: re.Pattern):
    node = link
    fallback = None
    for _ in range(8):
        node = getattr(node, "parent", None)
        if node is None:
            break
        text = clean(node.get_text(" ", strip=True))
        if 40 <= len(text) <= 1200 and pattern.search(text):
            fallback = node
            # Prefer the smallest useful card-like ancestor.
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
        title = pattern.search(text).group(0) if pattern.search(text) else f"{county} California – Type {type_code} Liquor License"
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
            "title": clean(title),
            "sourceUrl": href,
        })
        seen.add(href)
    return records, None


def main():
    combined = []
    source_status = []
    for source in SOURCES:
        try:
            if source["kind"] == "alcoholpermit":
                records, note = scrape_alcoholpermit(source)
            else:
                records, note = scrape_marketplace(source)
            combined.extend(records)
            source_status.append({"source": source["name"], "url": source["url"], "count": len(records), "note": note})
            print(f"{source['name']}: {len(records)} listings" + (f" ({note})" if note else ""))
        except Exception as exc:
            source_status.append({"source": source["name"], "url": source["url"], "count": 0, "note": f"sync error: {exc}"})
            print(f"Warning: {source['name']} failed: {exc}")

    if not combined:
        raise SystemExit("No third-party California inventory was retrieved; refusing to overwrite data.")

    combined.sort(key=lambda x: (x.get("county") or "", int(x.get("typeCode") or 999), x.get("price") if x.get("price") is not None else 10**12, x.get("source") or ""))
    payload = {
        "updatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "sources": source_status,
        "licenses": combined,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(combined)} third-party California listings to {OUT}")


if __name__ == "__main__":
    main()
