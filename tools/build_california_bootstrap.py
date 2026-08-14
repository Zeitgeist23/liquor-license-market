from __future__ import annotations

import json
from pathlib import Path

SOURCE = Path("data/california-market-inventory.json")
OUT = Path("data/california-market-bootstrap.json")
BOOTSTRAP_LIMIT = 60


def main():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows = data.get("licenses") or []
    sources = data.get("sources") or []

    counties = sorted({str(x.get("county")) for x in rows if x.get("county")})
    types = sorted(
        {str(x.get("typeCode")) for x in rows if x.get("typeCode") is not None},
        key=lambda v: (0, int(v)) if v.isdigit() else (1, v.lower()),
    )
    source_names = sorted({
        name
        for row in rows
        for name in ((row.get("sourceNames") or [row.get("source")]))
        if name
    })

    payload = {
        "updatedAt": data.get("updatedAt"),
        "sources": sources,
        "rawRecordCount": data.get("rawRecordCount", len(rows)),
        "uniqueCount": data.get("uniqueCount", len(rows)),
        "duplicatesMerged": data.get("duplicatesMerged", 0),
        "mergedCards": data.get("mergedCards", 0),
        "bootstrapCount": min(BOOTSTRAP_LIMIT, len(rows)),
        "facets": {
            "counties": counties,
            "types": types,
            "sources": source_names,
        },
        "licenses": rows[:BOOTSTRAP_LIMIT],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['licenses'])} bootstrap records to {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
