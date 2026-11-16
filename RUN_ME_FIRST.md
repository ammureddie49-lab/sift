# Run Sift Orbit (Windows — copy and paste)

Open the **Sift_Orbit** folder in VS Code and select **Terminal → New Terminal** (PowerShell).

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**.

**Challenge example:**

```text
Crawl https://example.com, extract the important information, give me a summary, and return JSON.
```

**Reliable live demo without internet:** Stop the app (`Ctrl+C`). Then use two terminals:

Terminal 1 (real test website):

```powershell
.\.venv\Scripts\python.exe -m http.server 8765 --bind 127.0.0.1 --directory demo_site
```

Terminal 2 (app, allowing loopback solely for this local test):

```powershell
$env:ALLOW_PRIVATE_NETWORK="true"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In the app, paste:

```text
Crawl http://127.0.0.1:8765, extract the important information, summarize it and return valid JSON.
```

Then inspect **Overview**, **Source pages**, **JSON**, **Task plan**, **CLI trace**, and **Download**. The locally served website is a fixture; the HTTP requests, CLI subprocess, stdout, exit status and JSON artifact are *real*.

Tests:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Read `README.md` for full setup, `DEMO_SCRIPT.md` for video instructions and `BRIEF_REQUIREMENTS.md` for direct alignment with the challenge.

## New interactive features to demonstrate

The updated Sift Orbit interface first shows an **editable execution approval dialog**. Confirm access permission to start the actual crawler. After completion open **Extraction → 3D Atlas → Evidence Lens → JSON → CLI Replay**. In the Atlas, drag to rotate, scroll to zoom, and click actual crawled pages. In CLI Replay, play or scrub the saved stdout trace; it never pretends to be a new run.

For a **comparison task**, use: `Compare http://127.0.0.1:8765/ versus http://127.0.0.1:8765/about.html and extract company name, services and email.` (Only when the local fixture server is running and `ALLOW_PRIVATE_NETWORK=true` is set locally.)
