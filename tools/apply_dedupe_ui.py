from __future__ import annotations

import re
import sys
from pathlib import Path

STATE_SLUGS = ["arizona", "new-mexico", "michigan", "ohio", "pennsylvania", "new-jersey"]

COMMON_HELPERS = r'''function sourceNames(item){return Array.isArray(item.sourceNames)&&item.sourceNames.length?item.sourceNames:[item.source].filter(Boolean)}
function sourceRows(item){return Array.isArray(item.sourceListings)&&item.sourceListings.length?item.sourceListings:[{source:item.source,sourceUrl:item.sourceUrl,sourceId:item.sourceId,listedDate:item.listedDate,price:item.price,privatePrice:item.privatePrice}]}
function sourceButtonLabel(name,multi){if(!multi)return 'VIEW ORIGINAL LISTING ↗';if(name==='AlcoholPermit.com')return 'ALCOHOLPERMIT ↗';if(name==='Liquor License Marketplace')return 'LICENSE MARKETPLACE ↗';return 'VIEW SOURCE ↗'}
function displayPrice(item){if(item.privatePrice&&item.price==null)return 'PRICE ON SOURCE';const lo=item.priceMin??item.price,hi=item.priceMax??item.price;if(lo!=null&&hi!=null&&lo!==hi)return money.format(lo)+' – '+money.format(hi);if(lo!=null)return money.format(lo);return 'CONTACT SOURCE'}
'''

STATE_FILTER = r'''function currentFiltered(){const q=$('search').value.trim().toLowerCase(),county=$('county').value,type=$('type').value,source=$('source').value;return sortRecords(records.filter(item=>{if(county&&item.county!==county)return false;if(type&&item.typeName!==type)return false;if(source&&!sourceNames(item).includes(source))return false;const hay=`${item.county} ${item.typeName} ${item.typeCode} ${item.sourceId||''} ${sourceNames(item).join(' ')} ${item.title||''}`.toLowerCase();return !q||hay.includes(q)}),$('sort').value)}'''

STATE_CARD = r'''function card(item){const names=sourceNames(item),rows=sourceRows(item),multi=rows.length>1,p=displayPrice(item);const actions=rows.map(x=>`<a class="btn btn-primary" href="${esc(x.sourceUrl)}" target="_blank" rel="noopener">${sourceButtonLabel(x.source,multi)}</a>`).join('');const status=multi?`${rows.length} SOURCE MATCH`:'Third-Party Listing';return `<article class="card"><div class="card-head"><span class="status">${status}</span><h2 class="county">${esc(item.county)} County</h2><div class="license">${esc(item.typeName)}${item.sourceId?' · Listing #'+esc(item.sourceId):''}</div><div class="source-name">${multi?'Sources':'Source'}: ${esc(names.join(' + '))}</div></div><div class="card-body"><div class="row"><div class="label">License Type</div><div class="value">${esc(item.typeName)}</div></div><div class="row"><div class="label">Asking Price</div><div class="value price">${p}</div></div>${item.listedDate?`<div class="row"><div class="label">Source Listed</div><div class="value">${esc(item.listedDate)}</div></div>`:''}<div class="actions">${actions}</div></div></article>`}'''

STATE_RENDER = r'''function render(){const all=currentFiltered(),shown=all.slice(0,visible),merged=Number(feedStats.duplicatesMerged||0);$('summary').innerHTML=`<span class="pill"><b>${all.length.toLocaleString()}</b> matching listings</span><span class="pill"><b>${records.length.toLocaleString()}</b> unique listings</span><span class="pill"><b>${merged.toLocaleString()}</b> duplicate records merged</span><span class="pill"><b>${new Set(records.map(x=>x.county)).size}</b> counties represented</span>`;$('inventory').innerHTML=shown.length?shown.map(card).join(''):'<div class="empty">No __STATE__ licenses match those filters.</div>';$('loadMore').hidden=shown.length>=all.length;if(!$('loadMore').hidden)$('loadMore').textContent=`LOAD MORE LISTINGS (${(all.length-shown.length).toLocaleString()} REMAINING)`}'''

CA_FILTER = r'''function currentFiltered(){
 const q=$('search').value.trim().toLowerCase(),county=$('county').value,type=$('type').value,source=$('source').value;
 const categorySet=new Set(categoryCodes[activeCategory]||[]);
 return sortRecords(records.filter(item=>{
  if(county&&item.county!==county)return false;
  if(type&&String(item.typeCode)!==type)return false;
  if(!type&&activeCategory&&categorySet.size&&!categorySet.has(String(item.typeCode)))return false;
  if(source&&!sourceNames(item).includes(source))return false;
  const hay=(String(item.county||'')+' '+String(item.typeCode||'')+' '+String(item.typeName||'')+' '+String(item.licenseNumber||'')+' '+sourceNames(item).join(' ')+' '+String(item.title||'')).toLowerCase();
  return !q||hay.includes(q)
 }),$('sort').value)
}'''

CA_CARD = r'''function card(item){const passed=auctionPassed(item);if(item.kind==='auction'){return `<article class="card ${passed?'passed':''}"><div class="card-head"><span class="status">${passed?'Auction Passed — Verify':'CDTFA Public Auction'}</span><h2 class="county">${esc(item.county)} County</h2><div class="license">Type ${esc(item.typeCode)} · License #${esc(item.licenseNumber)}</div><div class="source-name">California Department of Tax and Fee Administration</div></div><div class="card-body"><div class="row"><div class="label">License Type</div><div class="value">${esc(item.typeName)}</div></div><div class="row"><div class="label">Minimum Opening Bid</div><div class="value price">${item.price?money.format(item.price):'See Notice'}</div></div><div class="row"><div class="label">Auction</div><div class="value">${esc(item.auctionDate||'See Notice')}${item.auctionTime?'<br>'+esc(item.auctionTime)+' PT':''}</div></div>${item.auctionLocation?`<p class="location"><span class="label">Auction Location</span><br>${esc(item.auctionLocation)}</p>`:''}<div class="actions"><a class="btn btn-primary" href="${esc(item.sourceUrl)}" target="_blank" rel="noopener">OFFICIAL NOTICE ↗</a><a class="btn btn-secondary" href="${item.sourceListUrl}" target="_blank" rel="noopener">VIEW CDTFA AUCTIONS</a></div></div></article>`}const names=sourceNames(item),rows=sourceRows(item),multi=rows.length>1,price=displayPrice(item);const actions=rows.map(x=>`<a class="btn btn-primary" href="${esc(x.sourceUrl)}" target="_blank" rel="noopener">${sourceButtonLabel(x.source,multi)}</a>`).join('');return `<article class="card thirdparty"><div class="card-head"><span class="status">${multi?rows.length+' SOURCE MATCH':'Third-Party Listing'}</span><h2 class="county">${esc(item.county)} County</h2><div class="license">Type ${esc(item.typeCode)}${item.licenseNumber?' · Listing #'+esc(item.licenseNumber):''}</div><div class="source-name">${multi?'Sources':'Source'}: ${esc(names.join(' + '))}</div></div><div class="card-body"><div class="row"><div class="label">License Type</div><div class="value">${esc(item.typeName||('Type '+item.typeCode))}</div></div><div class="row"><div class="label">Asking Price</div><div class="value price">${price}</div></div>${item.listedDate?`<div class="row"><div class="label">Source Listed</div><div class="value">${esc(item.listedDate)}</div></div>`:''}<div class="actions">${actions}</div></div></article>`}'''

CA_RENDER = r'''function render(){
 const all=currentFiltered();
 const shown=all.slice(0,visible);
 const categoryPill=activeCategory?'<span class="pill"><b>'+esc(activeCategory)+'</b> selected category</span>':'';
 const merged=Number(marketStats.duplicatesMerged||0);
 $('summary').innerHTML=categoryPill+'<span class="pill"><b>'+all.length.toLocaleString()+'</b> matching listings</span><span class="pill"><b>'+records.length.toLocaleString()+'</b> unique listings</span><span class="pill"><b>'+merged.toLocaleString()+'</b> duplicate records merged</span><span class="pill"><b>'+new Set(records.map(x=>x.county)).size+'</b> counties represented</span>';
 $('inventory').innerHTML=shown.length?shown.map(card).join(''):'<div class="empty">No California licenses match those filters.</div>';
 $('loadMore').hidden=shown.length>=all.length;
 $('loadMore').textContent='LOAD MORE LISTINGS ('+(all.length-shown.length).toLocaleString()+' REMAINING)'
}'''


def replace_one(text, pattern, repl, label):
    updated, count = re.subn(pattern, repl, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"Could not patch {label}: matched {count} times")
    return updated


def patch_state(path: Path, state: str):
    text = path.read_text(encoding="utf-8")
    text = text.replace("let records=[],visible=60;", "let records=[],visible=60,feedStats={};")
    if COMMON_HELPERS not in text:
        text = text.replace("function sortRecords(items,mode)", COMMON_HELPERS + "function sortRecords(items,mode)", 1)
    text = replace_one(text, r"function currentFiltered\(\)\{.*?\}\nfunction card", STATE_FILTER + "\nfunction card", f"{state} filter")
    text = replace_one(text, r"function card\(item\)\{.*?\}\nfunction render", STATE_CARD + "\nfunction render", f"{state} card")
    render = STATE_RENDER.replace("__STATE__", state)
    text = replace_one(text, r"function render\(\)\{.*?\}\nfetch", render + "\nfetch", f"{state} render")
    text = text.replace("records=data.licenses||[];const meta=data.sources||[];", "records=data.licenses||[];feedStats=data||{};const meta=data.sources||[];", 1)
    text = text.replace("[...new Set(records.map(x=>x.source).filter(Boolean))].sort()", "[...new Set(records.flatMap(x=>sourceNames(x)).filter(Boolean))].sort()", 1)
    path.write_text(text, encoding="utf-8")


def patch_california(path: Path):
    text = path.read_text(encoding="utf-8")
    text = re.sub(
        r"let records=\[\];let sourceMeta=\[\];let visible=60;(?:let marketStats=\{\};)*",
        "let records=[];let sourceMeta=[];let visible=60;let marketStats={};",
        text,
        count=1,
    )
    if COMMON_HELPERS not in text:
        text = text.replace("function sortRecords(items,mode)", COMMON_HELPERS + "function sortRecords(items,mode)", 1)
    text = replace_one(text, r"function currentFiltered\(\)\{.*?\n\}\nfunction card", CA_FILTER + "\nfunction card", "California filter")
    text = replace_one(text, r"function card\(item\)\{.*?\}\nfunction render", CA_CARD + "\nfunction render", "California card")
    text = replace_one(text, r"function render\(\)\{.*?\n\}\nfunction populate", CA_RENDER + "\nfunction populate", "California render")
    text = text.replace("const sources=[...new Set(records.map(x=>x.source).filter(Boolean))].sort();", "const sources=[...new Set(records.flatMap(x=>sourceNames(x)).filter(Boolean))].sort();", 1)
    text = re.sub(
        r"records=\[\.\.\.govRows,\.\.\.marketRows\];sourceMeta=market\.sources\|\|\[\];(?:marketStats=market\|\|\{\};)*",
        "records=[...govRows,...marketRows];sourceMeta=market.sources||[];marketStats=market||{};",
        text,
        count=1,
    )
    path.write_text(text, encoding="utf-8")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in {"states", "all"}:
        names = {"arizona":"Arizona","new-mexico":"New Mexico","michigan":"Michigan","ohio":"Ohio","pennsylvania":"Pennsylvania","new-jersey":"New Jersey"}
        for slug in STATE_SLUGS:
            path = Path(slug) / "licenses-for-sale" / "index.html"
            patch_state(path, names[slug])
            print(f"Applied dedupe UI to {path}")
    if mode in {"california", "all"}:
        path = Path("california/licenses-for-sale/index.html")
        patch_california(path)
        print(f"Applied dedupe UI to {path}")


if __name__ == "__main__":
    main()
