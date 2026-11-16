# BuildSprint Round 2 — final checklist

## Mandatory deliverables from the challenge brief

- [ ] Submit a working Sift Studio app (running live in demo video).
- [ ] Provide full project source ZIP or Git repository URL.
- [ ] Include README with setup prerequisites, environment values, example prompts and CLI explanation.
- [ ] Include reproducible local-run instructions and/or hosted URL if available.
- [ ] **Record one 4–7 minute explanatory video showing an actual fresh crawl and its summary + JSON.**

## Before hitting record

- [ ] `python -m pytest -q` passes all checks.
- [ ] `http://127.0.0.1:8000/api/health` returns a healthy response.
- [ ] The four-page fixture website is served on `http://127.0.0.1:8765`.
- [ ] In local test mode only, the backend was launched with `ALLOW_PRIVATE_NETWORK=true`.
- [ ] The app actually creates a subprocess, captures logs and displays an exit code.
- [ ] Actual pages, summary, JSON output, file download and trace can be shown clearly.
- [ ] Explain an invalid-URL, failure, partial result or cancellation edge case.
- [ ] Disclose AI assistance and optional API services in the recording.

## Submission logistics

Original brief form: https://form.workelate.com/previewform/6af8bd0090174e8d87484e41

**Stated deadline: 16 November 2026, 11:59 PM IST.** The package does not itself submit anything or record video. Confirm any later organizer updates and upload your own recording.

## Suggested submission description

> Sift Studio is a working CLI-driven website research assistant. It converts natural-language requests into a validated crawl intent, executes a real bounded Python CLI subprocess through FastAPI, captures stdout/stderr and process status, validates a structured JSON artifact, and returns grounded summaries, source pages, quality checks, execution traces and downloadable results. It supports cancellation, safe URL restrictions, persistent chat history and a responsive interface with interactive 3D elements. The core demonstration needs no paid AI API.
