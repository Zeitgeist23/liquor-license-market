from __future__ import annotations

import re
from collections import defaultdict
from copy import deepcopy
from datetime import datetime


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def canonical_county(value):
    text = _clean(value).lower()
    text = re.sub(r"\bcounty\b", "", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def canonical_type(value):
    text = _clean(value).lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = text.replace("dispensers", "dispenser")
    text = text.replace("inter-local", "inter local").replace("interlocal", "inter local")
    if "inter local dispenser" in text or re.search(r"\bild\b", text):
        return "interlocaldispenser"
    text = re.sub(r"\bliquor\b", " ", text)
    text = re.sub(r"\blicen[cs]e\b", " ", text)
    text = re.sub(r"\bpermit\b", " ", text)
    text = re.sub(r"\btype\b", " ", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def _date_score(value):
    if not value:
        return 0
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return int(datetime.strptime(value, fmt).timestamp())
        except Exception:
            pass
    return 0


def _source_snapshot(item):
    return {
        "source": item.get("source"),
        "sourceUrl": item.get("sourceUrl"),
        "sourceId": item.get("sourceId"),
        "listedDate": item.get("listedDate"),
        "price": item.get("price"),
        "privatePrice": bool(item.get("privatePrice")),
    }


def _merge_pair(a, b, reason):
    # Prefer the record with a dated listing as the display record; otherwise keep
    # AlcoholPermit first because it normally exposes a stable source listing ID.
    candidates = [a, b]
    primary = max(
        candidates,
        key=lambda x: (
            _date_score(x.get("listedDate")),
            1 if x.get("sourceId") else 0,
            1 if x.get("source") == "AlcoholPermit.com" else 0,
        ),
    )
    merged = deepcopy(primary)
    snapshots = []
    seen_urls = set()
    for item in candidates:
        url = item.get("sourceUrl") or ""
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        snapshots.append(_source_snapshot(item))
    known_prices = sorted({int(x["price"]) for x in snapshots if x.get("price") is not None})
    merged["sourceListings"] = snapshots
    merged["sourceNames"] = sorted({x.get("source") for x in snapshots if x.get("source")})
    merged["duplicateCount"] = max(0, len(snapshots) - 1)
    merged["dedupeReason"] = reason
    if known_prices:
        merged["priceMin"] = known_prices[0]
        merged["priceMax"] = known_prices[-1]
        # Keep sorting stable and conservative when two sources have slightly different prices.
        merged["price"] = known_prices[0]
        merged["privatePrice"] = False
    return merged


def dedupe_cross_source(records):
    """Conservatively collapse probable cross-source duplicates.

    Matching is restricted to the same normalized county and license type.
    We merge when an exact public price appears exactly once on each source.
    If only one unmatched record remains on each source in a county/type bucket,
    we also merge a small price discrepancy (<= 3% or $5,000) to account for
    a stale asking price on one source. Ambiguous repeated same-price records are
    intentionally left separate to avoid collapsing distinct licenses.
    """
    raw = [deepcopy(x) for x in records]
    groups = defaultdict(list)
    for idx, item in enumerate(raw):
        key = (canonical_county(item.get("county")), canonical_type(item.get("typeName") or item.get("typeCode")))
        groups[key].append(idx)

    consumed = set()
    merged_records = []

    for _key, indexes in groups.items():
        by_source = defaultdict(list)
        for idx in indexes:
            by_source[raw[idx].get("source") or "Unknown"].append(idx)
        sources = sorted(by_source)
        if len(sources) < 2:
            continue

        # Current feeds have two private-market sources. Pair every source combination
        # conservatively so the routine remains safe if another feed is added later.
        for i, source_a in enumerate(sources):
            for source_b in sources[i + 1:]:
                a_ids = [x for x in by_source[source_a] if x not in consumed]
                b_ids = [x for x in by_source[source_b] if x not in consumed]
                if not a_ids or not b_ids:
                    continue

                a_prices = defaultdict(list)
                b_prices = defaultdict(list)
                for idx in a_ids:
                    if raw[idx].get("price") is not None:
                        a_prices[int(raw[idx]["price"])].append(idx)
                for idx in b_ids:
                    if raw[idx].get("price") is not None:
                        b_prices[int(raw[idx]["price"])].append(idx)

                # Exact-price matches are accepted only when unique on both sources.
                for price in sorted(set(a_prices) & set(b_prices)):
                    if len(a_prices[price]) != 1 or len(b_prices[price]) != 1:
                        continue
                    a_idx, b_idx = a_prices[price][0], b_prices[price][0]
                    if a_idx in consumed or b_idx in consumed:
                        continue
                    merged_records.append(_merge_pair(raw[a_idx], raw[b_idx], "county+type+unique-exact-price"))
                    consumed.update((a_idx, b_idx))

                # Small price difference: only when exactly one candidate remains on each source.
                a_left = [x for x in a_ids if x not in consumed]
                b_left = [x for x in b_ids if x not in consumed]
                if len(a_left) == 1 and len(b_left) == 1:
                    a_idx, b_idx = a_left[0], b_left[0]
                    pa, pb = raw[a_idx].get("price"), raw[b_idx].get("price")
                    if pa is not None and pb is not None:
                        pa, pb = int(pa), int(pb)
                        tolerance = max(5000, int(max(pa, pb) * 0.03))
                        if abs(pa - pb) <= tolerance:
                            merged_records.append(_merge_pair(raw[a_idx], raw[b_idx], "county+type+one-to-one-near-price"))
                            consumed.update((a_idx, b_idx))

    unique = [item for idx, item in enumerate(raw) if idx not in consumed]
    # Preserve provenance on non-merged rows too, so the UI can use one format.
    for item in unique:
        item.setdefault("sourceListings", [_source_snapshot(item)])
        item.setdefault("sourceNames", [item.get("source")] if item.get("source") else [])
        item.setdefault("duplicateCount", 0)
        if item.get("price") is not None:
            item.setdefault("priceMin", int(item["price"]))
            item.setdefault("priceMax", int(item["price"]))
    unique.extend(merged_records)
    unique.sort(key=lambda x: (
        _clean(x.get("county")).lower(),
        canonical_type(x.get("typeName") or x.get("typeCode")),
        x.get("price") if x.get("price") is not None else 10**15,
        _clean(x.get("source")).lower(),
    ))
    stats = {
        "rawRecordCount": len(raw),
        "uniqueCount": len(unique),
        "duplicatesMerged": len(raw) - len(unique),
        "mergedCards": sum(1 for x in unique if x.get("duplicateCount", 0) > 0),
    }
    return unique, stats
