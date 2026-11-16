"""End-to-end API -> actual CLI subprocess -> stdout -> saved JSON tests."""
from __future__ import annotations
import json
import time

from fastapi.testclient import TestClient
from app.main import app, interpret_intent


def test_interpret_intent_is_constrained():
    p=interpret_intent('Crawl https://example.com and summarize in JSON; check SEO', 'https://example.com')
    assert p['action']=='crawl_website'
    assert p['tool']=='app.crawler'
    assert set(p['requested_outputs']) == {'summary','structured_json','seo_audit'}
    assert p['execution_policy']=='approved-commands-only'


def test_followup_routes_to_evidence_only():
    p=interpret_intent('What does the company do?')
    assert p['action']=='answer_from_evidence'
    assert p['tool']=='evidence-search'
    assert p['requested_outputs'] == ['summary','structured_json'] or 'summary' in p['requested_outputs']


def test_real_chat_task_trace_and_download(local_site,monkeypatch):
    monkeypatch.setenv('ALLOW_PRIVATE_NETWORK','true')
    with TestClient(app) as client:
        session=client.post('/api/sessions',json={'title':'Live orchestration test'}).json()
        sid=session['id']
        try:
            prompt=f'Crawl {local_site}, summarize and give me JSON.'
            # Legacy chat is text-only and cannot bypass explicit authorization.
            unsafe=client.post('/api/chat',json={'session_id':sid,'message':prompt,'max_pages':4})
            assert unsafe.status_code==200 and unsafe.json()['approval_required'] is True
            assert unsafe.json()['kind']=='text'
            plan_response=client.post('/api/plan',json={'message':prompt,'max_pages':4})
            assert plan_response.status_code==200
            plan=plan_response.json()['plan']
            denied=client.post('/api/execute',json={'session_id':sid,'message':prompt,'plan':plan,'permission_confirmed':False})
            assert denied.status_code==422
            response=client.post('/api/execute',json={'session_id':sid,'message':prompt,'plan':plan,'permission_confirmed':True})
            assert response.status_code==200, response.text
            assert response.json()['kind']=='task'
            tid=response.json()['task_id']
            assert response.json()['plan']['action']=='crawl_website'
            t={}
            for _ in range(90):
                t=client.get('/api/tasks/'+tid).json()
                if t['status'] not in ('queued','running'):break
                time.sleep(0.1)
            assert t['status']=='completed',t
            assert t['exit_code']==0
            assert t['result']['metrics']['pages_crawled']==4
            assert t['result']['provenance']['live'] is True
            assert t['result']['summary']['overview']
            assert t['intent']['tool']=='app.crawler'
            assert len(t['logs'])>=6
            tr=client.get(f'/api/tasks/{tid}/trace').json()
            assert tr['status']=='completed' and tr['exit_code']==0
            assert tr['command'][:3]==['python','-m','app.crawler']
            assert any(x['step']=='fetch' for x in tr['stdout_events'])
            download=client.get(f'/api/tasks/{tid}/download')
            assert download.status_code==200
            assert json.loads(download.content)['status']=='completed'
        finally:
            client.delete('/api/sessions/'+sid)
