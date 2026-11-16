# BuildSprint 2026 — 4–7 minute demonstration guide

The challenge requires **a real demonstration video**. This is a script and checklist, not a video file. Speak naturally and show your own running application; use your own words rather than reading everything verbatim.

## Prepare before recording

1. In VS Code, open the extracted project. Run the 21 automated tests. Start two terminals for the fully reproducible local HTTP demonstration (`README.md` §2).
2. Make sure the frontend opens at `http://127.0.0.1:8000` and the demo website at `http://127.0.0.1:8765`.
3. Start with a clean research session using **New research**. Increase browser zoom if necessary so logs and JSON are readable. Screen-record at a reasonably high resolution.
4. Set `ALLOW_PRIVATE_NETWORK=true` **only** for this local fixture demo. Mention that private hosts are blocked in normal mode.
5. Optional: public `https://example.com` test is permitted when the real site is reachable, but a website may change or block crawling. The local four-page test site demonstrates the same real HTTP and subprocess behavior without relying on outside uptime.

## Suggested recording flow (about 5:30)

### 0:00–0:35 — Problem and solution

"The challenge is not to make another chatbot that writes commands. We need a conversational system that actually executes CLI work, captures what happens and returns trustworthy results. I built Sift Studio, a website intelligence workspace that turns a request into a bounded crawler job with verifiable evidence."

Show the clean research landing screen and pointer-responsive 3D website cards for a few seconds. Avoid spending too long on aesthetics.

### 0:35–1:20 — Architecture

Click **Behind the scenes**. Walk through the real sequence: prompt → intent → validation → approved `app.crawler` subprocess → stdout/stderr/exit-code capture → JSON artifact → grounded report. Mention that no API key is needed and the CLI is not a generic shell.

Show `app/main.py` around `create_subprocess_exec` and `app/crawler.py` around `emit`/`crawl` for 5–10 seconds each.

### 1:20–3:30 — Mandatory live task

Enter this exact prompt and hit Enter:

```text
Crawl http://127.0.0.1:8765, extract the important information,
give me a summary, and return the extracted data in JSON format.
```

Watch the worker status, pipeline and **Live activity** panel update. Explain that logs are coming from the spawned Python process, not a frontend animation.

When complete: show actual page and word counts. Open **Overview** for grounded content, **Source pages** for page titles and source links, **JSON** to show valid structured output, then **Download** the artifact. Open **Task plan** to show intent and approved tool selection, and **CLI trace** to show stdout and exit code 0.

### 3:30–4:15 — Follow-up intelligence

Click a follow-up suggestion like **What is this site about?** or type your own question. This answer is grounded only in data retrieved by the earlier run, with source links. No LLM key is required.

### 4:15–5:00 — Security and errors

On the default secure configuration, loopback, private addresses and nonstandard ports are blocked. For a demonstrable error without changing the local-demo setting, use a clearly invalid URL such as `file:///etc/passwd` or a malformed hostname and explain that only approved website HTTP(S) operations are allowed. Alternatively explain the failure response for robots.txt denial or a network timeout.

Show the **Stop run** control if you have a longer-running real website crawl. Explain the difference between completed, partial, failed and canceled states.

### 5:00–5:45 — Wrap up and stack

"The core run uses FastAPI, HTTPX, BeautifulSoup, a Python CLI subprocess, SQLite for durable logs, and vanilla JavaScript for the interface. The 3D scene is a responsive CSS-depth and Canvas visualization. ChatGPT helped with code and UI development; the crawler and analysis run locally without an LLM. The design prioritizes real execution, correctness, visibility and security rather than generated text that merely looks plausible."

Conclude with the actual application, not a slide. Do not claim any feature or testing result you haven't verified yourself.

## Record-and-submit checks

- Capture your own screen and voice; ensure both prompt and live JSON are legible.
- Show at least one **fresh** execution, not just saved historical reports.
- Make clear the example website is a fixture but the HTTP fetch and subprocess are real.
- Include technology and AI-service disclosure.
- Provide a repository or source package, README and one recording link/file as requested by organizers.
