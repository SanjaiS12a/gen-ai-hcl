# Implementation ledger

Plan: docs/superpowers/plans/2026-10-20-soc-copilot.md

Spec approved; user explicitly requested planning and completion of all six phases.
Implementation workspace: D:\HCL\soc-copilot, branch feat/local-soc-copilot.
Pre-flight: all tasks share backend response models; TypeScript contracts follow those exact fields.
Ruling: use 0.8B rather than 2B per user's later explicit instruction.
Ruling: evaluation labels LLM classification/severity as inherited; model owns narrative only.

## Phase evidence

1. Rules/IOCs: observed 6 failing regressions before implementation; all 7 phase tests passed after boundary/count/confidence/domain fixes.
2. SQLite/API: observed missing create_app failure, then 10 cumulative tests passed. Includes notes, ingest limits, audit, filter/page, CORS and sample reset preserving webhooks.
3. Providers: observed missing provider module, then 16 cumulative tests passed. JSON retry/fallback, cache mode separation, deadlines, serialization and MITRE canonicalization covered.
4. Scoped chat: observed missing scope module, then 30 cumulative tests passed. Full-question guard, fixed refusal without generation, six-message isolation and both injection alert contexts covered.
5. Frontend: TypeScript + production build passed. Browser verified Queue/search/lookup 1002, Detail/mock explanation/scoped chat/notes/status, History audit and Settings/rules-only explanation/report mode. Narrow viewport visually inspected; queue screenshot saved in docs/qa/queue.png. npm audit: 0 vulnerabilities after compatible lockfile updates.
6. Docs/scripts/eval: README, .env.example, Windows launchers, check_model.py and 34-case eval set/runner added. Python compileall and both PowerShell parser checks passed. Rules evaluation: 34/34 classification and 34/34 severity agreement on this synthetic regression set (9 benign). LLM fields explicitly inherited, no independent classification claim.

## Independent review and corrections

- Review found valid long evidence values could exceed fallback narrative limits. Added a failing API regression, bounded fallback summary, suite green.
- Review found benign-context wording downgraded confirmed ransomware. Added a failing regression and restricted benign lowering to eligible non-critical cases.
- Review found an in-flight request could repopulate samples after reset. Added a failing chat/explain race regression and atomic revision checks; stale requests return 409 without restoring history/cache.
- Added strict whitespace-output validation and provider local-files/load-once tests. Final cumulative backend suite: 37 passed in both development runtime and clean .venv using requirements-test pins; clean environment has no Torch/Transformers.
- Final reviewer independently reran all 37 tests and confirmed the three backend corrections. Its remaining notes-save race was fixed by disabling the editor during the pending save; the successful save therefore cannot label newer edits as persisted. Frontend rebuilt after this correction. No material review finding remains deferred.
- A final deterministic-evidence regression reproduced empty fields borrowing the following line. Evidence patterns now use horizontal whitespace and ignore empty values. Final suite: 38 tests passing in the pinned, model-free environment.

## Hardware evidence and limits

Attempted offline real Qwen3.5-0.8B load with installed Transformers 5.13.1 / Torch 2.13.0+cpu. The supported class reached safetensors loading but Windows returned OSError 1455 (paging file/commit limit). No successful real inference, speed, loaded-model peak RAM or adversarial output behavior is claimed. Mock/rules integration is verified. Memory settings were not changed.

Ruling: model contexts that still exceed 4096 tokens after character/field bounds fall back to rules rather than silently deleting more context; this costs model coverage on long/unusual-token inputs and preserves the server's memory budget.
Ruling: no additional GPU/fast-kernel dependencies or memory-setting changes were introduced; actual CPU speed and available memory must be checked on the user's laptop.

The branch is preserved for review; no remote push, publication or merge has been performed.
