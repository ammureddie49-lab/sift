"""New behavior contracts: consent, planning, actual extraction, source graph, comparison."""
from __future__ import annotations
import json
import time
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.planner import plan_prompt, TaskPlan
from app.analysis import page_extract, extract_fields, summary_proofs
from app.crawler import all_page_links
from app.schemas import CrawlArtifact


def wait_finished(client,tid,seconds=15):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        t=client.get('/api/tasks/'+tid).json()
        if t['status'] not in {'running','queued'}:return t
        time.sleep(.1)
    raise AssertionError(f'Task {tid} never finished')


def test_planning_does_not_crawl_negated_request():
    p=plan_prompt('Do not crawl https://example.com; explain what the crawler does')
    assert p.action=='no_action'
    assert plan_prompt('How does the tool work?').action=='no_action'
    assert plan_prompt('Compare https://example.com and https://iana.org').action=='compare_websites'
    assert plan_prompt('Crawl https://example.com and extract pricing and team').fields==['pricing','team']


def test_fields_are_strictly_allowlisted():
    try:TaskPlan(fields=['__import__("os")'])
    except ValueError:pass
    else:raise AssertionError('Invalid extraction field incorrectly accepted')


def test_graph_counts_internal_and_external_links():
    h='''<html><a href="/about">Internal</a><a href="https://external.org">External</a></html>'''
    internal,external=all_page_links(h,'https://example.com','https://example.com')
    assert internal==['https://example.com/about']
    assert external==['https://external.org/']


def test_evidence_field_with_absent_data_is_null():
    p=page_extract('<html><head><title>Demo Labs</title></head><body><main><p>We build services for local businesses that need secure applications.</p></main></body></html>','https://example.com')
    fields=extract_fields([p],['name','services','email'])
    assert fields[0]['value']=='Demo Labs'
    assert fields[1]['status']=='found'
    assert fields[2]['status']=='not_found' and fields[2]['value'] is None
    assert fields[1]['evidence'][0]['source_url']==p['url']


def test_artifact_rejects_unfetched_evidence():
    from app.schemas import CrawlArtifact
    try:
        CrawlArtifact.model_validate({'schema_version':'1','status':'completed','request':{},'site':{},'summary':{},'seo':{},
          'metrics':{'pages_crawled':1},'warnings':[],'provenance':{},
          'pages':[{'url':'https://example.com','title':'Demo','word_count':1,'paragraphs':['demo'],'links':[],'internal_links':0,'external_links':0}],
          'proofs':[{'source_url':'https://unfetched.test','excerpt':'unverified'}]})
    except ValueError:pass
    else:raise AssertionError('Invalid provenance unexpectedly validated')


def test_plan_execute_proof_graph_and_comparison(local_site,monkeypatch):
    monkeypatch.setenv('ALLOW_PRIVATE_NETWORK','true')
    with TestClient(app) as client:
        sid=client.post('/api/sessions',json={}).json()['id']
        prompt=f'Compare {local_site}/ and {local_site}/about.html. Extract company name, services and email as JSON.'
        try:
            draft=client.post('/api/plan',json={'message':prompt,'max_pages':4})
            assert draft.status_code==200,draft.text
            assert draft.json()['executed'] is False
            plan=draft.json()['plan']
            assert plan['action']=='compare_websites'
            denied=client.post('/api/execute',json={'session_id':sid,'message':prompt,'plan':plan,'permission_confirmed':False})
            assert denied.status_code==422
            start=client.post('/api/execute',json={'session_id':sid,'message':prompt,'plan':plan,'permission_confirmed':True})
            assert start.status_code==200,start.text
            ids=start.json()['task_ids']
            assert len(ids)==2
            tasks=[wait_finished(client,tid) for tid in ids]
            assert all(t['status'] in ('completed','partial') for t in tasks),tasks
            for t in tasks:
                assert t['artifact_sha256'] and len(t['artifact_sha256'])==64
                assert t['result']['provenance']['live']
                assert t['result']['graph']['nodes']
                assert t['result']['graph']['edges']
                assert t['result']['extraction']
                assert t['result']['proofs']
                assert t['stderr']==[]
                assert t['plan']['fields']
                assert t['exit_code']==0
            comp=client.get('/api/compare',params={'left':ids[0],'right':ids[1]})
            assert comp.status_code==200,comp.text
            assert len(comp.json()['rows'])>=3
            assert comp.json()['method'].startswith('Two independently')
            trace=client.get('/api/tasks/'+ids[0]+'/trace').json()
            assert trace['plan']['max_pages']==4
            assert any(ev['step']=='verify' for ev in trace['stdout_events'])
            assert '--fields-json' in trace['command']
        finally:
            client.delete('/api/sessions/'+sid)
