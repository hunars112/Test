const DDG_URL = 'https://html.duckduckgo.com/html/';
const BING_URL = 'https://www.bing.com/search';
const BLOCKED_HOSTS = new Set(['facebook.com','twitter.com','youtube.com','instagram.com','reddit.com','quora.com','pinterest.com','linkedin.com','gauthmath.com','amazon.com','ebay.com','etsy.com','yelp.com','tripadvisor.com','wikipedia.org','wikihow.com','wikimedia.org']);

function sleep(ms){return new Promise(r=>setTimeout(r,ms));}

function normalizeUrl(candidate){
  if(!candidate)return null;
  const cleaned=String(candidate).replace(/^\/+/,'').replace(/^uddg=/,'').trim();
  try{
    const decoded=decodeURIComponent(cleaned);
    const url=new URL(decoded.startsWith('http')?decoded:`https://${decoded}`);
    return `${url.origin}${url.pathname}`.replace(/\/$/,'');
  }catch{return null;}
}

function isLikelyWpPost(rawUrl){
  try{
    const u=new URL(rawUrl);
    const host=u.hostname.replace(/^www\./,'');
    const path=u.pathname;
    if(BLOCKED_HOSTS.has(host))return false;
    if(host.includes('wordpress.com'))return true;
    if(/\/blogs?\//.test(path))return true;
    if(/\/\d{4}\/\d{2}(\/\d{2})?\//.test(path))return true;
    const slug=path.split('/').filter(Boolean).pop()||'';
    if(slug.split('-').length>=4)return true;
    return false;
  }catch{return false;}
}

function parseDdg(html=''){
  const matches=[...html.matchAll(/<a[^>]*class="result__url"[^>]*>(.*?)<\/a>/gims)];
  return matches.map(m=>m[1].replace(/<[^>]*>/g,'').trim()).map(normalizeUrl).filter(Boolean);
}

function parseBing(html=''){
  const matches=[...html.matchAll(/<li class="b_algo"[\s\S]*?<a href="([^"]+)"/gim)];
  return matches.map(m=>normalizeUrl(m[1])).filter(Boolean);
}

async function ddgSearch(fetchFn,query){
  const url=`${DDG_URL}?q=${encodeURIComponent(query)}&b=&kl=us-en`;
  const response=await fetchFn(url,{method:'GET',headers:{'user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36','accept':'text/html,application/xhtml+xml','accept-language':'en-US,en;q=0.9','referer':'https://duckduckgo.com/'}});
  if(!response.ok)throw new Error(`DDG search failed (${response.status})`);
  return parseDdg(await response.text());
}

async function bingSearch(fetchFn,query){
  const url=`${BING_URL}?q=${encodeURIComponent(query)}`;
  const response=await fetchFn(url,{headers:{'user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}});
  if(!response.ok)throw new Error(`Bing search failed (${response.status})`);
  return parseBing(await response.text());
}

export async function discoverTargets(fetchFn,queries,{sleepBetween=3000}={}){
  if(typeof fetchFn!=='function')throw new Error('discoverTargets requires a fetchFn function');
  const list=Array.isArray(queries)?queries:[];
  const discovered=new Set();
  for(let i=0;i<list.length;i+=1){
    const query=String(list[i]??'').trim();
    if(!query)continue;
    let results=[];
    try{results=await ddgSearch(fetchFn,query);}catch(e){console.warn(`[discover-targets] DDG failed for "${query}":`,e.message);}
    if(results.length<3){
      try{const fb=await bingSearch(fetchFn,query);results=[...results,...fb];}catch(e){console.warn(`[discover-targets] Bing fallback failed for "${query}":`,e.message);}
    }
    const before=results.length;
    const filtered=results.filter(isLikelyWpPost);
    console.log(`[discover-targets] "${query}": ${before} raw -> ${filtered.length} WP posts`);
    for(const url of filtered)discovered.add(url);
    if(i<list.length-1&&sleepBetween>0)await sleep(sleepBetween);
  }
  return Array.from(discovered);
}
