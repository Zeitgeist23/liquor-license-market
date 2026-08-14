from __future__ import annotations

import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

SOURCE_URL = "https://cdtfa.ca.gov/taxes-and-fees/liquor-licenses-for-sale.htm"
OUT = Path("data/california-cdtfa.json")
UA = "LiquorLicenseMarket-CDTFA-Inventory/1.0 (+https://www.liquorlicensemarket.com/)"
PACIFIC = ZoneInfo("America/Los_Angeles")


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def extract_pdf(url: str) -> str:
    response = requests.get(url, timeout=35, headers={"User-Agent": UA})
    response.raise_for_status()
    reader = PdfReader(io.BytesIO(response.content))
    return clean(" ".join((page.extract_text() or "") for page in reader.pages))


def money_value(text: str):
    match = re.search(r"MINIMUM OPENING BID IS:\s*\$?\s*([0-9,]+(?:\.\d+)?)", text, re.I)
    return int(float(match.group(1).replace(",", ""))) if match else None


def type_details(text: str, fallback_code: str):
    match = re.search(r"TYPE OF LICENSE:\s*(\d+)\s*-\s*([A-Z][A-Z\- ]+?)(?=\s+The license|\s+The License|\s+The liquor|$)", text, re.I)
    if not match:
        return fallback_code, "California ABC License"
    return match.group(1), clean(match.group(2)).title()


def auction_time(text: str):
    match = re.search(r"\bon\s+[A-Z][a-z]+\s+\d{1,2},\s+\d{4},?\s+at\s+(\d{1,2}:\d{2})\s*(A\.?M\.?|P\.?M\.?)", text, re.I)
    if not match:
        return None
    suffix = re.sub(r"[^APMapm]", "", match.group(2)).upper()
    return f"{match.group(1)} {suffix}"


def auction_location(text: str):
    match = re.search(r"will sell the following described liquor license, at public sale, at\s+(.*?)\s+on\s+[A-Z][a-z]+\s+\d{1,2},\s+\d{4}", text, re.I)
    return clean(match.group(1)) if match else None


def iso_auction(date_text: str, time_text: str | None):
    if not time_text:
        return None
    naive = datetime.strptime(f"{date_text} {time_text}", "%B %d, %Y %I:%M %p")
    return naive.replace(tzinfo=PACIFIC).isoformat()


def main():
    response = requests.get(SOURCE_URL, timeout=35, headers={"User-Agent": UA})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    rows = []
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 3:
                continue
            county = clean(cells[0].get_text(" ", strip=True))
            link = cells[1].find("a", href=True)
            auction_date = clean(cells[2].get_text(" ", strip=True))
            if not county or not link or not re.match(r"\d+[-–]\d+", clean(link.get_text(" ", strip=True))):
                continue
            license_code = clean(link.get_text(" ", strip=True)).replace("–", "-")
            type_code, license_number = license_code.split("-", 1)
            notice_url = urljoin(SOURCE_URL, link["href"])
            item = {
                "county": county,
                "licenseNumber": license_number,
                "licenseCode": license_code,
                "typeCode": type_code,
                "typeName": "California ABC License",
                "auctionDate": auction_date,
                "auctionTime": None,
                "auctionDateTime": None,
                "minimumBid": None,
                "auctionLocation": None,
                "noticeUrl": notice_url,
            }
            try:
                pdf_text = extract_pdf(notice_url)
                item["typeCode"], item["typeName"] = type_details(pdf_text, type_code)
                item["minimumBid"] = money_value(pdf_text)
                item["auctionTime"] = auction_time(pdf_text)
                item["auctionLocation"] = auction_location(pdf_text)
                item["auctionDateTime"] = iso_auction(auction_date, item["auctionTime"])
            except Exception as exc:
                print(f"Warning: could not enrich {license_code}: {exc}")
            rows.append(item)

    if not rows:
        raise SystemExit("No CDTFA liquor-license auction rows were found; refusing to overwrite inventory.")

    def sort_key(item):
        if item.get("auctionDateTime"):
            return item["auctionDateTime"]
        try:
            return datetime.strptime(item["auctionDate"], "%B %d, %Y").isoformat()
        except Exception:
            return "9999"

    rows.sort(key=sort_key)
    payload = {
        "source": "California Department of Tax and Fee Administration",
        "sourceUrl": SOURCE_URL,
        "updatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "licenses": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} California CDTFA auction licenses to {OUT}")


if __name__ == "__main__":
    main()
