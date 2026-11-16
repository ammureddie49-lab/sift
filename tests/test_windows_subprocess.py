"""Regression: Windows Uvicorn reload may have no asyncio subprocess transport."""
import asyncio
import time
from fastapi.testclient import TestClient
from app.main import app


def test_cli_runs_even_when_asyncio_subprocess_is_unavailable(local_site, monkeypatch):
    monkeypatch.setenv('ALLOW_PRIVATE_NETWORK', 'true')

    async def unsupported_subprocess(*args, **kwargs):
        raise NotImplementedError('Windows SelectorEventLoop cannot launch subprocesses')

    monkeypatch.setattr(asyncio, 'create_subprocess_exec', unsupported_subprocess)
    with TestClient(app) as client:
        sid = client.post('/api/sessions', json={}).json()['id']
        try:
            prompt = f'Crawl {local_site}, summarize and return JSON'
            plan = client.post('/api/plan', json={'message':prompt, 'max_pages':4}).json()['plan']
            response = client.post('/api/execute', json={
                'session_id':sid, 'message':prompt, 'plan':plan, 'permission_confirmed':True
            })
            assert response.status_code == 200, response.text
            tid = response.json()['task_id']
            deadline = time.monotonic() + 16
            task = None
            while time.monotonic() < deadline:
                task = client.get(f'/api/tasks/{tid}').json()
                if task['status'] not in ('queued', 'running'):
                    break
                time.sleep(0.1)
            assert task['status'] == 'completed', task
            assert task['exit_code'] == 0
            assert task['logs'] and task['result']['metrics']['pages_crawled'] == 4
            assert client.get(f'/api/tasks/{tid}/trace').json()['stdout_events']
        finally:
            client.delete('/api/sessions/' + sid)
