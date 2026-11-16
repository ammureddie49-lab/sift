# Sift Orbit — verification report

Latest local verification for this packaged BuildSprint upgrade:

- `python -m pytest -q` — **28 passed**, including a real locally hosted HTTP crawl through a Python CLI subprocess, approvals, 2-site comparison, structured extraction, graph links, evidence contract, JSON, and API behavior.
- `node --check web/app.js` — JavaScript syntax verified.
- `python -m compileall -q app` — Python sources compiled.
- Existing browser screenshots in `screenshots/` cover the redesign, plan approval, completed report, **interactive atlas**, extraction, CLI replay and mobile layout. The screens are reference captures, not claims of a live hosted deployment.
- Real HTTP fixture in `demo_site/` is suitable for reproducing the CLI flow offline. No public website availability or robots permission is guaranteed.

## Limitations and honest scope

The deterministic parser and HTML field extractors have bounded capabilities. The renderer uses perspective Canvas 3D (not WebGL). Authentication, external hosted deployment, a submission-form upload, and a video recording are not included. For demo reliability, run the bundled test site locally; real public websites may deny crawling.

## Windows subprocess regression fix

- The original `asyncio.create_subprocess_exec` path could raise `NotImplementedError` with Uvicorn's Windows selector event loop in reload mode.
- Updated to Python's `subprocess.Popen` in `asyncio.to_thread`, preserving separate real CLI execution, streaming stdout and stderr, cancellation and timeout.
- Added `tests/test_windows_subprocess.py`, which deliberately makes the unsupported asyncio subprocess API unavailable. The patched app still finishes a real 4-page fixture crawl and captures its exit code, events and output.
- **Verification environment:** automated tests executed on Linux with the Windows-incompatibility condition simulated; direct testing on native Windows is still recommended.

## Final audit fixes
- Added latest-run status banner and a jump-to-results action; old failed attempts collapse in completed investigations instead of appearing as the active result.
- Legacy `/api/chat` cannot invoke the crawler without approval; the tested flow is `/api/plan` then consented `/api/execute`.
- Corrected the architecture UI to describe `subprocess.Popen` in `asyncio.to_thread`.
- Asset cache busting, Windows launch instructions, and regression testing included.
