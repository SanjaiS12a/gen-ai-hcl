# Local SOC Copilot Implementation Plan

> For agentic workers: use superpowers:executing-plans, task by task.

**Goal:** Complete all six phases of the approved local SOC copilot.
**Architecture:** Retain deterministic analysis, add SQLite persistence and bounded local generation behind a provider interface, and expose alert-scoped routes to a split React application.
**Tech Stack:** FastAPI, Pydantic, sqlite3, Transformers/PyTorch CPU, React, TypeScript, Vite, react-router-dom.
**Spec:** ../specs/2026-10-20-soc-copilot-design.md

## Global constraints

- Qwen/Qwen3.5-0.8B; MODEL_PATH supports local directory/cache; no runtime downloads.
- Python 3.11+, Node 20+, Windows 10/11, 8 GB RAM; CPU bfloat16.
- IOCs, evidence, classification, severity, MITRE are deterministic.
- No global chat, execution endpoints, cloud APIs, telemetry, or heavy additions beyond the requested inference stack.
- Generation serializes, times out cooperatively, validates JSON, retries once, and falls back.
- CORS permits only http://localhost:5173. Mock tests never require weights.

## Review focus

- Long/injection-bearing alerts: bounded context, untrusted data, no cross-alert disclosure.
- Model failure or slow generation: health/API stay responsive and fallback has honest metadata.
- Cache mode/provider changes: never serve an LLM result in rules-only mode.
- Reload samples with webhook alerts: preserve real ingests and reset only samples.
- Rapid route changes or failed saves: stale responses cannot overwrite the active alert; preserve visible errors.

### Task 1: Rule and IOC corrections
Files: backend/app/services/{analyzer,ioc}.py; backend/tests/test_rules.py.
Interface: analyze_alert(raw_alert: str) -> IncidentAnalysis; extract_iocs(raw_alert: str) -> list[Indicator].
- [x] Write regressions for boundaries, explicit attempts, unknown confidence/MITRE, generic terms, domain deduplication/TLDs.
- [x] Run `python -m pytest backend/tests/test_rules.py -q`; observe regressions fail.
- [x] Repair extraction/scoring and run the same command; expect all passing.

### Task 2: SQLite and alert API
Files: backend/app/{models,db,seed,main}.py; backend/tests/test_api.py.
Interface: create_app(db_path=None, provider=None) -> FastAPI; Store methods ingest/get/list/status/notes/stats/history/seed.
- [x] Write API tests with temporary databases; expect missing create_app failure.
- [x] Add typed alert envelopes, bounded requests, transactions and 30 seeded alerts.
- [x] Replace old global routes with requested alert CRUD/audit/export routes.
- [x] Run rule and API tests; expect all passing, including sample reload preserving webhook alerts.

### Task 3: Local provider and explanations
Files: backend/app/llm/{base,providers,copilot,mitre}.py, mitre_techniques.json; backend/tests/test_copilot.py.
Interface: Provider.generate(messages, deadline) -> str; Copilot.explain(alert, rules_only=False) -> CopilotResult.
- [x] Write strict JSON, retry, fallback, MITRE, cache identity, and deadline tests; run to observe missing implementation.
- [x] Verify official model loading/template and immutable dependency pins.
- [x] Implement mock, lazy Transformers, unavailable Ollama stub, serialization and threadpool routes.
- [x] Run backend suite; expect passing without importing Torch/model.

### Task 4: Scoped chat
Files: backend/app/llm/scope.py, copilot.py; backend/tests/test_chat.py.
Interface: in_scope(question: str, alert_id: int) -> bool; ChatResponse includes provenance.
- [x] Test refusals without provider calls, mixed intent, other IDs, last-six-message context, injection alerts and rules mode.
- [x] Run failing tests, implement guard/persistence/scoped context, rerun full backend suite.

### Task 5: Routed frontend
Files: frontend/src/{App,main,types,api,styles}, components/, pages/.
Interface: typed API responses match Pydantic; rules-only preference supplied on explain/chat requests.
- [x] Build Queue, Detail, History, Settings, shared shell and status/loading components.
- [x] Add routing and React type declarations; run `npm run build` (includes tsc).
- [x] Exercise mock-backed routes, lookup, generation/chat, notes, audit, export, and narrow layout in browser.

### Task 6: Documentation, scripts, evaluation, final verification
Files: README.md, .env.example, scripts/, backend/eval/, requirements*.txt, docs/implementation-progress.md.
Interface: PowerShell run scripts, check_model.py --model-path, run_eval.py [--llm].
- [x] Provide 30+ independently labeled evaluation cases; no independent LLM classification claim.
- [x] Run rules evaluation, backend suite, frontend build, script syntax checks and git diff --check.
- [x] Review all changed code and fix material findings with regression tests.
- [x] Record per-phase evidence, limitations and manual hardware verification checklist.

Execution is authorized for all phases by the user's explicit approval; proceed inline without further stage approvals.
