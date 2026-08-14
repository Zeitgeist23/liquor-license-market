from __future__ import annotations

import re
from pathlib import Path

PAGE = Path("california/licenses-for-sale/index.html")

FASTLOAD_BLOCK = r'''function setSourceCounts(meta){
 sourceMeta=meta||[];
 $('alcoholCount').textContent=(sourceMeta.find(x=>x.source==='AlcoholPermit.com')?.count||0).toLocaleString();
 $('marketplaceCount').textContent=(sourceMeta.find(x=>x.source==='Liquor License Marketplace')?.count||0).toLocaleString()
}
function populateOnce(){
 if(filtersPopulated)return;
 filtersPopulated=true;
 populate()
}
function ensureFullMarket(){
 if(fullMarketReady)return Promise.resolve();
 if(fullLoadPromise)return fullLoadPromise;
 fullLoadPromise=fetch(MARKET_URL).then(r=>{if(!r.ok)throw new Error('full market feed unavailable');return r.json()}).then(market=>{
  const marketRows=(market.licenses||[]).map(normalizeMarket);
  records=[...govRowsCache,...marketRows];
  marketStats=market||marketStats;
  setSourceCounts(market.sources||sourceMeta);
  fullMarketReady=true;
  populateOnce();
  render();
 }).catch(err=>{
  console.warn('California full inventory background load failed',err);
  fullLoadPromise=null;
 });
 return fullLoadPromise
}
Promise.all([
 fetch(CDTFA_URL).then(r=>r.ok?r.json():{licenses:[]}),
 fetch(BOOTSTRAP_URL).then(r=>{if(!r.ok)throw new Error('bootstrap feed unavailable');return r.json()})
]).then(([gov,boot])=>{
 govRowsCache=(gov.licenses||[]).map(normalizeAuction);
 const marketRows=(boot.licenses||[]).map(normalizeMarket);
 records=[...govRowsCache,...marketRows];
 marketStats=boot||{};
 setSourceCounts(boot.sources||[]);
 $('cdtfaCount').textContent=govRowsCache.length.toLocaleString();
 const dates=[gov.updatedAt,boot.updatedAt].filter(Boolean).map(x=>new Date(x)).sort((a,b)=>b-a);
 if(dates.length)$('updated').textContent='Inventory feeds last synchronized: '+dates[0].toLocaleString('en-US',{dateStyle:'medium',timeStyle:'short'});
 render();
 $('loadMore').hidden=false;
 $('loadMore').textContent='LOAD MORE LISTINGS';
 if('requestIdleCallback' in window)requestIdleCallback(()=>ensureFullMarket(),{timeout:1200});else setTimeout(()=>ensureFullMarket(),100)
}).catch(()=>{
 // Fallback to the full feed if the small bootstrap file is unavailable.
 Promise.all([
  fetch(CDTFA_URL).then(r=>r.ok?r.json():{licenses:[]}),
  fetch(MARKET_URL).then(r=>r.ok?r.json():{licenses:[],sources:[]})
 ]).then(([gov,market])=>{
  govRowsCache=(gov.licenses||[]).map(normalizeAuction);
  records=[...govRowsCache,...((market.licenses||[]).map(normalizeMarket))];
  marketStats=market||{};
  fullMarketReady=true;
  setSourceCounts(market.sources||[]);
  $('cdtfaCount').textContent=govRowsCache.length.toLocaleString();
  populateOnce();render()
 }).catch(()=>{$('inventory').innerHTML='<div class="empty">The California inventory feeds are temporarily unavailable. Please use the original source websites.</div>'})
});
'''

LISTENER_BLOCK = r'''$('type').addEventListener('change',()=>{activeCategory=''});
['search','county','type','source','sort'].forEach(id=>$(id).addEventListener(id==='search'?'input':'change',()=>{
 visible=60;
 if(fullMarketReady)render();else ensureFullMarket().then(()=>render())
}));
$('loadMore').addEventListener('click',()=>{
 if(fullMarketReady){visible+=60;render();return}
 ensureFullMarket().then(()=>{visible+=60;render()})
});
'''


def main():
    text = PAGE.read_text(encoding="utf-8")

    if "const BOOTSTRAP_URL=" not in text:
        text = text.replace(
            "const MARKET_URL='/data/california-market-inventory.json';",
            "const MARKET_URL='/data/california-market-inventory.json';\nconst BOOTSTRAP_URL='/data/california-market-bootstrap.json';",
            1,
        )

    text = re.sub(
        r"let records=\[\];let sourceMeta=\[\];let visible=60;[^\n]*",
        "let records=[];let sourceMeta=[];let visible=60;let marketStats={};let govRowsCache=[];let fullMarketReady=false;let fullLoadPromise=null;let filtersPopulated=false;",
        text,
        count=1,
    )

    start = text.find("Promise.all([fetch(CDTFA_URL")
    if start < 0:
        start = text.find("function setSourceCounts(meta)")
    end = text.find("$('type').addEventListener", start)
    if start < 0 or end < 0:
        raise SystemExit("Could not locate California inventory loading block")
    text = text[:start] + FASTLOAD_BLOCK + text[end:]

    listener_start = text.find("$('type').addEventListener", text.find(FASTLOAD_BLOCK[:30]))
    listener_end = text.find("</script>", listener_start)
    if listener_start < 0 or listener_end < 0:
        raise SystemExit("Could not locate California inventory listener block")
    text = text[:listener_start] + LISTENER_BLOCK + text[listener_end:]

    # Default browser/CDN caching is desirable for static inventory assets.
    text = text.replace("fetch(CDTFA_URL,{cache:'no-store'})", "fetch(CDTFA_URL)")
    text = text.replace("fetch(MARKET_URL,{cache:'no-store'})", "fetch(MARKET_URL)")

    PAGE.write_text(text, encoding="utf-8")
    print(f"Applied staged California inventory loading to {PAGE}")


if __name__ == "__main__":
    main()
