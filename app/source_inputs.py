"""Bounded public-source acquisition and deterministic fact extraction.

These readers never execute remote JavaScript, follow unvalidated redirects,
call expensive prediction endpoints, or send observer coordinates to sources.
"""
from __future__ import annotations
import asyncio, hashlib, html, json, math, re, time, unicodedata
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin
from urllib.robotparser import RobotFileParser
import httpx

AGENT = 'Downrange/0.3 (+https://github.com/spikked27/downrange)'
PUBLIC_HOSTS = {'nextspaceflight.com', 'jellyfish.johnkrausphotos.com',
                'raw.githubusercontent.com', 'api.flightclub.io',
                'www.spacex.com', 'www.nasa.gov', 'science.nasa.gov',
                'www.ulalaunch.com', 'www.rocketlabusa.com', 'rocketlabcorp.com',
                'www.blueorigin.com', 'www.esa.int', 'www.arianespace.com',
                'www.isro.gov.in', 'global.jaxa.jp', 'www.jaxa.jp'}
DIRECTIONS = {'north':0, 'northnortheast':22.5, 'northeast':45, 'eastnortheast':67.5,
              'east':90, 'eastsoutheast':112.5, 'southeast':135, 'southsoutheast':157.5,
              'south':180, 'southsouthwest':202.5, 'southwest':225, 'westsouthwest':247.5,
              'west':270, 'westnorthwest':292.5, 'northwest':315, 'northnorthwest':337.5}

class SourceUnavailable(ValueError): pass

def public_url(url: str) -> str:
    p=urlsplit(url)
    if p.scheme!='https' or p.hostname not in PUBLIC_HOSTS or p.port not in (None,443) or p.username or p.password or p.fragment:
        raise SourceUnavailable('Source URL is not an approved public HTTPS endpoint')
    if p.hostname=='raw.githubusercontent.com' and not p.path.startswith(('/shahar603/Telemetry-Data/', '/spikked27/downrange/')):
        raise SourceUnavailable('Unapproved data repository')
    return url

class CachedReader:
    def __init__(self, store):
        self.store=store
        self.lock=asyncio.Lock()
    def key(self,url): return 'source-http:'+hashlib.sha256(url.encode()).hexdigest()
    async def get(self,url,ttl=3600,*,headers=None,robots=True,max_bytes=4_000_000):
        """No stale body is silently substituted for a failed source response."""
        public_url(url)
        if headers and urlsplit(url).hostname!='api.flightclub.io':
            raise SourceUnavailable('Credentials allowed only for the configured simulation API')
        key=self.key(url); now=time.time(); old=self.store.meta(key,{})
        if now-old.get('fetched',0)<ttl and 'body' in old: return old['body']
        if now<old.get('next_attempt',0): raise SourceUnavailable(old.get('error','Source backoff'))
        if robots:
            robot_url=urljoin(url,'/robots.txt')
            text=await self.get(robot_url,86400,robots=False,max_bytes=256_000)
            rp=RobotFileParser(); rp.parse(text.splitlines())
            if not rp.can_fetch(AGENT,url): raise SourceUnavailable('Source robots policy disallows this path')
            delay=rp.crawl_delay(AGENT) or rp.crawl_delay('*') or 0
        else: delay=0
        host=urlsplit(url).hostname
        async with self.lock:
            old=self.store.meta(key,{})
            now=time.time()
            if now-old.get('fetched',0)<ttl and 'body' in old:return old['body']
            policy=self.store.meta('source-host:'+host,{})
            if now<policy.get('blocked_until',0): raise SourceUnavailable('Source host is rate-limited')
            wait=max(1.0,delay)-(now-policy.get('last_request',0))
            if wait>120:raise SourceUnavailable('Crawl delay exceeds acquisition cycle; retry later')
            if wait>0:await asyncio.sleep(wait)
            self.store.set_meta('source-host:'+host,{**policy,'last_request':time.time()})
            self.store.set_meta(key,{**old,'next_attempt':time.time()+300})
            try:
                # Redirects are not followed: discovery must supply the canonical host/path.
                async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:
                    async with client.stream('GET',url,headers={'User-Agent':AGENT,**(headers or {})}) as response:
                        if response.status_code==429:
                            value=response.headers.get('retry-after','')
                            wait=min(86400,max(600,int(value))) if value.isdigit() else 3600
                            self.store.set_meta('source-host:'+host,{'last_request':time.time(),'blocked_until':time.time()+wait})
                        if response.status_code==404 and url.endswith('/robots.txt'): body=''
                        else:
                            response.raise_for_status(); chunks=[]; size=0
                            async for chunk in response.aiter_bytes():
                                size+=len(chunk)
                                if size>max_bytes:raise SourceUnavailable('Source response exceeds size limit')
                                chunks.append(chunk)
                            body=b''.join(chunks).decode('utf-8')
                self.store.set_meta(key,{'body':body,'fetched':time.time(),'next_attempt':0,'error':None})
                return body
            except Exception as exc:
                # Do not persist a URL from an exception, response body, or credential.
                msg='Source unavailable: '+type(exc).__name__
                self.store.set_meta(key,{**old,'error':msg,'next_attempt':time.time()+600})
                raise SourceUnavailable(msg) from None

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text=[]; self.scripts=[]; self.links=[]; self.title=[]
        self._script=None;self._a=None;self._h1=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='script':self._script=[]
        if tag=='h1':self._h1=True
        if tag=='a':self._a={'url':a.get('href',''),'text':[],'vehicle':''}
        if tag=='img' and self._a is not None:self._a['vehicle']=a.get('alt','')
    def handle_endtag(self,tag):
        if tag=='script' and self._script is not None:
            self.scripts.append(''.join(self._script));self._script=None
        if tag=='h1':self._h1=False
        if tag=='a' and self._a is not None:
            self._a['text']=' '.join(self._a['text']);self.links.append(self._a);self._a=None
    def handle_data(self,data):
        if self._script is not None:self._script.append(data);return
        if data.strip():self.text.append(data.strip())
        if self._h1:self.title.append(data)
        if self._a is not None:self._a['text'].append(data)

def read_page(body):
    p=Page();p.feed(body);return p

def mission_name(value):
    value=value.split('|',1)[-1]
    value=re.sub(r'\([^)]*\)','',value)
    value=unicodedata.normalize('NFKD',value).casefold()
    value=re.sub(r'\b(group|mission|dedicated|rideshare)\b','',value)
    return re.sub(r'[^a-z0-9]','',value)

def mission_matches(launch, name):
    target=mission_name(launch.get('mission_name') or launch['name'])
    return len(target)>=4 and target==mission_name(name)

def decoded_scripts(page):
    """Decode strings in Next.js payloads as JSON strings, not JavaScript code."""
    decoder=json.JSONDecoder()
    for script in page.scripts:
        yield script
        for m in re.finditer(r'self\.__next_f\.push\(\[\d+,\s*',script):
            try:
                text,_=decoder.raw_decode(script[m.end():])
                if isinstance(text,str):yield text
            except (ValueError,TypeError):pass

def nextspaceflight_index(body):
    page=read_page(body);out=[]
    # The h3 is the mission name; don't match countdown labels from the whole anchor.
    for match in re.finditer(r'<a\b[^>]*href=["\'](/launches/details/\d+/?)["\'][^>]*>(.*?)</a>',body,re.S):
        h=re.search(r'<h3\b[^>]*>(.*?)</h3>',match[2],re.S)
        if h:
            name=' '.join(read_page(h[1]).text).strip()
            out.append({'name':name,'url':urljoin('https://nextspaceflight.com',match[1])})
    return out

def numeric(value,lo,hi):
    if value is None or isinstance(value,bool):return None
    try:
        v=float(value)
        return v if math.isfinite(v) and lo<=v<=hi else None
    except (ValueError,TypeError):return None

def nextspaceflight_facts(body,launch,url):
    from .geometry import utc
    p=read_page(body)
    if not mission_matches(launch,''.join(p.title)):raise SourceUnavailable('Mission title does not match')
    visible=' '.join(p.text); heading=None; net=None
    # Visible, labeled launch direction is safer than unrelated numbers in the page.
    m=re.search(r'\bLaunching\s+([A-Za-z-]+)',visible)
    if m:heading=DIRECTIONS.get(re.sub('[^a-z]','',m[1].lower()))
    for text in decoded_scripts(p):
        # Restrict to mission data block with its own name, time, and heading.
        for m in re.finditer(r'"name"\s*:\s*"([^"\\]+)"',text):
            if not mission_matches(launch,m[1]):continue
            block=text[m.end():m.end()+3500]
            n=re.search(r'"net"\s*:\s*"([^"\\]+)"',block)
            h=re.search(r'"heading"\s*:\s*(null|-?[0-9.]+)',block)
            if n:
                dt=utc(n[1]); net=n[1]
                if abs((dt-utc(launch['net'])).total_seconds())>36*3600:
                    raise SourceUnavailable('Mission date does not match this launch')
                if h and h[1]!='null':heading=numeric(h[1],0,360)
                break
        if net:break
    if net is None:raise SourceUnavailable('No dated mission identity in page')
    if heading is None:raise SourceUnavailable('Source has no launch direction')
    links=[urljoin(url,a['url']) for a in p.links if a['url'].startswith('https://')]
    return {'source':'Next Spaceflight','url':url,'heading_deg':heading%360,'spread_deg':12,
            'kind':'published-direction','source_net':net,'links':list(dict.fromkeys(links))[:30],
            'note':'Published general departure direction; not a guidance solution or full trajectory.'}

def jellyfish_facts(data,launch):
    from .geometry import utc,distance_km
    rows=[r for r in data.get('upcoming',[]) if not r.get('manual_test') and mission_matches(launch,r.get('mission',''))]
    if len(rows)!=1:return None
    r=rows[0];heading=numeric(r.get('trajectory_heading_deg'),0,360)
    pad=launch.get('pad',{})
    lat=numeric(r.get('pad_lat'),-90,90);lon=numeric(r.get('pad_lng'),-180,180)
    if heading is None or lat is None or lon is None or pad.get('latitude') is None or pad.get('longitude') is None:return None
    if distance_km(lat,lon,pad['latitude'],pad['longitude'])>50:return None
    source_net=r.get('launch_time_utc')
    if not source_net or abs((utc(source_net)-utc(launch['net'])).total_seconds())>36*3600:return None
    return {'source':'Space Jellyfish Predictor','url':'https://jellyfish.johnkrausphotos.com/',
            'heading_deg':heading%360,'spread_deg':12,'kind':'published-estimate',
            'source_net':source_net,'note':'Third-party estimated heading only. No prediction, image, or model copied.',
            'prediction_supported_by_source':bool(r.get('prediction_available'))}

def official_facts(body,launch,url):
    """Only explicitly labeled azimuths/directions; no free-form compass guessing."""
    p=read_page(body);text=' '.join(p.text)
    target=launch.get('mission_name') or launch['name'].split('|')[-1].strip()
    if len(mission_name(target))<4 or mission_name(target) not in mission_name(text):return None
    m=re.search(r'(?:launch|flight|departure)\s+azimuth\s*(?:of|is|:|=)?\s*(\d{1,3}(?:\.\d+)?)\s*(?:degrees|°)',text,re.I)
    heading=numeric(m[1],0,360) if m else None
    if heading is None:
        m=re.search(r'(?:launch|fly|flying|head|heading|depart)\s+(?:to(?:ward)?\s+(?:the\s+)?)?(north(?:east|west)?|south(?:east|west)?|east|west)\b',text,re.I)
        if m:heading=DIRECTIONS.get(m[1].lower())
    if heading is None:return None
    return {'source':urlsplit(url).hostname,'url':url,'heading_deg':heading%360,'spread_deg':10,
            'kind':'official-direction','note':'Explicit launch direction from linked mission page; ascent is separately estimated.'}
