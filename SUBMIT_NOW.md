# Sift Orbit — Submit Now (BuildSprint Round 2)

## What the screenshot means
The older failed card belongs to a previous run. The newest run marked COMPLETED is a separate successful execution; its events appear in the right-hand CLI feed. Old runs are preserved but collapsed after a later run.

## Fastest Windows setup
Open VS Code in the folder containing `app`, `web` and `requirements.txt`.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Go to http://127.0.0.1:8000 then use Ctrl+Shift+R. Press **New investigation** to avoid old failed cards.

Task: `Crawl https://example.com, summarize the important information and return valid JSON.`

Confirm permissions, approve the task plan, show the **COMPLETED** run, navigate to **Overview**, **JSON**, and **CLI Replay**. Click **Export JSON**. If `example.com` is not reachable on your internet, demonstrate the bundled site using `RUN_ME_FIRST.md`.

## Live crawl proof (without internet)
Terminal A:
```powershell
.\.venv\Scripts\python.exe -m http.server 8765 --bind 127.0.0.1 --directory demo_site
```
Terminal B:
```powershell
$env:ALLOW_PRIVATE_NETWORK='true'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Prompt: `Crawl http://127.0.0.1:8765, summarize it and return JSON.`

The loopback allowance is **for localhost demonstration only**. Do not enable it on an internet-accessible deployment.

## Must submit
1. Source ZIP or repository URL (this full source package).
2. README and configuration/run instructions (included).
3. Local live demo instructions (included).
4. **A real 4–7 minute screen recording made by you** showing planning, CLI stdout/exit, crawl, summary, JSON and an error case. The ZIP does not contain this recording.
5. Upload the links/files via the organizer's official form before the deadline.

Do not claim a remote public site was tested unless you have actually run it. The local HTTP fixture is a genuine crawler execution, not mocked results.
