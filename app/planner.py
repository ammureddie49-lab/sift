"""Explainable, bounded natural-language planner. Produces DATA, never executable commands.

No network model is required. A provider-backed planner may be introduced in a future version,
but the deterministic implementation always keeps execution inside the approved tool registry.
"""
from __future__ import annotations
import re
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator, model_validator

ALLOWED_FIELDS = {
    'name': 'Organization / product name', 'description': 'What the website offers',
    'services': 'Services', 'products': 'Products / features', 'pricing': 'Pricing',
    'email': 'Contact email', 'phone': 'Contact telephone', 'location': 'Location / address',
    'team': 'People / team', 'faq': 'Frequently asked questions',
    'technology': 'Technologies', 'social': 'Social profiles',
}
KEYWORDS = {
    'name': ['company name', 'brand name', 'organization name'],
    'description': ['description', 'overview', 'summarize', 'summary', 'about', 'explain'],
    'services': ['service', 'solution', 'offerings'],
    'products': ['product', 'feature', 'tool'],
    'pricing': ['pricing', 'price', 'cost', 'plan', 'subscription'],
    'email': ['email', 'e-mail', 'contact details', 'contact information'],
    'phone': ['phone', 'telephone', 'call us', 'contact details', 'contact information'],
    'location': ['address', 'location', 'where located', 'office'],
    'team': ['team', 'founder', 'leadership', 'employees'],
    'faq': ['faq', 'questions', 'frequently asked'],
    'technology': ['technology', 'technologies', 'stack', 'tech stack'],
    'social': ['social', 'linkedin', 'instagram', 'twitter'],
}

class TaskPlan(BaseModel):
    action: str = 'crawl_website'
    target_url: str | None = None
    comparison_url: str | None = None
    max_pages: int = Field(default=6,ge=1,le=15)
    max_depth: int = Field(default=2,ge=0,le=3)
    fields: list[str] = Field(default_factory=lambda:['name','description','services','products','email'])
    requested_outputs: list[str] = Field(default_factory=lambda:['summary','structured_json'])
    tool: str = 'app.crawler'
    execution_policy: str = 'approved-commands-only'
    requires_approval: bool = True
    interpretation: str = ''

    @field_validator('fields')
    @classmethod
    def fields_are_approved(cls, value):
        if len(value)>12 or len(set(value))!=len(value) or any(v not in ALLOWED_FIELDS for v in value):
            raise ValueError('Choose at most 12 distinct fields from the approved extraction catalog.')
        return value

    @field_validator('requested_outputs')
    @classmethod
    def outputs_are_approved(cls,value):
        valid={'summary','structured_json','seo_audit','evidence','site_graph'}
        if len(value)>5 or any(v not in valid for v in value):
            raise ValueError('Unsupported report output.')
        return list(dict.fromkeys(value))

    @model_validator(mode='after')
    def allowed_action(self):
        if self.action not in {'crawl_website','compare_websites','answer_from_evidence','no_action'}:
            raise ValueError('Unsupported operation.')
        if self.tool != 'app.crawler' or self.execution_policy!='approved-commands-only':
            raise ValueError('Only the approved crawler tool is executable.')
        return self


def urls_in(text: str) -> list[str]:
    found=[]
    for m in re.findall(r'https?://[^\s<>"\'`]+|(?<![\w@])(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/[^\s<>"\'`]*)?',text,re.I):
        u=m.rstrip('.,;)]}\'"')
        if not u.lower().startswith(('https://','http://')):u='https://'+u
        if u not in found: found.append(u)
    return found[:3]


def plan_prompt(message: str, url: str | None = None, max_pages: int = 6, fields: list[str] | None = None) -> TaskPlan:
    text=message.lower()
    urls=([url] if url else [])+urls_in(message)
    urls=list(dict.fromkeys(u for u in urls if u))
    # Do not turn negative or hypothetical mentions into actual website requests.
    refused=bool(re.search(r"\b(?:don['’]?t|do not|never|without|no need to)\s+(?:actually\s+)?(?:crawl|scrape|fetch|visit|scan|run)\b",text))
    hypothetical=bool(re.search(r'\b(?:what does|how does|explain)\s+(?:the\s+)?(?:crawler|app|tool|sift)\b',text)) and not re.search(r'\b(?:crawl|scan|extract|scrape|research|compare)\s+https?://',text)
    action='no_action' if refused or hypothetical else ('compare_websites' if len(urls)>=2 and re.search(r'\b(compare|versus|\bvs\b|difference|contrast)\b',text) else 'crawl_website' if urls else 'answer_from_evidence')
    if fields is None:
        picked=[name for name,terms in KEYWORDS.items() if any(t in text for t in terms)]
        if not picked or picked==['description']:picked=['name','description','services','products','email']
        fields=picked[:12]
    outputs=[]
    if any(w in text for w in ['summar','overview','research','about']):outputs.append('summary')
    if any(w in text for w in ['json','extract','structure','data','compare']):outputs.append('structured_json')
    if any(w in text for w in ['seo','audit','headings','metadata','page quality']):outputs.append('seo_audit')
    outputs += ['evidence','site_graph']
    if not any(x in outputs for x in ('summary','structured_json','seo_audit')):outputs=['summary','structured_json',*outputs]
    return TaskPlan(action=action,target_url=urls[0] if urls else None,
        comparison_url=urls[1] if action=='compare_websites' else None,max_pages=max_pages,
        fields=fields,requested_outputs=list(dict.fromkeys(outputs)),
        interpretation={
            'crawl_website':'Crawl permitted pages, extract requested fields and deliver verified evidence.',
            'compare_websites':'Run two independent approved crawler processes and compare verified information.',
            'answer_from_evidence':'Answer from an existing completed crawl without launching new work.',
            'no_action':'No crawler will run because the request does not authorize execution.'
        }[action])
