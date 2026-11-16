"""SQLite durable history. Small, dependency-free, per-operation connections."""
from __future__ import annotations
import json
import sqlite3
import uuid
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/'data'/'sift_studio.db'


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect():
    DB.parent.mkdir(exist_ok=True,parents=True)
    con=sqlite3.connect(DB,timeout=10)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA busy_timeout=10000')
    return con


def init():
    with connect() as con:
        con.execute('PRAGMA journal_mode=WAL')
        con.executescript('''
        CREATE TABLE IF NOT EXISTS sessions (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
          id TEXT PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,
          kind TEXT NOT NULL DEFAULT 'text', task_id TEXT, sources TEXT NOT NULL DEFAULT '[]',
          created_at TEXT NOT NULL, FOREIGN KEY(session_id) REFERENCES sessions(id)
        );
        CREATE TABLE IF NOT EXISTS tasks (
          id TEXT PRIMARY KEY, session_id TEXT NOT NULL, url TEXT NOT NULL, prompt TEXT NOT NULL,
          max_pages INTEGER NOT NULL, status TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0,
          logs TEXT NOT NULL DEFAULT '[]', error TEXT, result_file TEXT, exit_code INTEGER,
          started_at TEXT, finished_at TEXT, created_at TEXT NOT NULL,
          plan TEXT NOT NULL DEFAULT '{}', stderr TEXT NOT NULL DEFAULT '[]',
          FOREIGN KEY(session_id) REFERENCES sessions(id)
        );
        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id,created_at);
        CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id,created_at);
        ''')
        cols={r[1] for r in con.execute('PRAGMA table_info(tasks)')}
        if 'plan' not in cols: con.execute("ALTER TABLE tasks ADD COLUMN plan TEXT NOT NULL DEFAULT '{}'")
        if 'stderr' not in cols: con.execute("ALTER TABLE tasks ADD COLUMN stderr TEXT NOT NULL DEFAULT '[]'")


def uid() -> str:
    return uuid.uuid4().hex[:16]


def row(d):
    return dict(d) if d is not None else None


def create_session(title='New conversation'):
    sid=uid();t=now()
    with connect() as con:
        con.execute('INSERT INTO sessions VALUES (?,?,?,?)',(sid,title,t,t))
    return get_session(sid)


def get_session(sid):
    with connect() as con:
        return row(con.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone())


def list_sessions():
    with connect() as con:
        return [dict(x) for x in con.execute('SELECT * FROM sessions ORDER BY updated_at DESC LIMIT 100')]


def update_title(sid,title):
    with connect() as con:
        con.execute('UPDATE sessions SET title=?,updated_at=? WHERE id=?',(title[:75],now(),sid))


def delete_session(sid):
    with connect() as con:
        con.execute('DELETE FROM messages WHERE session_id=?',(sid,))
        con.execute('DELETE FROM tasks WHERE session_id=?',(sid,))
        con.execute('DELETE FROM sessions WHERE id=?',(sid,))


def add_message(sid,role,content,kind='text',task_id=None,sources=None):
    mid=uid()
    with connect() as con:
        con.execute('INSERT INTO messages VALUES (?,?,?,?,?,?,?,?)',(mid,sid,role,content,kind,task_id,json.dumps(sources or []),now()))
        con.execute('UPDATE sessions SET updated_at=? WHERE id=?',(now(),sid))
    return mid


def list_messages(sid):
    with connect() as con:
        res=[dict(r) for r in con.execute('SELECT * FROM messages WHERE session_id=? ORDER BY created_at,id',(sid,))]
    for r in res:r['sources']=json.loads(r['sources'])
    return res


def create_task(sid,url,prompt,max_pages,plan=None):
    tid=uid()
    with connect() as con:
        con.execute('INSERT INTO tasks(id,session_id,url,prompt,max_pages,status,created_at,plan) VALUES (?,?,?,?,?,?,?,?)',
                    (tid,sid,url,prompt,max_pages,'queued',now(),json.dumps(plan or {})))
    return tid


def task(tid):
    with connect() as con:
        r=row(con.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone())
    if r:
        r['logs']=json.loads(r['logs'])
        r['plan']=json.loads(r['plan'])
        r['stderr']=json.loads(r['stderr'])
    return r


def set_task(tid,**patch):
    allowed={'status','progress','logs','error','result_file','exit_code','started_at','finished_at','stderr'}
    patch={k:json.dumps(v) if k in {'logs','stderr'} else v for k,v in patch.items() if k in allowed}
    if not patch:return
    with connect() as con:
        con.execute('UPDATE tasks SET '+','.join(f'{k}=?' for k in patch)+' WHERE id=?',(*patch.values(),tid))


def last_success(sid):
    with connect() as con:
        r=row(con.execute("SELECT * FROM tasks WHERE session_id=? AND status IN ('completed','partial') ORDER BY created_at DESC LIMIT 1",(sid,)).fetchone())
    if r:
        r['logs']=json.loads(r['logs'])
        r['plan']=json.loads(r['plan'])
        r['stderr']=json.loads(r['stderr'])
    return r


def running_ids():
    with connect() as con:
        return [r[0] for r in con.execute("SELECT id FROM tasks WHERE status IN ('queued','running')")]
