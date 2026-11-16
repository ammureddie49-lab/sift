"""API smoke coverage without requiring external network."""
import time
from fastapi.testclient import TestClient
from app.main import app


def test_api_health_session_chat():
    with TestClient(app) as client:
        health=client.get('/api/health')
        assert health.status_code==200
        assert health.json()['cli']=='app.crawler'
        session=client.post('/api/sessions',json={'title':'Test workspace'}).json()
        sid=session['id']
        response=client.post('/api/chat',json={'session_id':sid,'message':'Hello!','max_pages':4})
        assert response.status_code==200
        assert response.json()['kind']=='text'
        messages=client.get('/api/sessions/'+sid).json()['messages']
        assert len(messages)==2
        assert client.get('/').status_code==200
        assert client.get('/api/tasks/notreal').status_code==404
        assert client.delete('/api/sessions/'+sid).json()['deleted']


def test_chat_rejects_untrusted_url():
    with TestClient(app) as client:
        sid=client.post('/api/sessions',json={}).json()['id']
        response=client.post('/api/chat',json={'session_id':sid,'message':'Crawl http://127.0.0.1/private'})
        assert response.status_code==200
        assert response.json()['kind']=='text'
        assert 'blocked' in response.json()['content'].lower()
        client.delete('/api/sessions/'+sid)
