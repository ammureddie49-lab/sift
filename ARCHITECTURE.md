# Architecture and engineering decisions

## Execution sequence

1. Browser calls `POST /api/plan` with the natural-language request and bounded page count; the user approves a constrained plan and `POST /api/execute` starts the CLI. Legacy `/api/chat` does not start any crawl without explicit approval.
2. `find_url` extracts an HTTP(S) target; `interpret_intent` determines the approved action and requested output modes.
3. `validate_url` rejects unsafe schemes, credentials, disallowed ports, private/reserved IPs and unsafe DNS responses. Invalid requests become visible chat errors rather than jobs.
4. The backend persists a queued job to SQLite and schedules `run_cli` under a concurrency semaphore.
5. `run_cli` constructs a fixed argument list with `sys.executable`, `-m`, `app.crawler` and typed flags. It invokes **`subprocess.Popen via asyncio.to_thread(*argv)`**, deliberately not `shell=True` or model-authored code.
6. The worker requests robots.txt, checks restrictions, traverses same-host HTML pages within page/depth/size/time limits, and emits newline-delimited JSON progress events on `stdout`.
7. FastAPI concurrently reads `stdout` and `stderr`, waits for process termination with a job timeout, stores events, captures the exit code, validates the JSON artifact and marks the task completed, partial, failed or canceled.
8. The browser polls task state at a short interval, reflecting real progress and final results. A separate `GET /api/tasks/{id}/trace` provides the command representation, stdout event list and exit code. Download returns the actual artifact.
9. The user can ask grounded follow-ups about the most recent successful crawl. Optional LLM is configured by environment only, with a deterministic evidence-search fallback.

## Data model

`Session(id,title,created_at,updated_at)` → many `Message(id,session_id,role,kind,content,task_id,sources)` → optional `Task(id,session_id,url,prompt,max_pages,status,progress,logs,error,result_file,exit_code,started_at,finished_at)`.

One task has one approved JSON output file. The path is checked to remain inside the approved results directory before it is read or downloaded.

## Trust boundaries

- Prompt text is never evaluated as code. User controls only validated data arguments.
- HTTP response bodies are untrusted and enter extraction only; HTML scripts are not executed by the crawler.
- The frontend escapes extracted text and enforces http/https for generated source links.
- Cross-host redirect targets are refused; path restrictions apply before and after redirects.
- Network-host validation is repeated for each fetch and redirect, but **DNS rebinding is a residual risk** without request-time IP pinning. This is a local hackathon prototype, not a hardened remote scraping service.
- API key is read server-side from `.env`; it is not returned to the frontend.

## Why Python + a simple frontend?

Python provides a directly demonstrable, reproducible CLI process and easy validation/HTML parsing without requiring judges to install both Node and Python. FastAPI handles concurrent I/O, OpenAPI docs and request validation. A vanilla JavaScript client keeps the install small and the code auditable. A CSS 3D transform stack plus depth-projected Canvas nodes provides real interactive 3D motion without an extra external 3D library or a remote CDN dependency. This keeps the *real process execution* prominent instead of hiding it behind an overcomplicated agent framework.

## Data authenticity

Crawl status and metrics are derived from actual HTTP exchanges. The report's sentences are extractive from fetched HTML metadata and body text; no fake progress steps or hard-coded results exist in the operational path. An offline fixture website is provided for reproducible live HTTP demonstrations. The aesthetic three-dimensional illustration is UI-only, and does not impersonate evidence.

## Potential extensions after hackathon

- Containerized workers with OS-level network and filesystem policies
- Verified DNS resolution / connect-to-IP pinning
- Authentication, rate limiting, quotas, observability and distributed task queue
- Headless browser for JS-rendered pages when explicitly allowed
- LLM structured-intent parsing with typed JSON-schema outputs and strict allowlisting
- Side-by-side version comparison, citation-level confidence, evidence highlights
