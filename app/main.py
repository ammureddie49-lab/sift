"""Sift Studio: chat → validated intent → allowlisted CLI subprocess → live logs → JSON artifact."""
from __future__ import annotations
import asyncio
import json
import os
import re
import sys
import subprocess
import hashlib
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import database as db
from app.llm import answer, available
from app.security import UnsafeURL, validate_url
from app.planner import TaskPlan, plan_prompt, ALLOWED_FIELDS
from app.schemas import CrawlArtifact

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')
MAX_CONCURRENT=max(1,min(5,int(os.getenv('MAX_CONCURRENT_JOBS','2'))))
semaphore=asyncio.Semaphore(MAX_CONCURRENT)
processes:dict[str,subprocess.Popen]={}
canceled:set[str]=set()
runners:dict[str,asyncio.Task]={}
TASK_TIMEOUT=150


@asynccontextmanager
async def lifespan(app:FastAPI):
    db.init()
    # On restart, never claim previously interrupted jobs completed.
    for tid in db.running_ids():
        db.set_task(tid,status='failed',error='Server restarted before the CLI job completed.',finished_at=db.now())
    yield
    for proc in list(processes.values()):
        if proc.poll() is None:
            try:proc.terminate()
            except OSError:pass
    for running in list(runners.values()):
        running.cancel()


app=FastAPI(title='Sift Orbit API',version='3.0.0',lifespan=lifespan,docs_url='/api/docs',redoc_url=None)


class SessionInput(BaseModel):
    title:str=Field(default='New conversation',max_length=100)


class ChatInput(BaseModel):
    session_id:str=Field(min_length=1,max_length=64)
    message:str=Field(min_length=1,max_length=4000)
    url:str|None=Field(default=None,max_length=2048)
    max_pages:int=Field(default=6,ge=1,le=15)


class PlanInput(BaseModel):
    message: str=Field(min_length=1,max_length=4000)
    url: str|None=Field(default=None,max_length=2048)
    max_pages: int=Field(default=6,ge=1,le=15)
    fields: list[str]|None=None

class ExecuteInput(BaseModel):
    session_id: str=Field(min_length=1,max_length=64)
    message: str=Field(min_length=1,max_length=4000)
    plan: TaskPlan
    permission_confirmed: bool=False


def find_url(msg):
    found=re.search(r'https?://[^\s<>"\']+',msg,re.I)
    if found:return found.group(0).rstrip(').,;\'"')
    found=re.search(r'(?<![\w@])(?:www\.)?[\w-]+(?:\.[\w-]+)+(?:/[^\s<>"\']*)?',msg)
    if found:return 'https://'+found.group(0).rstrip(').,;\'"')
    return None


def interpret_intent(prompt: str, url: str | None = None) -> dict:
    """Legacy compatibility adapter; real UI uses /api/plan + /api/execute."""
    plan=plan_prompt(prompt,url)
    return {'action':plan.action,'target_url':plan.target_url,
      'requested_outputs':[x for x in plan.requested_outputs if x in ('summary','structured_json','seo_audit')],
      'tool': 'app.crawler' if plan.action in ('crawl_website','compare_websites') else 'evidence-search',
      'execution_policy':'approved-commands-only'}


def task_public(item:dict,full=False):
    doc={k:v for k,v in item.items() if k!='result_file'}
    doc['intent']=interpret_intent(item['prompt'],item['url'])
    doc['plan']=item.get('plan') or plan_prompt(item['prompt'],item['url'],item['max_pages']).model_dump()
    if full and item.get('result_file'):
        try:
            result_path=Path(item['result_file']).resolve()
            if result_path.is_relative_to((ROOT/'data'/'results').resolve()) and result_path.exists():
                contents=result_path.read_bytes()
                doc['result']=json.loads(contents)
                doc['artifact_sha256']=hashlib.sha256(contents).hexdigest()
        except (OSError,ValueError,json.JSONDecodeError):
            doc['result']=None
    return doc


async def run_cli(tid:str):
    task=db.task(tid)
    if not task:return
    async with semaphore:
        if tid in canceled:
            db.set_task(tid,status='canceled',finished_at=db.now(),error='Canceled before execution.')
            return
        output=(ROOT/'data'/'results'/f'{tid}.json').resolve()
        plan=task.get('plan') or {}
        fields=plan.get('fields',['name','description','services','products','email'])
        depth=int(plan.get('max_depth',2))
        argv=[sys.executable,'-m','app.crawler','--url',task['url'],'--max-pages',str(task['max_pages']),
              '--max-depth',str(depth),'--timeout','12','--fields-json',json.dumps(fields),'--output',str(output)]
        db.set_task(tid,status='running',started_at=db.now(),progress=2)
        logs=[];stderr=[]
        try:
            # shell=False: no user-controlled executable or arbitrary CLI flags.
            # Uvicorn --reload on Windows can use SelectorEventLoop, which does not
            # implement asyncio.create_subprocess_exec (raises NotImplementedError).
            # Popen plus asyncio.to_thread works with both Windows event loops and
            # still streams real stdout/stderr without blocking the HTTP server.
            proc=await asyncio.to_thread(
                subprocess.Popen, argv, cwd=str(ROOT),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env={**os.environ,'PYTHONUNBUFFERED':'1'},
                creationflags=(subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0),
            )
            processes[tid]=proc

            async def stdout_reader():
                while True:
                    b=await asyncio.to_thread(proc.stdout.readline)
                    if not b:break
                    try:
                        event=json.loads(b.decode('utf-8',errors='replace'))
                        if event.get('event')!='progress':continue
                        event={k:event.get(k) for k in ('event','at','step','message','progress','level','url') if k in event}
                        event['message']=str(event.get('message',''))[:400]
                    except (ValueError,AttributeError):
                        event={'event':'progress','step':'output','level':'info','message':'Worker emitted non-JSON status.','progress':logs[-1].get('progress',0) if logs else 0}
                    logs.append(event)
                    db.set_task(tid,logs=logs[-120:],progress=int(event.get('progress') or 0))

            async def stderr_reader():
                while True:
                    b=await asyncio.to_thread(proc.stderr.readline)
                    if not b:break
                    if len(stderr)<30:
                        line=b.decode('utf-8','replace')[:250].strip()
                        line=re.sub(r'(?i)(api[_-]?key|password|bearer|token)[=: ]+[^\s]+',r'\1=[REDACTED]',line)
                        stderr.append(line)
                        db.set_task(tid,stderr=stderr)

            await asyncio.wait_for(asyncio.gather(
                stdout_reader(), stderr_reader(), asyncio.to_thread(proc.wait)
            ), timeout=TASK_TIMEOUT)
            exit_code=proc.returncode
            db.set_task(tid,exit_code=exit_code)
            if tid in canceled:
                db.set_task(tid,status='canceled',error='Canceled by user.',finished_at=db.now(),stderr=stderr)
            elif output.exists():
                artifact=json.loads(output.read_text(encoding='utf-8'))
                status=artifact.get('status','failed')
                if exit_code!=0 or status=='failed':
                    db.set_task(tid,status='failed',error=str(artifact.get('error') or 'CLI process reported failure.'),result_file=str(output),finished_at=db.now(),progress=100)
                elif status in {'completed','partial'}:
                    try: CrawlArtifact.model_validate(artifact)
                    except ValueError:
                        db.set_task(tid,status='failed',error='Worker JSON did not satisfy the validated result/evidence contract.',finished_at=db.now(),progress=100)
                    else: db.set_task(tid,status=status,result_file=str(output),finished_at=db.now(),progress=100)
                else:
                    db.set_task(tid,status='failed',error='CLI output did not match the expected success schema.',finished_at=db.now())
            elif tid in canceled:
                db.set_task(tid,status='canceled',error='Canceled by user.',finished_at=db.now())
            else:
                db.set_task(tid,status='failed',error=f'CLI produced no result file (exit {exit_code}). '+(' '.join(stderr)[:180] if stderr else ''),finished_at=db.now(),progress=100)
        except asyncio.TimeoutError:
            proc=processes.get(tid)
            if proc and proc.poll() is None:
                proc.kill()
                await asyncio.to_thread(proc.wait)
            db.set_task(tid,status='failed',error=f'Execution exceeded {TASK_TIMEOUT} seconds and was stopped.',finished_at=db.now(),progress=100)
        except asyncio.CancelledError:
            proc=processes.get(tid)
            if proc and proc.poll() is None:
                proc.kill()
                await asyncio.to_thread(proc.wait)
            raise
        except Exception as exc:
            db.set_task(tid,status='failed',error='Execution failure: '+type(exc).__name__+' (check Python CLI availability and server console).',finished_at=db.now(),progress=100,stderr=stderr)
        finally:
            proc=processes.get(tid)
            if proc:
                for stream in (proc.stdout, proc.stderr):
                    if stream:
                        try: stream.close()
                        except OSError: pass
            processes.pop(tid,None)
            runners.pop(tid,None)


@app.get('/api/health')
async def health():
    return {'status':'ok','version':'3.0.0','llm_enabled':available(),'engine':'OpenAI-compatible grounded Q&A' if available() else 'Built-in evidence search (no key needed)','cli':'app.crawler','job_limit':MAX_CONCURRENT,'fields':ALLOWED_FIELDS,'planner':'deterministic constrained planner','graph':'interactive 3d canvas'}


@app.get('/api/sessions')
async def sessions():
    return {'sessions':db.list_sessions()}


@app.post('/api/sessions')
async def new_session(payload:SessionInput):
    return db.create_session(payload.title)


@app.get('/api/sessions/{sid}')
async def session_messages(sid:str):
    session=db.get_session(sid)
    if not session:raise HTTPException(404,'Conversation not found.')
    return {'session':session,'messages':db.list_messages(sid)}


@app.delete('/api/sessions/{sid}')
async def remove_session(sid:str):
    if not db.get_session(sid):raise HTTPException(404,'Conversation not found.')
    with db.connect() as con:
        active=[r[0] for r in con.execute("SELECT id FROM tasks WHERE session_id=? AND status IN ('queued','running')",(sid,))]
    for tid in active:
        canceled.add(tid)
        if (proc:=processes.get(tid)) and proc.poll() is None:proc.terminate()
    db.delete_session(sid)
    return {'deleted':True}


@app.post('/api/plan')
async def prepare_plan(payload:PlanInput):
    """Read-only planning: absolutely no CLI process is started here."""
    plan=plan_prompt(payload.message,payload.url,payload.max_pages,payload.fields)
    if plan.target_url and plan.action in ('crawl_website','compare_websites'):
        try:
            plan.target_url=validate_url(plan.target_url)
            if plan.comparison_url:plan.comparison_url=validate_url(plan.comparison_url)
        except UnsafeURL as exc:raise HTTPException(422,str(exc)) from exc
    return {'plan':plan.model_dump(),'field_catalog':ALLOWED_FIELDS,'executed':False}

@app.post('/api/execute')
async def execute_approved_plan(payload:ExecuteInput):
    """User-approved, server-revalidated plan; no raw model/shell invocation."""
    if not db.get_session(payload.session_id):raise HTTPException(404,'Conversation not found.')
    if not payload.permission_confirmed:raise HTTPException(422,'Confirm that you are permitted to crawl the selected public website(s).')
    plan=payload.plan
    if plan.action not in ('crawl_website','compare_websites'):
        raise HTTPException(422,'This plan does not authorize a crawl.')
    if not plan.target_url:raise HTTPException(422,'Plan needs a URL.')
    try:
        urls=[validate_url(plan.target_url)]
        if plan.action=='compare_websites':
            if not plan.comparison_url:raise HTTPException(422,'Comparison requires two websites.')
            urls.append(validate_url(plan.comparison_url))
    except UnsafeURL as exc:raise HTTPException(422,str(exc)) from exc
    if len(set(urls))!=len(urls):raise HTTPException(422,'Comparison URLs must differ.')
    db.add_message(payload.session_id,'user',payload.message)
    if len([m for m in db.list_messages(payload.session_id) if m['role']=='user'])==1:
        db.update_title(payload.session_id,('Compare: ' if len(urls)==2 else 'Research: ')+urlparse(urls[0]).hostname)
    ids=[]
    for url in urls:
        local=plan.model_copy(update={'target_url':url,'comparison_url':None,'action':'crawl_website'})
        tid=db.create_task(payload.session_id,url,payload.message,plan.max_pages,local.model_dump())
        db.add_message(payload.session_id,'assistant','Approved CLI crawl; output is generated from actual fetched HTML.','task',tid)
        runners[tid]=asyncio.create_task(run_cli(tid));ids.append(tid)
    return {'kind':'comparison' if len(ids)==2 else 'task','task_ids':ids,'task_id':ids[0],
            'plan':plan.model_dump(),'approved':True}

@app.get('/api/compare')
async def compare_results(left: str,right: str):
    """Evidence-only comparison of two completed, verified crawls."""
    runs=[db.task(i) for i in (left,right)]
    if not all(r and r['status'] in ('completed','partial') and r.get('result_file') for r in runs):
        raise HTTPException(409,'Both approved CLI crawls must complete before comparison.')
    if runs[0]['session_id']!=runs[1]['session_id']:
        raise HTTPException(422,'Comparison tasks must belong to the same research session.')
    data=[]
    for t in runs:
        path=Path(t['result_file']).resolve()
        if not path.is_relative_to((ROOT/'data'/'results').resolve()):raise HTTPException(404,'Invalid artifact path.')
        data.append(CrawlArtifact.model_validate_json(path.read_bytes()))
    by=[]
    for d in data:by.append({f.field:f for f in d.extraction})
    catalog=list(dict.fromkeys([*by[0],*by[1]]))
    rows=[]
    for field in catalog:
        rows.append({'field':field,'label':ALLOWED_FIELDS.get(field,field),
          'left':by[0][field].model_dump() if field in by[0] else None,
          'right':by[1][field].model_dump() if field in by[1] else None})
    return {'status':'completed','method':'Two independently executed CLI crawls; evidence-only field comparison',
      'left':{'task_id':left,'url':runs[0]['url']},'right':{'task_id':right,'url':runs[1]['url']},'rows':rows}

@app.post('/api/chat')
async def chat(payload:ChatInput):
    if not db.get_session(payload.session_id):raise HTTPException(404,'Conversation not found.')
    msg=payload.message.strip()
    if not msg:raise HTTPException(422,'Message cannot be blank.')
    db.add_message(payload.session_id,'user',msg)
    messages=db.list_messages(payload.session_id)
    if len([m for m in messages if m['role']=='user'])==1:
        db.update_title(payload.session_id,re.sub(r'https?://','',msg)[:44])
    url=payload.url.strip() if payload.url else find_url(msg)
    if url and plan_prompt(msg,url).action not in ('no_action','answer_from_evidence'):
        try:
            url=validate_url(url)
        except UnsafeURL as exc:
            content=f"I couldn't start this task: **{exc}** Please provide a public HTTP(S) website that permits crawling."
            db.add_message(payload.session_id,'assistant',content)
            return {'kind':'text','content':content}
        content=('The URL is valid, but execution was not started. For safety, use the app’s ' 
                 '**Review Plan → Approve & Execute** workflow to explicitly authorize a real CLI crawl.')
        db.add_message(payload.session_id,'assistant',content)
        return {'kind':'text','content':content,'approval_required':True}
    previous=db.last_success(payload.session_id)
    if previous and previous.get('result_file'):
        try:
            data=json.loads(Path(previous['result_file']).read_text(encoding='utf-8'))
            response=await answer(msg,data)
            db.add_message(payload.session_id,'assistant',response['text'],'text',sources=response['sources'])
            return {'kind':'text',**response}
        except (ValueError,OSError):pass
    content=('I can crawl a public website and return **real page content, a grounded summary, structured JSON, SEO checks, and source links**. '
             'Try: **“Crawl https://example.com, summarize it, and give me the data as JSON.”** '
             'After a successful crawl, ask follow-up questions about the extracted pages.')
    db.add_message(payload.session_id,'assistant',content)
    return {'kind':'text','content':content}


@app.get('/api/tasks/{tid}')
async def get_task(tid:str):
    value=db.task(tid)
    if not value:raise HTTPException(404,'Task not found.')
    return task_public(value,full=True)


@app.post('/api/tasks/{tid}/cancel')
async def cancel(tid:str):
    t=db.task(tid)
    if not t:raise HTTPException(404,'Task not found.')
    if t['status'] not in ('queued','running'):
        return {'status':t['status'],'message':'Task already finished.'}
    canceled.add(tid)
    proc=processes.get(tid)
    if proc and proc.poll() is None:
        try:proc.terminate()
        except OSError:pass
    db.set_task(tid,status='canceled',error='Canceled by user.',finished_at=db.now())
    return {'status':'canceled'}


@app.get('/api/tasks/{tid}/download')
async def download(tid:str):
    t=db.task(tid)
    if not t or not t.get('result_file'):raise HTTPException(404,'No result artifact available for this task.')
    path=Path(t['result_file']).resolve()
    if not path.is_relative_to((ROOT/'data'/'results').resolve()) or not path.is_file():
        raise HTTPException(404,'Result artifact not found.')
    return FileResponse(path,media_type='application/json',filename=f'sift-research-{tid}.json')


@app.get('/api/tasks/{tid}/trace')
async def trace(tid:str):
    t=db.task(tid)
    if not t:raise HTTPException(404,'Task not found.')
    plan=t.get('plan') or {}
    return {'task_id':tid,'status':t['status'],'command':['python','-m','app.crawler','--url',t['url'],'--max-pages',str(t['max_pages']),'--max-depth',str(plan.get('max_depth',2)),'--timeout','12','--fields-json',json.dumps(plan.get('fields',[])),'--output','<approved results path>'],
            'stdout_events':t['logs'],'stderr':t.get('stderr',[]),'exit_code':t['exit_code'],'error':t['error'],
            'started_at':t['started_at'],'finished_at':t['finished_at'],'plan':plan}

app.mount('/',StaticFiles(directory=str(ROOT/'web'),html=True),name='web')
