"""Approved CLI worker invoked ONLY through subprocess with validated argv.

Example: python -m app.crawler --url https://example.com --max-pages 6 --output data/results/demo.json
Writes progress JSONL to stdout and a structured artifact to --output.
"""
from __future__ import annotations
import argparse
import socket
import ipaddress
from contextlib import contextmanager
from urllib.parse import urlunparse
import json
import os
import re
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from app.analysis import enrich_links, make_summary, page_extract, seo_audit, extract_fields, summary_proofs
from app.security import UnsafeURL, normalize_url, same_site, validate_url, private_network_allowed

USER_AGENT = 'SiftOrbit-BuildSprint/3.0 (+educational; robots compliant)'
MAX_BYTES = 2_000_000
SKIP_SUFFIX = ('.pdf','.png','.jpg','.jpeg','.gif','.webp','.svg','.zip','.mp4','.mp3','.doc','.docx','.xls','.xlsx','.ppt','.pptx','.css','.js','.xml')
PRIORITY = ('about','services','products','features','solutions','pricing','team','mission','contact','docs','documentation','blog','faq','who-we-are','careers')


def emit(step: str, message: str, progress: int = 0, level: str = 'info', **details) -> None:
    row = {'event': 'progress', 'at': datetime.now(timezone.utc).isoformat(), 'step': step,
           'message': message, 'progress': progress, 'level': level, **details}
    print(json.dumps(row, ensure_ascii=False), flush=True)


@contextmanager
def pinned_stream(client: httpx.Client, url: str, *, timeout: float, accept: str='text/html'):
    """Connect only to a checked IP, while preserving HTTP Host and TLS SNI.

    Resolving the hostname then connecting by name can be vulnerable to DNS rebinding.
    Pinning the network destination for each request closes that check/use gap.
    """
    normalized=validate_url(url)
    parsed=urlparse(normalized)
    host=parsed.hostname
    port=parsed.port or (443 if parsed.scheme=='https' else 80)
    infos=socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
    allowed=[]
    for info in infos:
        ip=ipaddress.ip_address(info[4][0])
        if ip.is_global or private_network_allowed():allowed.append(str(ip))
    if not allowed:raise UnsafeURL('No permitted IP address for requested hostname.')
    # URL target is the checked IP; original Host + SNI support virtual hosts & HTTPS.
    ip=allowed[0]
    authority=f'[{ip}]' if ':' in ip else ip
    if parsed.port:authority+=f':{port}'
    dest=urlunparse(parsed._replace(netloc=authority))
    host_header=host if not parsed.port else f'{host}:{port}'
    headers={'Host':host_header,'User-Agent':USER_AGENT,'Accept':accept}
    with client.stream('GET',dest,headers=headers,timeout=timeout,follow_redirects=False,extensions={'sni_hostname':host}) as response:
        yield response


def safe_fetch(client: httpx.Client, url: str, timeout: float, robots: RobotFileParser | None = None) -> tuple[str, str, int]:
    current = url
    for _ in range(4):
        current=validate_url(current)
        if robots and not robots.can_fetch(USER_AGENT,current):
            raise RuntimeError('robots.txt disallows requested or redirected path.')
        try:
            with pinned_stream(client,current,timeout=timeout,accept='text/html,text/plain;q=0.8,*/*;q=0.2') as response:
                if response.status_code in {301,302,303,307,308}:
                    target=response.headers.get('location')
                    if not target:raise RuntimeError('Redirect has no location header.')
                    next_url=urljoin(current,target)
                    if not same_site(next_url,url):raise RuntimeError('Cross-domain redirects are not followed.')
                    if urlparse(current).scheme=='https' and urlparse(next_url).scheme!='https':
                        raise RuntimeError('HTTPS to HTTP downgrade rejected.')
                    current=next_url
                    continue
                if response.status_code>=400:raise RuntimeError(f'HTTP {response.status_code}')
                ct=response.headers.get('content-type','').lower()
                if not any(k in ct for k in ('html','text/plain','xhtml')):
                    raise RuntimeError(f'Non-HTML content rejected ({ct or "unknown type"}).')
                received=bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    received.extend(chunk)
                    if len(received)>MAX_BYTES:raise RuntimeError('Page exceeds 2 MB content safety limit.')
                return received.decode(response.encoding or 'utf-8',errors='replace'),current,response.status_code
        except httpx.TimeoutException as exc:raise RuntimeError('Request timed out.') from exc
        except httpx.RequestError as exc:raise RuntimeError('Network request failed: '+type(exc).__name__) from exc
    raise RuntimeError('Too many redirects.')


def robots_policy(client: httpx.Client, start_url: str, timeout: float) -> tuple[RobotFileParser | None, str | None]:
    parsed=urlparse(start_url)
    robots=f'{parsed.scheme}://{parsed.netloc}/robots.txt'
    try:
        validate_url(robots)
        with pinned_stream(client,robots,timeout=timeout,accept='text/plain,*/*;q=0.2') as resp:
            if resp.status_code in (404,410):
                return None,None  # RFC: not found -> allowed.
            if resp.status_code in (401,403):
                return None,'robots.txt denies access (HTTP '+str(resp.status_code)+').'
            if resp.status_code != 200:
                return None,'robots.txt unavailable (HTTP '+str(resp.status_code)+'). Crawl stopped conservatively.'
            data=bytearray()
            for chunk in resp.iter_bytes():
                data.extend(chunk)
                if len(data)>250_000:
                    return None,'robots.txt exceeds safety limit; crawl stopped.'
            rp=RobotFileParser()
            rp.parse(data.decode('utf-8','replace').splitlines())
            return rp,None
    except (httpx.RequestError, httpx.TimeoutException, UnsafeURL) as exc:
        return None,f'Could not check robots.txt ({type(exc).__name__}); crawl stopped conservatively.'


def all_page_links(html: str, current_url: str, start_url: str) -> tuple[list[str],list[str]]:
    soup=BeautifulSoup(html,'html.parser')
    internal=[];external=[];seen=set()
    for a in soup.find_all('a',href=True):
        href=a['href'].strip()
        if href.startswith(('#','mailto:','tel:','javascript:','data:')):continue
        try:
            link=normalize_url(urljoin(current_url,href))
            parts=urlparse(link)
            if parts.scheme not in ('https','http') or parts.path.lower().endswith(SKIP_SUFFIX):continue
            if link in seen:continue
            seen.add(link)
            (internal if same_site(link,start_url) else external).append(link)
        except (ValueError,TypeError):continue
    return internal[:180],external[:180]

def candidate_links(html: str, current_url: str, start_url: str) -> list[str]:
    """Backwards compatible internal-only traversal interface."""
    return all_page_links(html,current_url,start_url)[0]


def link_rank(link: str) -> int:
    path=urlparse(link).path.lower()
    return min((i for i,t in enumerate(PRIORITY) if t in path),default=len(PRIORITY))


def crawl(start_url: str,max_pages: int,timeout: float,max_depth: int=2, fields: list[str] | None = None) -> tuple[dict,int]:
    start=time.monotonic()
    emit('validate','Validating URL and checking network boundaries…',4)
    start_url=validate_url(start_url)
    start_url=normalize_url(start_url)
    origin=urlparse(start_url).hostname
    pages=[]; warnings=[]; discovered={start_url}; queue=deque([(start_url,0)]); attempted=set(); edges=[]; nodes={start_url:{"id":start_url,"url":start_url,"title":urlparse(start_url).path or "Home","depth":0,"status":"discovered"}}
    emit('robots','Reading robots.txt and crawl permissions…',12)
    with httpx.Client(trust_env=False, headers={'User-Agent':USER_AGENT}) as client:
        robots,robots_error=robots_policy(client,start_url,timeout)
        if robots_error:
            emit('robots',robots_error,100,'error')
            return {'status':'failed','error':robots_error,'pages':[],'warnings':[robots_error]},3
        while queue and len(pages)<max_pages:
            url,depth=queue.popleft()
            if url in attempted or depth>max_depth:continue
            attempted.add(url)
            try:
                validate_url(url)
                if robots and not robots.can_fetch(USER_AGENT,url):
                    warnings.append(f'Blocked by robots.txt: {url}')
                    nodes[url]={"id":url,"url":url,"title":urlparse(url).path or 'Home',"depth":depth,"status":"blocked"}
                    emit('robots',f'Skipping disallowed path: {url}',min(87,20+int(len(pages)/max_pages*60)),'warning')
                    continue
                emit('fetch',f'Fetching {url}',min(87,20+int(len(pages)/max_pages*60)),url=url)
                html,final_url,status=safe_fetch(client,url,timeout,robots)
                if robots and not robots.can_fetch(USER_AGENT,final_url):
                    warnings.append(f'Final URL disallowed by robots.txt: {final_url}')
                    continue
                page=page_extract(html,final_url)
                urls,external_urls=all_page_links(html,final_url,start_url)
                enrich_links(page,urls+external_urls,origin)
                page["external_urls"]=external_urls[:60]
                nodes[url]={"id":url,"url":url,"title":page["title"] or urlparse(url).path or "Home","depth":depth,"status":"crawled"}
                for link in urls[:80]:
                    edges.append({"source":url,"target":link})
                    if link not in nodes and len(nodes)<110:nodes[link]={"id":link,"url":link,"title":urlparse(link).path or "Home","depth":depth+1,"status":"discovered"}
                page['http_status']=status
                page['depth']=depth
                pages.append(page)
                emit('extract',f'Extracted {page["title"] or final_url} • {page["word_count"]:,} words',min(90,26+int(len(pages)/max_pages*60)),url=final_url)
                for link in sorted(urls,key=link_rank):
                    if link not in discovered and len(discovered)<max_pages*20:
                        discovered.add(link)
                        if depth < max_depth:queue.append((link,depth+1))
                # Polite crawl delay
                if queue and len(pages)<max_pages:time.sleep(0.2)
            except (RuntimeError,UnsafeURL,ValueError) as exc:
                reason=f'{url}: {str(exc)[:180]}'
                warnings.append(reason)
                nodes[url]={"id":url,"url":url,"title":urlparse(url).path or 'Page',"depth":depth,"status":"error"}
                emit('fetch',f'Could not crawl {urlparse(url).path or "/"}: {str(exc)[:140]}',min(90,26+int(len(pages)/max_pages*60)),'warning')
            except Exception as exc:
                warnings.append(f'{url}: {type(exc).__name__}')
                nodes[url]={"id":url,"url":url,"title":urlparse(url).path or 'Page',"depth":depth,"status":"error"}
                emit('fetch',f'Page failed: {type(exc).__name__}',min(90,26+int(len(pages)/max_pages*60)),'warning')
    if not pages:
        err='No permitted HTML pages could be fetched.'
        emit('complete',err,100,'error')
        return {'status':'failed','error':err,'pages':[],'warnings':warnings,'request':{'url':start_url,'max_pages':max_pages}},4
    emit('analyze','Generating grounded summary, key topics and SEO checks…',94)
    requested=fields if fields is not None else ['name','description','services','products','email']
    extracted=extract_fields(pages,requested)
    summary=make_summary(pages,start_url)
    proof=summary_proofs(pages,summary)
    emit('verify',f'Validating {len(extracted)} extracted fields and {len(proof)} source-linked claims…',97)
    result={
        'schema_version':'1.0.0','status':'partial' if warnings else 'completed',
        'request':{'url':start_url,'max_pages':max_pages,'max_depth':max_depth,'fields':requested},
        'site':{'url':start_url,'domain':origin,'title':pages[0]['title'],'description':pages[0]['description'], 'language':pages[0]['language']},
        'summary':summary,'seo':seo_audit(pages),
        'extraction':extracted,'proofs':proof,
        'graph':{'nodes':list(nodes.values())[:110],'edges':[e for e in edges if e['source'] in nodes and e['target'] in nodes][:240]},
        'metrics':{'pages_crawled':len(pages),'pages_discovered':len(discovered),
                   'total_words':sum(p['word_count'] for p in pages),
                   'internal_links':sum(p['internal_links'] for p in pages),
                   'external_links':sum(p['external_links'] for p in pages),
                   'duration_seconds':round(time.monotonic()-start,2)},
        'pages':pages,'warnings':warnings,
        'provenance':{'crawler':'Sift Studio approved Python CLI','method':'HTTP GET + BeautifulSoup HTML parsing; deterministic extractive analysis','live':True,'robots_respected':True,'generated_at':datetime.now(timezone.utc).isoformat()}
    }
    emit('complete',f'Finished: {len(pages)} actual page(s), {result["metrics"]["total_words"]:,} words.',100,'success' if not warnings else 'warning')
    return result,0


def main() -> int:
    ap=argparse.ArgumentParser(description='Approved website crawling CLI for Sift Studio')
    ap.add_argument('--url',required=True)
    ap.add_argument('--max-pages',type=int,default=6)
    ap.add_argument('--max-depth',type=int,default=2)
    ap.add_argument('--timeout',type=float,default=12)
    ap.add_argument('--output',required=True)
    ap.add_argument('--fields-json',default='["name","description","services","products","email"]')
    args=ap.parse_args()
    if not (1<=args.max_pages<=15 and 0<=args.max_depth<=3 and 3<=args.timeout<=25):
        emit('validate','CLI limits out of bounds.',100,'error');return 2
    try:
        output=Path(args.output).resolve()
        results_root=(Path(__file__).resolve().parents[1]/'data'/'results').resolve()
        if not output.is_relative_to(results_root) or output.suffix!='.json':
            raise ValueError('Output path outside approved results directory.')
        from app.planner import ALLOWED_FIELDS
        fields=json.loads(args.fields_json)
        if not isinstance(fields,list) or len(fields)>12 or len(set(fields))!=len(fields) or any(not isinstance(v,str) or v not in ALLOWED_FIELDS for v in fields):
            raise ValueError('Field selection not allowlisted.')
        result,code=crawl(args.url,args.max_pages,args.timeout,args.max_depth,fields)
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        return code
    except (UnsafeURL,ValueError) as exc:
        emit('validate',str(exc),100,'error')
        return 2
    except Exception as exc:
        emit('error',f'Unexpected worker failure: {type(exc).__name__}',100,'error')
        print(f'worker_failure={type(exc).__name__}',file=sys.stderr)
        return 5


if __name__=='__main__':
    raise SystemExit(main())
