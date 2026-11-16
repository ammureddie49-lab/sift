"""Real HTTP test against our own mini-site; zero fabricated crawler responses."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]

class Silent(SimpleHTTPRequestHandler):
    def log_message(self,*a,**kw):pass

@pytest.fixture(scope='module')
def local_site():
    handler=partial(Silent,directory=str(ROOT/'demo_site'))
    httpd=ThreadingHTTPServer(('127.0.0.1',0),handler)
    thread=threading.Thread(target=httpd.serve_forever,daemon=True)
    thread.start()
    try:yield f'http://127.0.0.1:{httpd.server_port}'
    finally:httpd.shutdown();thread.join(timeout=3);httpd.server_close()

def test_cli_real_http_crawl_with_artifact(local_site):
    artifact=ROOT/'data'/'results'/f'test-{uuid.uuid4().hex}.json'
    try:
        proc=subprocess.run([sys.executable,'-m','app.crawler','--url',local_site,'--max-pages','4','--timeout','5','--output',str(artifact)],
            cwd=ROOT,env={**os.environ,'ALLOW_PRIVATE_NETWORK':'true'},capture_output=True,text=True,timeout=35)
        assert proc.returncode==0,(proc.stdout,proc.stderr)
        logs=[json.loads(line) for line in proc.stdout.strip().splitlines()]
        assert any(l['step']=='fetch' for l in logs)
        assert any(l['step']=='complete' and l['progress']==100 for l in logs)
        result=json.loads(artifact.read_text(encoding='utf-8'))
        assert result['status']=='completed'
        assert result['metrics']['pages_crawled']==4
        assert result['metrics']['total_words']>100
        assert result['site']['title'].startswith('Northstar Labs')
        assert len(result['pages'])==4
        assert result['seo']['score']>=75
        assert all(p['url'].startswith(local_site) for p in result['pages'])
    finally:artifact.unlink(missing_ok=True)

def test_cli_rejects_non_allowlisted_output(local_site,tmp_path):
    proc=subprocess.run([sys.executable,'-m','app.crawler','--url',local_site,'--max-pages','2','--output',str(tmp_path/'outside.json')],
      cwd=ROOT,env={**os.environ,'ALLOW_PRIVATE_NETWORK':'true'},capture_output=True,text=True,timeout=15)
    assert proc.returncode==2
    assert not (tmp_path/'outside.json').exists()
