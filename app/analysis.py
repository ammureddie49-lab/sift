"""Evidence-grounded extraction, summarization and transparent rule-based SEO checks."""
from __future__ import annotations
import re
from collections import Counter
from urllib.parse import urlparse
from bs4 import BeautifulSoup

STOP = set('a an and are as at be been but by can could do does for from had has have how i if in into is it its of on or our their the them there these this to us was were what when where which who will with you your we they more all not than that such using get see learn find about home page website company'.split())


def page_extract(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    meta = soup.find('meta', attrs={'name': re.compile('^description$', re.I)})
    description = (meta.get('content') or '').strip() if meta else ''
    canonical = soup.find('link', rel='canonical')
    canonical_url = canonical.get('href', '').strip() if canonical else ''
    lang = soup.html.get('lang', '') if soup.html else ''
    headings = [dict(level=int(el.name[1]), text=el.get_text(' ', strip=True)[:200]) for el in soup.find_all(re.compile('^h[1-3]$')) if el.get_text(' ', strip=True)]
    raw_contact = ' '.join(tag.get('href','')[7:] if tag.get('href','').startswith('mailto:') else tag.get('href','')[4:] for tag in soup.find_all('a',href=True) if tag.get('href','').startswith(('mailto:','tel:')))[:2000]
    # Remove content unlikely to reflect the primary page body.
    for tag in soup(['script', 'style', 'svg', 'noscript', 'iframe', 'form', 'nav', 'footer', 'header', 'aside']):
        tag.decompose()
    content = soup.find('main') or soup.find('article') or soup.body or soup
    paragraphs = []
    seen = set()
    for el in content.find_all(['p', 'li', 'h1', 'h2', 'h3']):
        val = ' '.join(el.get_text(' ', strip=True).split())
        if len(val) >= 32 and val not in seen:
            seen.add(val); paragraphs.append(val[:650])
    if not paragraphs:
        txt = ' '.join(content.get_text(' ', strip=True).split())
        paragraphs = [txt[:1250]] if txt else []
    text = ' '.join(paragraphs)
    words = re.findall(r"\b[\w'-]+\b", text)
    return {
        'url': url, 'title': title[:250], 'description': description[:500],
        'canonical': canonical_url[:500], 'language': lang[:30],
        'headings': headings[:45], 'h1_count': len([h for h in headings if h['level'] == 1]),
        'paragraphs': paragraphs[:40], 'excerpt': ' '.join(paragraphs[:3])[:550],
        'word_count': len(words), 'links': [], 'external_urls': [], 'raw_contact': raw_contact, 'internal_links': 0, 'external_links': 0,
    }


def enrich_links(page: dict, hrefs: list[str], domain: str) -> None:
    from urllib.parse import urlparse
    own = sum(urlparse(u).hostname == domain for u in hrefs)
    page['internal_links'] = own
    page['external_links'] = len(hrefs) - own
    page['links'] = hrefs[:60]


def make_summary(pages: list[dict], site_url: str) -> dict:
    home = pages[0]
    all_text = ' '.join(p.get('title','') + ' ' + p.get('description','') + ' ' + ' '.join(p.get('paragraphs',[])[:18]) for p in pages)
    tokens = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z\-]{2,}", all_text)]
    top = Counter(w for w in tokens if w not in STOP and len(w) > 3).most_common(12)
    candidates = []
    if home.get('description'):
        candidates.append(home['description'])
    for p in pages:
        for par in p.get('paragraphs', [])[:6]:
            if 55 <= len(par) <= 420 and not par.lower().startswith(('cookie', 'privacy policy', 'all rights')):
                candidates.append(par)
    highlights=[]; normalized=set()
    for item in candidates:
        key = item[:85].lower()
        if key not in normalized:
            normalized.add(key); highlights.append(item)
        if len(highlights)>=5: break
    title = home.get('title') or urlparse(site_url).hostname or 'Website'
    overview = home.get('description') or (highlights[0] if highlights else f'Extracted content from {title}.')
    return {
        'title': title, 'overview': overview[:650],
        'highlights': highlights, 'top_keywords': [{'term':word,'frequency':count} for word,count in top],
        'method': 'Deterministic, extractive summary based only on retrieved page text; no unsupported facts generated.'
    }


def seo_audit(pages: list[dict]) -> dict:
    checks=[]
    for page in pages:
        checks.append({'page':page['url'],'check':'Page title','passed':bool(page['title']),'detail': 'Present' if page['title'] else 'Missing <title> element'})
        checks.append({'page':page['url'],'check':'Meta description','passed':bool(page['description']),'detail': 'Present' if page['description'] else 'Missing meta description'})
        checks.append({'page':page['url'],'check':'Exactly one H1','passed':page['h1_count']==1,'detail':f"Found {page['h1_count']} H1 heading(s)"})
        checks.append({'page':page['url'],'check':'HTML language','passed':bool(page['language']),'detail':page['language'] or 'Missing html lang attribute'})
    passed=sum(bool(check['passed']) for check in checks)
    score=round(100*passed/len(checks)) if checks else 0
    issues=[c for c in checks if not c['passed']]
    return {'score':score,'checks':checks,'issues':issues,'note':'Informational heuristic based on four per-page HTML checks, not a comprehensive SEO or accessibility assessment.'}


def question_answer(question: str, result: dict) -> dict:
    """Search local extracted evidence; never invent an answer beyond page material."""
    q=question.lower().strip()
    pages=result.get('pages',[])
    if any(w in q for w in ['seo','audit','issues','improve','optimization']):
        audit=result.get('seo',{})
        issues=audit.get('issues',[])[:5]
        bullets='\n'.join(f"- {x['check']}: {x['detail']} ({x['page']})" for x in issues)
        return {'text':f"The heuristic SEO score is **{audit.get('score',0)}/100**.\n\n"+(f"Items to review:\n{bullets}" if issues else 'All evaluated checks passed.'),'sources':[x['page'] for x in issues]}
    if any(w in q for w in ['summary','summarize','about this site','what does','overview']):
        sm=result.get('summary',{})
        return {'text':sm.get('overview','No summary available.'),'sources':[pages[0]['url']] if pages else []}
    if any(w in q for w in ['how many pages','page count','pages crawled']):
        return {'text':f"I crawled **{len(pages)} page(s)** and extracted **{sum(p.get('word_count',0) for p in pages):,} words**.",'sources':[p['url'] for p in pages]}
    tokens=set(re.findall(r'[a-z]{3,}',q))-STOP-set('tell give show explain please information details site'.split())
    scored=[]
    for page in pages:
        options=[page.get('title',''),page.get('description','')]+page.get('paragraphs',[])
        for option in options:
            lower=option.lower()
            score=sum((3 if token in lower else 1 if len(token)>=6 and token[:5] in lower else 0) for token in tokens)
            if len(option) > 45 and score:
                scored.append((score, option, page['url']))
    scored.sort(reverse=True)
    picked=[]; sources=[]; seen=set()
    for score, snippet, url in scored:
        if snippet in seen: continue
        seen.add(snippet); picked.append(snippet[:350]); sources.append(url)
        if len(picked)==3: break
    if not picked:
        return {'text':'I could not find reliable evidence for that question in the crawled pages. Try crawling more pages or asking about topics explicitly mentioned on the website.','sources':[]}
    return {'text':'Here is what I found in the crawled pages:\n\n'+'\n\n'.join(f'- {p}' for p in picked),'sources':list(dict.fromkeys(sources))}

# --- Source anchored extraction and machine-verifiable research evidence ---
from app.planner import ALLOWED_FIELDS
from html import unescape
from urllib.parse import urljoin

_FIELD_TOKENS={
 'services':['service','provide','help','consult','offer','solution','development','design','support','training'],
 'products':['product','platform','software','feature','tool','application','app','suite'],
 'pricing':['price','pricing','monthly','yearly','plan','subscription','per month','$','₹','usd','free trial','per user'],
 'location':['address','headquarter','located','based in','office','hyderabad','london','new york','india'],
 'team':['team','founder','ceo','chief','leadership','co-founder','director'],
 'faq':['frequently asked','question','faq','how do','what is','can i'],
 'technology':['technology','technologies','stack','python','react','ai','machine learning','cloud','api'],
}

def extract_fields(pages: list[dict], requested: list[str]) -> list[dict]:
    """Deterministic evidence matching. Returns null instead of unsupported values.

    A text match is not a guarantee of semantic accuracy: UI labels it as extracted evidence.
    """
    if not pages:return []
    results=[]
    for field in requested:
        if field not in ALLOWED_FIELDS:continue
        hits=[]
        for p in pages:
            url=p['url'];title=p.get('title','')
            options=([p.get('description','')] if field=='description' else [])+p.get('paragraphs',[])
            if field=='name':
                val=(title.split('|')[0].split(' — ')[0].split(' - ')[0] or '').strip()
                if val and len(val)>2:
                    hits=[(val, {'source_url':url,'excerpt':title,'page_title':title})]
                    break
            elif field=='email':
                text=' '.join(options+[p.get('raw_contact','')]);matches=re.findall(r'(?<![\w.])([\w.+\-]+@[\w.\-]+\.[A-Za-z]{2,})(?![\w.])',text)
                for m in matches[:4]:hits.append((m,{'source_url':url,'excerpt':next((s for s in options if m in s),m)[:360],'page_title':title}))
            elif field=='phone':
                text=' '.join(options+[p.get('raw_contact','')])
                # Require clear phone-like formatting and at least 9 digits.
                matches=re.findall(r'(?<!\w)(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?|\d{2,4}[\s.-])\d{3,4}[\s.-]?\d{3,4}(?!\w)',text)
                for m in matches[:3]:
                    if 9<=len(re.sub(r'\D','',m))<=15:hits.append((m.strip(),{'source_url':url,'excerpt':next((s for s in options if m in s),m)[:360],'page_title':title}))
            elif field=='social':
                for u in p.get('external_urls',[]):
                    if any(s in urlparse(u).hostname.lower() for s in ('linkedin.com','github.com','instagram.com','facebook.com','youtube.com','x.com','twitter.com')):
                        hits.append((u,{'source_url':url,'excerpt':f'Social profile linked from {title or url}: {u}'[:360],'page_title':title}))
            else:
                words=_FIELD_TOKENS.get(field,[])
                for sentence in options:
                    lower=sentence.lower()
                    if field=='description' or any(w in lower for w in words):
                        # Avoid filler snippets and source-internal instructions; never execute extracted text.
                        if len(sentence)>=25:hits.append((sentence[:340],{'source_url':url,'excerpt':sentence[:340],'page_title':title}))
                        if field=='description' and hits:break
        unique=[];seen=set()
        for val,proof in hits:
            key=val.casefold().strip()
            if key not in seen:
                seen.add(key);unique.append((val,proof))
            if len(unique)>=4:break
        if unique:
            vals=[item[0] for item in unique]
            results.append({'field':field,'label':ALLOWED_FIELDS[field],'value':vals[0] if field in ('name','description','email','phone') else vals,
              'status':'found','evidence':[item[1] for item in unique],'method':'verbatim-text-or-link-match'})
        else:
            results.append({'field':field,'label':ALLOWED_FIELDS[field],'value':None,
              'status':'not_found','evidence':[],'method':'no-verifiable-match'})
    return results


def summary_proofs(pages:list[dict], summary:dict) -> list[dict]:
    """Links each highlighted statement to its actual page paragraph/description."""
    proofs=[]
    for item in [summary.get('overview',''),*summary.get('highlights',[])]:
        for p in pages:
            if item and (item==p.get('description') or item in p.get('paragraphs',[])):
                key=(p['url'],item)
                if not any((x['source_url'],x['excerpt'])==key for x in proofs):
                    proofs.append({'source_url':p['url'],'excerpt':item[:650],'page_title':p.get('title','')})
                break
    return proofs
