# Sift Orbit — Windows subprocess hotfix

## Symptom
The application displays `Execution failure: NotImplementedError` and the CLI trace shows `0/0 events` with no crawl result.

## Cause
When Uvicorn runs with `--reload` on Windows, the event loop can be a selector loop, which does not support `asyncio.create_subprocess_exec`. The old backend attempted that operation before the crawler started. This was a bug in the shipped application, not a problem with the website.

## Fix
`app/main.py` now starts the **same approved Python CLI** using `subprocess.Popen` inside `asyncio.to_thread()`. It reads both stdout and stderr asynchronously via worker threads, monitors the real exit code, and retains timeouts and cancellation. There is no shell invocation, and all argv values remain validated/allowlisted.

## Update existing installation
1. Stop the old server using **Ctrl+C** in the terminal. If it doesn't stop, close the terminal.
2. Extract this updated ZIP. Open its `Sift_Orbit` directory (the folder with `requirements.txt`) in VS Code.
3. From PowerShell in that directory:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

4. Hard-refresh the website using **Ctrl+Shift+R**.
5. Start a **new** crawl (failed tasks from the old version will remain failed in history).

If port 8000 is already being used, close the earlier Uvicorn server; don't run two copies against the same directory at once.

## Minimal patch alternative
If you want to preserve your local SQLite history, copy the updated `app/main.py` over your previous `app/main.py`, stop and restart Uvicorn, and start a new task. No database migration is required.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

This package adds a regression test that deliberately makes `asyncio.create_subprocess_exec` raise `NotImplementedError` and checks that the real CLI still completes with captured stdout and a saved result.
