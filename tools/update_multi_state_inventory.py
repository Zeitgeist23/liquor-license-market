from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

UA = "LiquorLicenseMarket-Inventory/1.0 (+https://www.liquorlicensemarket.com/)"

STATES = {
    "arizona": {"name":"Arizona","alcoholpermit":"https://alcoholpermit.com/liquor-licenses/arizona/","marketplace":"https://liquorlicensemarketplace.com/arizona/","types":["Series 6","Series 7","Series 9"]},
    "new-mexico": {"name":"New Mexico","alcoholpermit":"https://alcoholpermit.com/liquor-licenses/new-mexico/","marketplace":"https://liquorlicensemarketplace.com/new-mexico/","types":["Inter-Local Dispenser License","Inter Local Dispenser (ILD)","Dispenser License","Dispensers License"]},
    "michigan": {"name":"Michigan","alcoholpermit":"https://alcoholpermit.com/liquor-licenses/michigan/","marketplace":"https://liquorlicensemarketplace.com/michigan/","types":["Class C Resort","Class C","Tavern","SDD"]},
    "ohio": {"name":"Ohio","alcoholpermit":"https://alcoholpermit.com/liquor-licenses/ohio/","marketplace":"https://liquorlicensemarketplace.com/ohio/","types":["C1 + C2","D-1","D-2","D-3","D-5"]},
    "pennsylvania": {"name":"Pennsylvania","alcoholpermit":"https://alcoholpermit.com/liquor-licenses/pennsylvania/","marketplace":"https://liquorlicensemarketplace.com/pennsylvania/","types":["Type R","Type E","Type D"]},
    "new-jersey": {"name":"New Jersey","alcoholpermit":"https://alcoholpermit.com/liquor-licenses/new-jersey/","marketplace":"https://liquorlicensemarketplace.com/new-jersey/","types":["Type 32","Type 33","Type 44"]},
}

def clean(v): return re.sub(r"\s+"," ",v or "").strip()

def robots_allows(url):
    p=urlparse(url); robots=f"{p.scheme}://{p.netloc}/robots.txt"
    try:
        r=requests.get(robots,timeout=10,headers={"User-Agent":UA})
        if r.status_code>=400:return True
        rp=robotparser.RobotFileParser(); rp.set_url(robots); rp.parse(r.text.splitlines())
        return rp.can_fetch(UA,url) and rp.can_fetch("*",url)
    except Exception:return True

def get_soup(url):
    r=requests.get(url,timeout=20,headers={"User-Agent":UA}); r.raise_for_status(); return BeautifulSoup(r.text,"html.parser")

def money(text):
    m=re.search(r"\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)",text)
    return int(round(float(m.group(1).replace(",","")))) if m else None

def smallest_card(link,must=None):
    node=link; fallback=None
    for _ in range(10):
        node=getattr(node,"parent",None)
        if node is None:break
        text=clean(node.get_text(" ",strip=True))
        if 30<=len(text)<=1200 and (not must or must.lower() in text.lower()):
            fallback=node
            if len(text)<=550:return node
    return fallback

def detect_type(text,image_alt,choices):
    alt=re.sub(r"\s+ID\s*\d+.*$","",clean(image_alt),flags=re.I)
    for c in sorted(choices,key=len,reverse=True):
        if c.lower() in alt.lower():return c
    lower=text.lower()
    for c in sorted(choices,key=len,reverse=True):
        if c.lower() in lower:return c
    return alt or "Liquor License"

def scrape_alcoholpermit(cfg):
    url=cfg["alcoholpermit"]; state=cfg["name"]
    if not robots_allows(url):return [],"robots.txt disallows automated retrieval"
    soup=get_soup(url); rows=[]; seen=set(); county_re=re.compile(r"([A-Za-zÀ-ÿ .'-]+) County",re.I)
    for link in soup.find_all("a",href=True):
        if clean(link.get_text(" ",strip=True)).lower() not in {"view details","details"}:continue
        href=urljoin(url,link["href"])
        if href in seen:continue
        card=smallest_card(link,state)
        if not card:continue
        text=clean(card.get_text(" ",strip=True))
        if state.lower() not in text.lower():continue
        cm=county_re.search(text)
        if not cm:continue
        county=clean(cm.group(1)); image=card.find("img",alt=True); image_alt=clean(image.get("alt")) if image else ""
        type_name=detect_type(text,image_alt,cfg["types"]); price=money(text); private="private listing" in text.lower() or "unlock the price" in text.lower(); im=re.search(r"\bID\s*(\d+)\b",image_alt,re.I)
        rows.append({"source":"AlcoholPermit.com","sourceKind":"third-party","county":county,"typeCode":type_name.replace("Liquor License","").replace("License","").strip(),"typeName":type_name,"price":None if private else price,"privatePrice":private,"listedDate":None,"sourceId":im.group(1) if im else None,"title":f"{state} {type_name} – {county} County","sourceUrl":href}); seen.add(href)
    return rows,None

def parse_market_title(text,state):
    esc=re.escape(state)
    for pat in [rf"(?P<county>[A-Za-zÀ-ÿ .'-]+?)\s+{esc}\s*[–—-]\s*(?P<type>.+?)\s+Liquor (?:License|Permit)",r"(?P<county>[A-Za-zÀ-ÿ .'-]+?)\s+County\s*[–—-]\s*(?P<type>.+?)\s+Liquor (?:License|Permit)"]:
        m=re.search(pat,text,re.I)
        if m:return clean(m.group("county")),clean(m.group("type"))
    return None,None

def scrape_marketplace(cfg):
    url=cfg["marketplace"]; state=cfg["name"]
    if not robots_allows(url):return [],"robots.txt disallows automated retrieval"
    soup=get_soup(url); rows=[]; seen=set()
    for link in soup.find_all("a",href=True):
        if clean(link.get_text(" ",strip=True)).lower() not in {"view listing","view license","view"}:continue
        href=urljoin(url,link["href"])
        if href in seen:continue
        card=smallest_card(link,"Price")
        if not card:continue
        text=clean(card.get_text(" ",strip=True)); county,type_name=parse_market_title(text,state)
        if not county or not type_name or len(county)>50:continue
        dm=re.search(r"Listed:\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",text); pm=re.search(r"Price:\s*\$?\s*([0-9][0-9,]*(?:\.\d{1,2})?)",text,re.I); private=bool(re.search(r"price\s+(?:upon|on)\s+request",text,re.I)); price=int(round(float(pm.group(1).replace(",","")))) if pm else money(text)
        rows.append({"source":"Liquor License Marketplace","sourceKind":"third-party","county":county.replace(" County","").strip(),"typeCode":type_name.replace("Liquor License","").replace("Liquor Permit","").strip(),"typeName":type_name,"price":None if private else price,"privatePrice":private,"listedDate":dm.group(1) if dm else None,"sourceId":None,"title":f"{county} {state} – {type_name}","sourceUrl":href}); seen.add(href)
    return rows,None

def process_state(slug,cfg,now):
    combined=[]; status=[]
    for source,scraper,key in [("AlcoholPermit.com",scrape_alcoholpermit,"alcoholpermit"),("Liquor License Marketplace",scrape_marketplace,"marketplace")]:
        try: rows,note=scraper(cfg)
        except Exception as exc: rows,note=[],f"sync error: {exc}"
        combined.extend(rows); status.append({"source":source,"url":cfg[key],"count":len(rows),"note":note}); print(f"{cfg['name']} / {source}: {len(rows)}"+(f" ({note})" if note else ""),flush=True)
    if not combined:return slug,cfg,None
    combined.sort(key=lambda x:(x.get("county") or "",x.get("typeName") or "",x.get("price") if x.get("price") is not None else 10**12,x.get("source") or ""))
    return slug,cfg,{"state":cfg["name"],"updatedAt":now,"sources":status,"licenses":combined}

def main():
    out=Path("data"); out.mkdir(exist_ok=True); now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"); written=0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures=[pool.submit(process_state,slug,cfg,now) for slug,cfg in STATES.items()]
        for fut in as_completed(futures):
            slug,cfg,payload=fut.result(); path=out/f"{slug}-market-inventory.json"
            if not payload:
                print(f"Warning: no {cfg['name']} records retrieved; retaining previous feed if present",flush=True); continue
            path.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); written+=1; print(f"Wrote {len(payload['licenses'])} {cfg['name']} records to {path}",flush=True)
    if not written:raise SystemExit("No state inventory was retrieved")

if __name__=="__main__":main()
