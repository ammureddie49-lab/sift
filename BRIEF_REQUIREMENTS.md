# BuildSprint Round 2 — requirements traced directly to the challenge brief

This map covers the implementation brief's **Sections 3–12**, not a generic web-app feature wishlist.

| Brief area | Exact obligation | Evidence in Sift Studio | How to show it to judges |
|---|---|---|---|
| §3 User input | Natural-language chat with URL | `web/index.html`, `web/app.js`, `POST /api/plan + /api/execute` | Submit a sentence containing the URL |
| §3 Intent understanding | Decide action, inputs and output | `app/main.py: interpret_intent`, `find_url` | Open result → **Task plan** |
| §3 Backend orchestration | Select/invoke approved CLI | `app/main.py: run_cli` | Show `create_subprocess_exec` and **CLI trace** |
| §3 Real execution | Fetch permitted live website pages | `app/crawler.py: crawl`, `safe_fetch` | Local demo site: four real HTTP requests |
| §3 Output capture | Capture stdout/stderr/status | `run_cli` readers and `exit_code`; SQLite `tasks.logs` | Execution trail and **CLI trace** |
| §3 Response | Return verified results to chat | `task_public`, task renderer | Summary, fetched sources, JSON |
| §3 Errors | Invalid, blocked, failures, timeouts | `security.py`, robots, job timeout, partial/failed statuses | Try `http://127.0.0.1` with default config |
| §4 Mandatory demo | Crawl, summary, JSON in one flow | `demo_site/` plus real process | Follow `DEMO_SCRIPT.md` |
| §5 Valid JSON | Properly named structured fields | `app/crawler.py` artifact | JSON tab → download → inspect |
| §6 CLI transparency | Tool, arguments, logs, exit, cancellation | `GET /api/tasks/{id}/trace`, POST cancel | Task plan and CLI trace |
| §7 Technology choice | Document stack and AI-assisted work | `README.md` §10 | Mention it during the video |
| §8 Security | Input validation, safe tools, bounded crawl | `security.py`, `crawler.py`, `main.py` | Briefly explain allowlist and SSRF restrictions |
| §9 Deliverables | Runnable code + instructions + video | Project ZIP, README, `DEMO_SCRIPT.md` | **User must record video** |
| §10 Video | 4–7 minute actual execution | Stepwise script | Screen-record live crawl and outcome |
| §11 Rubric | 25/20/15/15/10/10/5 marks | Technical implementation and tested UI | Demo executable evidence before UI polish |
| §12 Reject conditions | No mock crawl, no text-only LLM wrapper | Real HTTP + CLI subprocess + artifact | Show stdout, exit code and actual JSON |

## Interpretation boundaries

The prompt says "AI or intent-understanding layer" — this project uses a transparent constrained intent router by default. Optional OpenAI-compatible grounded follow-ups are available, but the core crawler does not rely on a paid model or fabricate content. It is an intentionally scoped **website research CLI agent**, not arbitrary command execution.

The provided demo website is an explicit test fixture, but the **HTTP traffic, CLI process, stdout capture and resulting artifact are real**. Public sites may refuse crawling, and Sift reports that honestly.
