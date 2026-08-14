from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

UA = "LiquorLicenseMarket-Inventory/1.0 (+https://www.liquorlicensemarket.com/)"

STATES = {
    "arizona": {
        "name": "Arizona",
        "alcoholpermit": "https://alcoholpermit.com/liquor-licenses/arizona/",
        "marketplace": "https://liquorlicensemarketplace.com/arizona/",
        "types": ["Series 6", "Series 7", "Series 9"],
    },
    "new-mexico": {
        "name": "New Mexico",
        "alcoholpermit": "https://alcoholpermit.com/liquor-licenses/new-mexico/",
        "marketplace": "https://liquorlicensemarketplace.com/new-mexico/",
        "types": ["Inter-Local Dispenser License", "Inter Local Dispenser (ILD)", "Dispenser License", "Dispensers License"],
    },
    "michigan": {
        "name": "Michigan",
        "alcoholpermit": "https://alcoholpermit.com/liquor-licenses/michigan/",
        "marketplace": "https://liquorlicensemarketplace.com/michigan/",
        "types": ["Class C Resort", "Class C", "Tavern", "SDD"],
    },
    "ohio": {
        "name": "Ohio",
        "alcoholpermit": "https://alcoholpermit.com/liquor-licenses/ohio/",
        "marketplace": "https://liquorlicensemarketplace.com/ohio/",
        "types": ["C1 + C2", "D-1", "D-2", "D-3", "D-5"],
    },
    "pennsylvania": {
        "name": "Pennsylvania",
        "alcoholpermit": "https://alcoholpermit.com/liquor-licenses/pennsylvania/",
        "marketplace": "https://liquorlicensemarketplace.com/pennsylvania/",
        "types": ["Type R", "Type E", "Type D"],
    },
    "new-jersey": {
        "name": "New Jersey",
        "alcoholpermit": "https://alcoholpermit.com/liquor-licenses/new-jersey/",
        "marketplace": "https://liquorlicensemarketplace.com/new-jersey/",
        "types": ["Type 32", "Type 33", "Type 44"],
    },
}


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
    response = requests.get(url, timeout=50, headers={"User-Agent": UA})
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def money(text: str):
    match = re.search(r"\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)", text)
    if not match:
        return None
    return int(round(float(match.group(1).replace(",", ""))))


def smallest_card(link, must_contain: str | None = None):
    node = link
    fallback = None
    for _ in range(10):
        node = getattr(node, "parent", None)
        if node is None:
            break
        text = clean(node.get_text(" ", strip=True))
        if 30 <= len(text) <= 1200 and (not must_contain or must_contain.lower() in text.lower()):
            fallback = node
            if len(text) <= 550:
                return node
    return fallback


def detect_type(text: str, image_alt: str, type_choices: list[str]):
    alt = re.sub(r"\s+ID\s*\d+.*$", "", clean(image_alt), flags=re.I)
    if alt and alt.lower() not in {"image", "license"}:
        for choice in sorted(type_choices, key=len, reverse=True):
            if choice.lower() in alt.lower():
                return choice
    lower = text.lower()
    for choice in sorted(type_choices, key=len, reverse=True):
        if choice.lower() in lower:
            return choice
    return alt or "Liquor License"


def scrape_alcoholpermit(config: dict):
    url = config["alcoholpermit"]
    state = config["name"]
    if not robots_allows(url):
        return [], "robots.txt disallows automated retrieval"
    soup = get_soup(url)
    records, seen = [], set()
    county_re = re.compile(r"([A-Za-zÀ-ÿ .'-]+) County", re.I)
    for link in soup.find_all("a", href=True):
        label = clean(link.get_text(" ", strip=True)).lower()
        if label not in {"view details", "details"}:
            continue
        href = urljoin(url, link["href"])
        if href in seen:
            continue
        card = smallest_card(link, state)
        if not card:
            continue
        text = clean(card.get_text(" ", strip=True))
        if state.lower() not in text.lower():
            continue
        county_match = county_re.search(text)
        if not county_match:
            continue
        county = clean(county_match.group(1))
        image = card.find("img", alt=True)
        image_alt = clean(image.get("alt")) if image else ""
        type_name = detect_type(text, image_alt, config["types"])
        type_code = type_name.replace("Liquor License", "").replace("License", "").strip()
        price = money(text)
        private = "private listing" in text.lower() or "unlock the price" in text.lower()
        id_match = re.search(r"\bID\s*(\d+)\b", image_alt, re.I)
        title_el = card.find(["h2", "h3", "h4"])
        title = clean(title_el.get_text(" ", strip=True)) if title_el else f"{state} {type_name} – {county} County"
        records.append({
            "source": "AlcoholPermit.com",
            "sourceKind": "third-party",
            "county": county,
            "typeCode": type_code,
            "typeName": type_name,
            "price": None if private else price,
            "privatePrice": private,
            "listedDate": None,
            "sourceId": id_match.group(1) if id_match else None,
            "title": title,
            "sourceUrl": href,
        })
        seen.add(href)
    return records, None


def parse_market_title(text: str, state: str):
    escaped = re.escape(state)
    patterns = [
        rf"(?P<county>[A-Za-zÀ-ÿ .'-]+?)\s+{escaped}\s*[–—-]\s*(?P<type>.+?)\s+Liquor (?:License|Permit)",
        r"(?P<county>[A-Za-zÀ-ÿ .'-]+?)\s+County\s*[–—-]\s*(?P<type>.+?)\s+Liquor (?:License|Permit)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return clean(match.group("county")), clean(match.group("type"))
    return None, None


def scrape_marketplace(config: dict):
    url = config["marketplace"]
    state = config["name"]
    if not robots_allows(url):
        return [], "robots.txt disallows automated retrieval"
    soup = get_soup(url)
    records, seen = [], set()
    for link in soup.find_all("a", href=True):
        label = clean(link.get_text(" ", strip=True)).lower()
        if label not in {"view listing", "view license", "view"}:
            continue
        href = urljoin(url, link["href"])
        if href in seen:
            continue
        card = smallest_card(link, "Price")
        if not card:
            continue
        text = clean(card.get_text(" ", strip=True))
        county, type_name = parse_market_title(text, state)
        if not county or not type_name or len(county) > 50:
            continue
        date_match = re.search(r"Listed:\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4})", text)
        price_match = re.search(r"Price:\s*\$?\s*([0-9][0-9,]*(?:\.\d{1,2})?)", text, re.I)
        price = int(round(float(price_match.group(1).replace(",", "")))) if price_match else money(text)
        private = bool(re.search(r"price\s+(?:upon|on)\s+request", text, re.I))
        records.append({
            "source": "Liquor License Marketplace",
            "sourceKind": "third-party",
            "county": county.replace(" County", "").strip(),
            "typeCode": type_name.replace("Liquor License", "").replace("Liquor Permit", "").strip(),
            "typeName": type_name,
            "price": None if private else price,
            "privatePrice": private,
            "listedDate": date_match.group(1) if date_match else None,
            "sourceId": None,
            "title": f"{county} {state} – {type_name}",
            "sourceUrl": href,
        })
        seen.add(href)
    return records, None


def main():
    out_dir = Path("data")
    out_dir.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    any_rows = False
    for slug, config in STATES.items():
        combined, status = [], []
        for source_name, scraper, url_key in [
            ("AlcoholPermit.com", scrape_alcoholpermit, "alcoholpermit"),
            ("Liquor License Marketplace", scrape_marketplace, "marketplace"),
        ]:
            try:
                rows, note = scraper(config)
            except Exception as exc:
                rows, note = [], f"sync error: {exc}"
            combined.extend(rows)
            status.append({"source": source_name, "url": config[url_key], "count": len(rows), "note": note})
            print(f"{config['name']} / {source_name}: {len(rows)}" + (f" ({note})" if note else ""))
        # Do not overwrite a previously good state feed with nothing due to a transient source outage.
        path = out_dir / f"{slug}-market-inventory.json"
        if not combined:
            print(f"Warning: no {config['name']} records retrieved; retaining previous feed if present")
            continue
        any_rows = True
        combined.sort(key=lambda x: (
            x.get("county") or "",
            x.get("typeName") or "",
            x.get("price") if x.get("price") is not None else 10**12,
            x.get("source") or "",
        ))
        payload = {"state": config["name"], "updatedAt": now, "sources": status, "licenses": combined}
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote {len(combined)} {config['name']} records to {path}")
    if not any_rows:
        raise SystemExit("No state inventory was retrieved")


if __name__ == "__main__":
    main()
