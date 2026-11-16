# Sift Orbit — BuildSprint upgrade highlights

This release extends Sift Studio specifically for the BuildSprint Round 2 **CLI-Driven AI Chat Execution for Complex Tasks** brief. All execution results come from actual approved Python CLI processes, not from the animations or a fabricated report.

## From the earlier Sift Studio release

1. **New interactive design**: Rebuilt as **Sift Orbit**, with a distinctive dark-navy / lime editorial product interface, custom CSS surfaces, orbitable 3D Canvas hero, drag-to-rotate, mouse-wheel zoom, and responsive layout. The atlas is a real depth-projected 3D scene, implemented in Canvas without requiring WebGL/CDN downloads.
2. **Plan before execution**: `POST /api/plan` returns a constrained, editable, typed task plan without running a process. The UI asks users to approve the target, extraction fields, bounds, and crawl permission before invoking `POST /api/execute`.
3. **Extraction Studio**: Approved fields include name, description, services, products, pricing, email, phone, location, team, FAQ, technology and social links. Each extracted value includes source evidence; unsupported fields return `null` rather than guessed data.
4. **3D Crawl Atlas**: Real discovered pages and internal hyperlinks drive the nodes and edges. Drag to orbit, zoom, click nodes to inspect the source, reset, or switch to 2D. A textual accessible page listing accompanies the canvas.
5. **Evidence Lens**: Source-backed highlights and extracted fields show source URLs and excerpts. An evidence-passport JSON download captures execution metadata and artifact checksum.
6. **Execution Theatre**: Replay **recorded** stdout events along a timeline, inspect allowed CLI argv, stderr (redacted), status, exit code, and cancellation. Replay does not re-run the CLI.
7. **Two-site comparison**: A comparison plan launches two independently bounded CLI processes; only their actual validated output may contribute to the side-by-side comparison and JSON export.
8. **Security and correctness**: Explicit approval, allowlisted tool/fields, HTTPS/HTTP address checks, per-request IP pinning, conservative robots policy, redirect checks, crawl limits, content size caps, schema validation, external-link counting fix and error transparency.
9. **Extra usability**: Voice-input fallback in supported browsers, printable report, saved sessions and source search.

## What it is not

- The deterministic intent parser is **not** a generative agent. The optional LLM is for evidence-grounded follow-up Q&A only; core crawling, extraction and planning need no API key.
- Extractors use conservative HTML/text rules and cannot guarantee arbitrary fields are found on every website. Missing or blocked information must stay missing.
- The 3D Atlas is a perspective Canvas visualization of the crawl graph, **not** a WebGL game or a full immersive VR engine.
- The included demo site is a local fixture served via real HTTP, not an online deployment. Public websites must allow access and can be unreachable.
- User accounts, multi-tenant isolation and hosted production-grade hardening are out of scope for this local hackathon prototype.
- The submission video and form submission cannot be completed by the source ZIP and must be done separately.

## Recommended 4–7 minute video sequence

1. Show natural-language request and the editable plan **before** execution; explain that it triggers no CLI until approved.
2. Approve a crawl and show the live stdout execution panel, worker status and actual CLI exit code.
3. Open the **Extraction**, **3D Atlas**, **Evidence Lens**, **JSON**, and **CLI Replay** tabs; drag and click a source node.
4. Demonstrate the two-site comparison (can use the local fixture homepage and about page as separate targets).
5. Show an invalid/private URL rejection or cancellation, the tested safeguards, architecture and AI-tool disclosures.

Run instructions are in `RUN_ME_FIRST.md`; technical details in `ARCHITECTURE.md`.
