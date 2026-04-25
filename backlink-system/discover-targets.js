const BING_SEARCH_ENDPOINT = 'https://www.bing.com/search';

function sleep(ms){return new Promise(r=>setTimeout(r,ms));}

export function normalizeUrl(rawUrl){
  if(!rawUrl||typeof rawUrl!=='string')return null;
  try{
    const parsed=new URL(rawUrl);
    parsed.hash='';
    if((parsed.protocol==='http:'&&parsed.port==='80')||(parsed.protocol==='https:'&&parsed.port==='443'))parsed.port='';
    if(parsed.pathname!=='/'&&parsed.pathname.endsWith('/'))parsed.pathname=parsed.pathname.slice(0,-1);
    return parsed.toString();
  }catch{return null;}
}

export function isLikelyWpPost(rawUrl){
  try{
    const url=new URL(rawUrl);
    const path=url.pathname.toLowerCase();
    if(!path||path==='/')return false;
    if(path.includes('/wp-content/')||path.includes('/wp-admin/')||path.includes('/wp-json/'))return false;
    if(/\.(jpg|jpeg|png|gif|webp|svg|pdf|xml|txt|zip)$/i.test(path))return false;
    return true;
  }catch{return false;}
}

function decodeBingRedirect(rawHref){
  try{
    const parsed=new URL(rawHref);
    if(!parsed.hostname.endsWith('bing.com')||!parsed.pathname.startsWith('/ck/a'))return normalizeUrl(rawHref);
    const encoded=parsed.searchParams.get('u');
    if(!encoded)return null;
    const withoutPrefix=encoded.startsWith('a1')?encoded.slice(2):encoded;
    const b64=withoutPrefix.replace(/-/g,'+').replace(/_/g,'/');
    const decoded=Buffer.from(b64,'base64').toString('utf8');
    return normalizeUrl(decoded);
  }catch{return null;}
}

export function parseBing(html){
  if(!html||typeof html!=='string')return[];
  const urls=[];
  const re=/<a[^>]+href=["']([^"']+)["']/gi;
  let m;
  while((m=re.exec(html))!==null){
    const d=decodeBingRedirect(m[1]);
    if(d)urls.push(d);
  }
  return urls;
}

export async function bingSearch(fetchFn,query){
  const url=`${BING_SEARCH_ENDPOINT}?q=${encodeURIComponent(query)}`;
  const r=await fetchFn(url,{method:'GET',headers:{'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36','Accept':'text/html,application/xhtml+xml'}});
  if(!r.ok)return[];
  return parseBing(await r.text());
}

export async function discoverTargets(fetchFn,queries,{sleepBetween=3000}={}){
  if(typeof fetchFn!=='function')throw new Error('discoverTargets requires a fetchFn function');
  const list=Array.isArray(queries)?queries:[];
  const discovered=new Set();
  for(let i=0;i<list.length;i++){
    const query=String(list[i]??'').trim();
    if(!query)continue;
    const[primary,secondary]=await Promise.all([bingSearch(fetchFn,query),bingSearch(fetchFn,query+' site:wordpress.com')]);
    const before=primary.length+secondary.length;
    const combined=[...primary,...secondary].filter(isLikelyWpPost);
    console.log(`[discover-targets] "${query}": ${before} raw -> ${combined.length} WP posts`);
    for(const url of combined)discovered.add(url);
    if(i<list.length-1&&sleepBetween>0)await sleep(sleepBetween);
  }
  return Array.from(discovered);
}
