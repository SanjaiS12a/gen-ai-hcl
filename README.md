# Local SOC Incident-Response Copilot

A Windows-friendly, local alert triage workspace. Look up `1002` or `ALR-1002`, review evidence, request an explanation, ask a follow-up about that alert, record notes/status, and export a Markdown incident report. The copilot recommends actions; **nothing in this application executes a response action**.

**The demo feed is simulated.** SQLite starts with 30 fictional alerts covering seven incident types, benign cases, and two malicious instruction-injection email bodies. This is not a SIEM and does not collect live security telemetry. A local `POST /api/alerts` webhook permits later SIEM integration.

## What uses the model

| Capability | Implementation |
| --- | --- |
| IOC extraction and structured evidence | Deterministic Python |
| Incident type, severity, confidence, MITRE candidates | Rule-based; not independent AI findings |
| Summary, why it matters, verify-first checklist, next steps, optional false-positive estimate | Local Qwen narrative; strict JSON/Pydantic validation |
| Missing model, timeout, invalid JSON after one retry | Rule-based explanation with fallback reason |
| Scoped chat | Server-side question guard, selected alert only, last six stored messages; local model or rule fallback |
| Notes, status/audit, cache, report | SQLite and Python |

Every explanation/chat response includes engine, provider, model, and generation time. `engine=llm, provider=mock` means a deterministic test double, **not real inference**. MITRE candidates are checked against a small bundled technique catalog; they are not a complete ATT&CK analysis. IOCs are syntactic extracts, not reputation findings.

Runtime is local-only: no cloud API, telemetry, external assets, remote code, online enrichment, or automatic model downloads. Package installation and the explicit model download below need internet access. Data stays in the local SQLite file. Anyone with access to this computer/database can read it: this single-user local demo has no authentication, encryption, or production deployment controls.

## Windows setup

Use Python 3.11+ and Node 20+ (Node 20.19+ for Vite 7). Python 3.13 and Node 24 were used during development. Run commands from this repository's root in PowerShell.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
# CPU wheel; no NVIDIA/ROCm packages are needed.
.\.venv\Scripts\python.exe -m pip install torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
cd frontend
npm ci
cd ..
```

Dependencies are explicit, not installed by the run scripts. If this machine already has the downloaded model at `D:\HCL\models\Qwen3.5-0.8B`, no additional model download is necessary. Otherwise install the Hub CLI and explicitly download:

```powershell
.\.venv\Scripts\python.exe -m pip install "huggingface_hub[cli]"
.\.venv\Scripts\hf.exe download Qwen/Qwen3.5-0.8B --local-dir D:\HCL\models\Qwen3.5-0.8B
```

If your Hub package says the `cli` extra is unnecessary, install `huggingface_hub` directly; it includes `hf`. If Xet transfer stalls, retry with `$env:HF_HUB_DISABLE_XET='1'` before running `hf download`. A checksum check is available through `hf cache verify Qwen/Qwen3.5-0.8B --local-dir D:\HCL\models\Qwen3.5-0.8B --fail-on-missing-files`.

Edit `.env` to match your machine:

```dotenv
MODEL_PATH=D:\HCL\models\Qwen3.5-0.8B
LLM_PROVIDER=transformers
DB_PATH=data/copilot.db
MAX_NEW_TOKENS=400
GENERATION_TIMEOUT=90
TORCH_THREADS=4
HF_HUB_OFFLINE=1
HF_HUB_DISABLE_TELEMETRY=1
DO_NOT_TRACK=1
```

`MODEL_PATH` defaults to `Qwen/Qwen3.5-0.8B` and can identify an existing HF cache entry. All model/tokenizer loads specify `local_files_only=True`, even without `HF_HUB_OFFLINE`. The `.env` file is read by the backend PowerShell launcher. Direct Python/uvicorn commands require you to set the environment variables yourself.

In two terminals:

```powershell
.\scripts\run_backend.ps1
```

```powershell
.\scripts\run_frontend.ps1
```

Open [http://localhost:5173](http://localhost:5173). The API binds to loopback port 8000. CORS permits exactly `http://localhost:5173`, so use that frontend URL rather than `127.0.0.1:5173`. `/health` reports provider/model state without loading the model. `not_loaded` is normal until the first explanation or permitted chat request.

For a model-free demo set `LLM_PROVIDER=mock` in `.env` and restart the backend. The Settings switch selects rules-only mode for this browser's explanation/chat/report requests. It does not unload an already loaded model. `LLM_PROVIDER=ollama` is an unavailable stub; it makes no HTTP calls and falls back to rules. Provider/model changes require a backend restart.

## Model compatibility and hardware limits

The target is **Qwen3.5-0.8B**, replacing the original brief's 2B target at the user's request. The downloaded revision was `2fc06364715b967f1860aea9cf38778875588b17`; its weights are approximately 1.75 GB. Other compatible local paths can be supplied, but 2B requires more memory.

The [official model card](https://huggingface.co/Qwen/Qwen3.5-0.8B) originally requests current Transformers. This implementation pins `transformers==5.13.1` and `torch==2.13.0`, rather than a moving Git main branch. The [official Transformers documentation](https://huggingface.co/docs/transformers/model_doc/qwen3_5) distinguishes the text-only class from `Qwen3_5ForConditionalGeneration`, which matches this checkpoint's downloaded configuration. We load that class and `AutoTokenizer`, use CPU bfloat16, and explicitly set `enable_thinking=False` in the checkpoint's chat template. No images/video are accepted by the app; no vision preprocessing dependencies are added.

Loading happens once per backend process. A single-worker generation executor and lock prevent parallel inference. Greedy decoding is deterministic, equivalent to zero-temperature selection, with a maximum of 400 new tokens. Raw model context is limited to 4,000 alert characters, 20 IOCs with bounded values, bounded evidence, and up to six bounded history messages. The tokenizer rejects context above 4,096 tokens, returning rules instead of risking unbounded allocation. Shortening is reported by `context_truncated`; the complete alert is preserved in SQLite/UI/report.

The deadline includes model loading and retries for normal API requests. Calls waiting on a busy model quickly fall back. Generation stopping is cooperative: a single PyTorch operation/model load cannot be forcibly interrupted by a thread deadline. The API can return rules while that worker finishes, and the generation lock remains held until it exits. Restart the backend if a worker never finishes; the program does not spawn replacement model copies.

An 8 GB laptop also runs Windows, a browser, and Python. Weight size is not total working memory. Ryzen 7 5820U uses the CPU path; AMD iGPU acceleration is not configured. bfloat16 may be slow on this CPU. Optimized NVIDIA-oriented kernels are deliberately not installed. Expect 10–30+ seconds and potentially much longer; actual speed is not guaranteed.

**Observed development-machine limitation:** a real offline loading attempt reached the checkpoint loader but failed with Windows error 1455, "The paging file is too small for this operation to complete." Thus real generation speed, peak loaded-model memory, and narrative quality are **not verified**. No virtual-memory settings were changed. Close memory-heavy applications and check available RAM/Windows commit capacity before rerunning; use rules-only or mock mode if the model cannot fit.

## API and data

See [http://localhost:8000/docs](http://localhost:8000/docs) for the generated API reference.

| Method | Route | Behavior |
| --- | --- | --- |
| GET | `/health` | Provider/model state |
| GET/POST | `/api/alerts` | Filter/page queue; ingest local webhook |
| GET | `/api/alerts/{id}` | Alert and deterministic baseline |
| POST | `/api/alerts/{id}/explain` | Cached explanation; `regenerate=true`, `rules_only=true` supported |
| GET/POST | `/api/alerts/{id}/chat` | Stored history / scoped question |
| PATCH | `/api/alerts/{id}/status` | New, In progress, Closed; atomic audit entry |
| GET/PUT | `/api/alerts/{id}/notes` | Saved analyst notes |
| GET | `/api/alerts/{id}/report.md` | Markdown, without starting generation; supports rules_only |
| GET | `/api/stats` | Counts/time series |
| GET | `/api/history` | Closed alerts and status changes |
| POST | `/api/seed` | Reload 30 simulated samples |

Queue supports `severity`, `status`, `type`, `q`, `page`, `page_size` (maximum 100). IDs accept numeric and ALR-prefixed forms. Webhook input is capped at 20,000 raw characters. Questions are capped at 1,000 characters and notes at 20,000. Stored chat retrieval returns the latest 100 messages; generation uses only the last six.

```powershell
$body = @{ raw_alert = "Failed login`nAttempts: 30`nSource IP: 192.0.2.50"; source = 'Local SIEM' } | ConvertTo-Json
Invoke-RestMethod http://localhost:8000/api/alerts -Method Post -ContentType application/json -Body $body
```

Reloading samples resets their notes, chat, explanations, and statuses. Webhook alerts are preserved. A request overtaken by a sample reload receives HTTP 409 instead of writing stale output into the recreated sample. Transient inference failures are not cached; valid model results and explicit rules-only results have separate cache entries keyed by model/provider/configuration. Reports use the saved explanation for the selected mode, or deterministic text if none exists.

There is no general chat endpoint. The scope guard deliberately accepts a conservative range of alert-triage questions and refuses uncertain/mixed intent locally. Use the suggestion chips for common questions. Alert data and history are serialized as untrusted data below a fixed system prompt. Prompt construction and deterministic guards are tested; these measures **do not prove universal prompt-injection resistance** of a small model. No external tools are available to the model.

## Tests and evaluation

Tests need no model or Torch installation:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-test.txt
.\.venv\Scripts\python.exe -m pytest backend\tests -q
cd frontend
npm run build
npm audit
cd ..
.\.venv\Scripts\python.exe backend\eval\run_eval.py
```

The evaluation contains 34 manually labeled regression cases, including nine benign examples. It prints rules classification accuracy and severity agreement. Because the model is intentionally prohibited from deciding those fields, the LLM column is explicitly inherited from rules. This is a small synthetic regression evaluation, not an estimate of production detection accuracy. `--llm` explicitly runs all local narrative generations and reports schema success, fallback counts, and timing; it can be slow and skips when the model cannot load.

Run the hardware smoke check separately (it does not read `.env`; use arguments or environment variables):

```powershell
.\.venv\Scripts\python.exe scripts\check_model.py --model-path D:\HCL\models\Qwen3.5-0.8B --timeout 180
```

It prints load time, explanation JSON, generation time, current/peak process RAM on Windows, and exit code 0 for real model output, 2 for rules fallback, or 1 for loading failure. Loading itself can outlast the requested generation timeout. Peak working set is process memory, not whole-system commit use; also inspect Task Manager.

## Limitations and troubleshooting

- Model not loaded/error: verify the local path and complete safetensors/tokenizer/config files; inspect pinned dependencies and memory. Restart after a load error. The backend remains usable with rules.
- Slow CPU response: reduce `MAX_NEW_TOKENS`, close other heavy applications, and try `TORCH_THREADS=4`. More threads can be slower. Reducing output length can increase invalid/truncated JSON fallback.
- 0.8B narrative quality: it can miss nuance, repeat templates, follow malicious data, hallucinate, or produce malformed JSON. Treat all narrative as unverified assistance; consult original sensor logs. Neither MITRE candidates nor a false-positive estimate establishes compromise.
- Long inputs: model context can be shortened or rejected while full original text is preserved. The UI shows truncation/fallback. Ask for a smaller, focused alert if needed.
- Scope refusal: rephrase as one question about the current alert. The server deliberately does not answer general security education, other alerts, or mixed requests.
- Frontend connection error: start the backend, verify ports 8000/5173 and the localhost URL, and retry. This application does not expose services on all network interfaces.
- Sample feed: reopening the app does not create a new live feed. Reload samples explicitly; no scheduler or background telemetry collector exists.

## Verify on your laptop

- [ ] Offline model loads from the supplied directory after closing memory-heavy applications.
- [ ] `check_model.py` returns real `engine=llm` output and acceptable load/generation time.
- [ ] Peak process RAM and whole-system commit remain acceptable with both UI and backend running.
- [ ] The queue and health stay responsive during generation; repeated calls serialize/fall back.
- [ ] Missing weights, deadlines, malformed output, and rules-only mode visibly use `engine=rules`.
- [ ] Review narrative accuracy and the two injection sample alerts (ALR-1029/1030); test additional adversarial text.
- [ ] Verify IOC/evidence grounding, false-positive suggestions, and long-alert truncation before using real incident data.
- [ ] Notes/status audit and Markdown export persist across a backend restart.

Implementation plan and phase evidence are in `docs/superpowers/plans/` and `docs/implementation-progress.md`.
