"""Shared tiny local website for actual-HTTP integration tests."""
from __future__ import annotations
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import pytest

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args,**kwargs): pass

@pytest.fixture
def local_site():
    root=Path(__file__).resolve().parents[1]
    handler=partial(QuietHandler,directory=str(root/'demo_site'))
    server=ThreadingHTTPServer(('127.0.0.1',0),handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try: yield f'http://127.0.0.1:{server.server_port}'
    finally: server.shutdown(); thread.join(timeout=3);server.server_close()
