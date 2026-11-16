"""Artifact contract for evidence-backed CLI output, validated before declaring success."""
from __future__ import annotations
from pydantic import BaseModel, Field, field_validator, model_validator

class Page(BaseModel):
    url: str
    title: str
    word_count: int = Field(ge=0)
    paragraphs: list[str]
    links: list[str]
    internal_links: int=Field(ge=0)
    external_links: int=Field(ge=0)

class Evidence(BaseModel):
    source_url: str
    excerpt: str
    page_title: str = ''

class ExtractedField(BaseModel):
    field: str
    label: str
    value: str | list[str] | None
    status: str
    evidence: list[Evidence]
    method: str

    @model_validator(mode='after')
    def matches_status(self):
        if self.status not in ('found','not_found'):raise ValueError('invalid field status')
        if self.status=='not_found' and self.value is not None:raise ValueError('not_found must be null')
        if self.status=='found' and (not self.evidence or self.value is None):raise ValueError('found requires evidence')
        return self

class CrawlArtifact(BaseModel):
    schema_version: str
    status: str
    request: dict
    site: dict
    summary: dict
    seo: dict
    metrics: dict
    pages: list[Page] = Field(min_length=1)
    warnings: list[str]
    provenance: dict
    extraction: list[ExtractedField] = Field(default_factory=list)
    graph: dict=Field(default_factory=dict)
    proofs: list[Evidence] = Field(default_factory=list)

    @field_validator('status')
    @classmethod
    def status_supported(cls,v):
        if v not in ('completed','partial'):raise ValueError('not successful')
        return v

    @model_validator(mode='after')
    def verified(self):
        urls={p.url for p in self.pages}
        if self.metrics.get('pages_crawled')!=len(urls):raise ValueError('page metric is inconsistent')
        if any(e.source_url not in urls for x in self.extraction for e in x.evidence):
            raise ValueError('field evidence refers to an uncrawled source')
        if any(e.source_url not in urls for e in self.proofs):
            raise ValueError('summary evidence refers to an uncrawled source')
        return self
