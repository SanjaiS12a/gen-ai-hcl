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

Initial offline Qwen3.5-0.8B loading with Transformers 5.13.1 / Torch 2.13.0+cpu failed with Windows OSError 1455 (paging file/commit limit). The local-model correction below supersedes that initial loading limitation. Memory settings were not changed.

Ruling: model contexts that still exceed 4096 tokens after character/field bounds fall back to rules rather than silently deleting more context; this costs model coverage on long/unusual-token inputs and preserves the server's memory budget.
Ruling: no additional GPU/fast-kernel dependencies or memory-setting changes were introduced; actual CPU speed and available memory must be checked on the user's laptop.

The branch is preserved for review; no remote push, publication or merge has been performed.

## Genuine local-model correction (2026-10-20)

- Persisted the local runtime configuration: Transformers provider, downloaded Qwen3.5-0.8B directory, offline flags, 300-second deadline, 400-token output cap, four CPU threads. Browser rules-only mode is disabled. The first successful explanation used a 256-token cap; longer chat required the larger allowance.
- The supported `disable_mmap=True` loading option bypasses the observed Windows mapping error. Optional layer-wise dynamic int8 Linear conversion uses the installed PyTorch CPU kernels without an additional model download or quantization package; this is enabled in this machine's ignored `.env`.
- Reproduced copied-input and extra-closing-brace failures with actual generated output. Moved schema instructions after delimited untrusted data, used an assistant JSON prefill with thinking disabled, and stopped generation at a complete JSON object. Only one redundant closing brace is normalized; field validation remains strict.
- A real POST explanation for ALR-1002 returned `engine=llm`, `provider=transformers`, `fallback_reason=null`, model `D:\HCL\models\Qwen3.5-0.8B`, and `generation_ms=151646`. The browser displayed that saved explanation with the Local AI badge, verification checkboxes, and three numbered next steps.
- The 0.8B response remained basic and misdescribed the sender email as a target. Schema validation establishes structure, not factual correctness. Original alert evidence remains visible and model output still requires analyst review; no adversarial-output robustness claim is made.
- Health now exposes loading errors and generation token progress. Added the question chip "How do I resolve this alert step by step?" and corresponding scope tests.
- Independent review reproduced a debug-only unbound-variable exception when a provider raises ValueError. A failing regression was observed and the variable is initialized on each attempt.
- Actual chat generations also reproduced split JSON objects, repeated examples, and overstated compromise. Added compact JSON token constraints through LM Format Enforcer's public core APIs, removed example answer phrases, placed current alert data after untrusted history, and strengthened the conditional-evidence instructions. Placeholder advice now triggers retry/fallback instead of being accepted as model advice. These controls improve format and prompt guidance; they do not prove factual accuracy.
- The new grammar tests block premature object closure and a second object, and verify the assistant prefill matches the schema. Independent read-only review found no material issue with the tokenizer adapter or constraint integration. The placeholder regression failed before the fix and passes afterward. Final cumulative backend suite: 49 passed. The TypeScript check and production build also pass.
- One later cold start exited during loading under Windows memory pressure. Switched to the officially documented `Qwen3_5ForCausalLM` and `Qwen3_5TextConfig` text-only loader, using the built-in checkpoint key conversion and requiring no missing/mismatched text weights. The real loader read 320 text tensors rather than instantiating the full vision model's 473 tensors and reached ready. Process working set observed after load: 1.04 GiB, peak 2.87 GiB; these are one-run process observations, not whole-system guarantees.
- Final text-only explanation with the revised prompt and JSON constraints returned real `engine=llm`, `provider=transformers`, no fallback, two verification checks, and three concrete response steps in 206230 ms including cold loading/filter preparation. Saved response: docs/qa/local-model-response.json. The answer still misidentified the username as an email address, illustrating the 0.8B model's factual limitations. Failed agent-created runtime-check messages were removed from the disposable browser-test database; original history, alert, notes, and status were preserved.
- Final warm-model step-by-step chat returned `engine=llm`, `provider=transformers`, no fallback, verification checks and three numbered actions in approximately 90.8 seconds. Verified the Local AI badge and full steps in the browser. Saved evidence: docs/qa/local-ai-step-by-step.png and docs/qa/local-model-chat-response.json. Some narrative still overgeneralizes the evidence; the UI's verification warning remains important. Backend left running with this real model loaded and diagnostic output logging disabled. Final independent review reported no material issue with text-only loading or the placeholder fix.
