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

## Fast Windows CPU setup (recommended)

The active CPU profile keeps **Qwen3.5-0.8B**, using its Q8_0 GGUF text weights with the portable [llama.cpp runtime](https://github.com/ggml-org/llama.cpp). It avoids Python tensor/JSON-filter overhead. Step-by-step questions generate only three instructions, labeled **Investigate**, **Confirm**, and **Respond if confirmed**, rather than regenerating an entire explanation. The full explanation remains available separately.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-fast.txt
# Explicit network setup: pinned runtime archive and model, SHA-256 checked.
.\scripts\setup_fast_model.ps1
Copy-Item .env.example .env
# Adjust paths in .env if setup printed a different model/runtime directory.
cd frontend
npm ci
cd ..
.\scripts\run_backend.ps1
# In another terminal:
.\scripts\run_frontend.ps1
```

On this machine the verified runtime and model already exist; no repeat download is required. The portable CPU runtime archive is approximately 24 MB and the Q8_0 model approximately 834 MB. There is no Ollama, Docker, GPU package, or new Python inference dependency in this profile. The original safetensors model is retained for the optional Transformers profile.

```dotenv
LLM_PROVIDER=llamacpp
MODEL_PATH=D:\HCL\models\Qwen3.5-0.8B-GGUF\Qwen3.5-0.8B-Q8_0.gguf
LLAMA_SERVER_PATH=D:\HCL\tools\llama-b11755\llama-server.exe
LLAMA_PORT=8081
LLAMA_THREADS=4
LLAMA_BATCH_THREADS=8
MAX_NEW_TOKENS=300
GENERATION_TIMEOUT=90
```

The backend starts its own hidden model process lazily, reuses it, and stops it on normal shutdown. Its authenticated HTTP connection is fixed to `127.0.0.1`; proxies and redirects are disabled. The model server runs offline with thinking disabled, one generation slot, and a 4096-token context. Port 8081 must be free; the provider refuses to attach to an unrelated server. `LLAMA_PORT` can select another loopback port. The application API remains on port 8000 and the frontend on [http://localhost:5173](http://localhost:5173).

Observed on the Ryzen 7 5825U: the previous Transformers warm chat took 90.8 seconds. Standalone native focused plans took 11.0 seconds (phishing) and 11.8 seconds (brute force). Three fresh browser plans took 15.3, 13.3, and 22.0 seconds, an observed range of 13–22 seconds; the first included native startup. A full explanation took 27.0 seconds. These are individual observations with different context/output lengths and CPU/memory conditions, not a latency guarantee. Model output still needs review. [Benchmark details](docs/performance-2026-10-20.md) describe the comparison.

Local triage guidance is included as recommendations, never observed facts. A grounding check retries/falls back if a model invents an email address, IP, URL or hash. It is a narrow check, not proof of factual accuracy. No action is executed.

## Optional Transformers setup

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
GENERATION_TIMEOUT=300
TORCH_THREADS=4
MODEL_DISABLE_MMAP=1
MODEL_CPU_INT8=0
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

## Optional Transformers compatibility and hardware limits

The target is **Qwen3.5-0.8B**, replacing the original brief's 2B target at the user's request. The downloaded revision was `2fc06364715b967f1860aea9cf38778875588b17`; its weights are approximately 1.75 GB. Other compatible local paths can be supplied, but 2B requires more memory.

The [official model card](https://huggingface.co/Qwen/Qwen3.5-0.8B) originally requests current Transformers. This implementation pins `transformers==5.13.1` and `torch==2.13.0`, rather than a moving Git main branch. Following the [official Transformers text-only guidance](https://huggingface.co/docs/transformers/model_doc/qwen3_5), it loads `Qwen3_5ForCausalLM` with `Qwen3_5TextConfig` and `AutoTokenizer`, using CPU bfloat16 before optional int8 conversion. Transformers' built-in checkpoint conversion selects the text weights from the downloaded multimodal checkpoint. Missing or mismatched text weights cause a loading failure instead of accepting uninitialized parameters. Vision modules are not instantiated. The chat template explicitly sets `enable_thinking=False`; no images/video or vision preprocessing dependencies are used.

Loading happens once per backend process. A single-worker generation executor and lock prevent parallel inference. Greedy decoding is deterministic, equivalent to zero-temperature selection, with a maximum of 400 new tokens. Raw model context is limited to 4,000 alert characters, 20 IOCs with bounded values, bounded evidence, and up to six bounded history messages. The tokenizer rejects context above 4,096 tokens, returning rules instead of risking unbounded allocation. Shortening is reported by `context_truncated`; the complete alert is preserved in SQLite/UI/report.

The deadline includes model loading and retries for normal API requests. Calls waiting on a busy model quickly fall back. Generation stopping is cooperative: a single PyTorch operation/model load cannot be forcibly interrupted by a thread deadline. The API can return rules while that worker finishes, and the generation lock remains held until it exits. Restart the backend if a worker never finishes; the program does not spawn replacement model copies.

An 8 GB laptop also runs Windows, a browser, and Python. Weight size is not total working memory. Ryzen 7 5820U uses the CPU path; AMD iGPU acceleration is not configured. bfloat16 may be slow on this CPU. Optimized NVIDIA-oriented kernels are deliberately not installed. Expect 10–30+ seconds and potentially much longer; actual speed is not guaranteed.

For older AVX2 CPUs where bfloat16 is emulated slowly, `MODEL_CPU_INT8=1` enables PyTorch's existing dynamic int8 conversion for Linear layers, with float32 activations. It uses the same local checkpoint and no new dependency or download. Conversion occurs once, one Linear layer at a time to avoid expanding the whole model to float32 at once. Loading can still raise transient memory demand; validate narrative quality because quantization can change the model's output. This option relies on the pinned PyTorch version's `torch.ao.quantization` API. The CPU profile on this machine uses `MAX_NEW_TOKENS=400` and `GENERATION_TIMEOUT=300`, with concise JSON requesting three practical next steps. The health endpoint and status bar report generated token counts; loading/prefill may take time before the first token. Explanations remain recommendations, not executed actions.

For this small model, the output instructions follow the delimited untrusted data, and an assistant JSON prefill starts the summary sentence. The continuation follows the [official Hugging Face chat-template prefill mechanism](https://huggingface.co/docs/transformers/main/en/chat_templating#continue_final_message), with thinking still disabled. Generation stops when a complete JSON object is available. One redundant closing brace is tolerated without changing model-written words; trailing prose, additional objects, unknown fields, and missing fields are rejected. Pydantic still validates every narrative before `engine=llm` is returned.

[LM Format Enforcer](https://github.com/noamgat/lm-format-enforcer) constrains the next allowed tokens to a compact narrative JSON schema: two verification checks and three next steps, with bounded strings and required fields. Its two added pure-Python wheels total approximately 68 KB; there is no second model or network service. The adapter uses the library's public core API to support Transformers 5 and reuses tokenizer data across requests. This improves formatting; it does not establish factual correctness or guarantee completion before a deadline.

**Windows loading workaround:** the default safetensors memory-mapped loader initially failed with Windows error 1455, "The paging file is too small for this operation to complete." Setting `MODEL_DISABLE_MMAP=1` uses Transformers' supported `disable_mmap=True` option instead. This successfully loaded the local 0.8B checkpoint on the development machine without manually changing Windows settings; the observed process peak working set during loading was approximately 2.63 GiB. This mode reads the checkpoint into memory and can increase transient RAM demand. Generation can still be slow under memory pressure; check actual response metadata and Task Manager instead of assuming a ready model guarantees acceptable latency.

A final text-only ALR-1002 explanation was verified locally with `engine=llm`, `provider=transformers`, and no fallback, taking 206.2 seconds including cold loading and JSON-filter preparation. This machine uses `MODEL_CPU_INT8=1`, `MAX_NEW_TOKENS=400`, `GENERATION_TIMEOUT=300`, and `TORCH_THREADS=4`. The browser displays the Local AI badge, two verification checks, and three numbered steps; the "How do I resolve this alert step by step?" chip requests a scoped follow-up. The tiny model's answers can be basic or inaccurate, including misidentifying an entity or a possible cause; structured output validation does not verify its claims against the evidence.

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

The evaluation contains 34 manually labeled regression cases, including nine benign examples. It prints rules classification accuracy and severity agreement. Because the model is intentionally prohibited from deciding those fields, the LLM column is explicitly inherited from rules. This is a small synthetic regression evaluation, not an estimate of production detection accuracy. `--llm` explicitly runs all local narrative generations and reports schema success, fallback counts, and timing; it can be slow and skips when the model cannot load. Use `--provider llamacpp --model-path <GGUF-file> --server-path <llama-server.exe>` for the fast profile, or `--provider transformers --model-path <safetensors-directory>` for the original profile. Stop the backend first or set a different free `LLAMA_PORT`.

Run the hardware smoke check separately (it does not read `.env`; use arguments or environment variables). For the fast profile, stop the backend first or choose another free loopback port:

```powershell
$env:LLAMA_PORT='8082'
.\.venv\Scripts\python.exe scripts\check_model.py --provider llamacpp --server-path D:\HCL\tools\llama-b11755\llama-server.exe --model-path D:\HCL\models\Qwen3.5-0.8B-GGUF\Qwen3.5-0.8B-Q8_0.gguf --alert-id 1002 --question 'How do I resolve this alert step by step?' --runs 2 --timeout 90 --max-new-tokens 300
```

It prints load time, response JSON, generation time, native token timings, and current/peak process RAM on Windows. Native mode reports Python parent and model-child RAM separately. Exit code 0 means real model output, 2 means rules fallback, and 1 means loading failure. `--question` selects the compact chat plan; omit it for a full explanation. The optional Transformers check uses `--provider transformers --model-path D:\HCL\models\Qwen3.5-0.8B --cpu-int8 --disable-mmap --timeout 300`. Peak working set is process memory, not whole-system commit use; also inspect Task Manager.

## Limitations and troubleshooting

- Model not loaded/error: for native mode verify the GGUF path, runtime executable/DLLs and a free `LLAMA_PORT`; for Transformers verify the complete safetensors/tokenizer/config directory. Restart after a load error. The backend remains usable with rules. On forced backend termination, an orphan native process can retain the port; stop only that known process or choose another port.
- Slow CPU response: use the step-by-step chip for a compact plan; close other heavy applications and try `LLAMA_THREADS=4`, `LLAMA_BATCH_THREADS=8`. The optional Transformers profile uses `TORCH_THREADS=4`. More threads can be slower. Reducing output length can increase invalid/truncated JSON fallback.
- 0.8B narrative quality: it can miss nuance, repeat templates, follow malicious data, hallucinate, or produce malformed JSON. Treat all narrative as unverified assistance; consult original sensor logs. Neither MITRE candidates nor a false-positive estimate establishes compromise.
- Long inputs: model context can be shortened or rejected while full original text is preserved. The UI shows truncation/fallback. Ask for a smaller, focused alert if needed.
- Scope refusal: rephrase as one question about the current alert. The server deliberately does not answer general security education, other alerts, or mixed requests.
- Frontend connection error: start the backend, verify ports 8000/5173 and the localhost URL, and retry. This application does not expose services on all network interfaces.
- Sample feed: reopening the app does not create a new live feed. Reload samples explicitly; no scheduler or background telemetry collector exists.

## Verify on your laptop

- [ ] Offline model loads from the supplied GGUF file (or directory for Transformers) after closing memory-heavy applications.
- [ ] `check_model.py` returns real `engine=llm` output and acceptable load/generation time.
- [ ] Peak process RAM and whole-system commit remain acceptable with both UI and backend running.
- [ ] The queue and health stay responsive during generation; repeated calls serialize/fall back.
- [ ] Missing weights, deadlines, malformed output, and rules-only mode visibly use `engine=rules`.
- [ ] Review narrative accuracy and the two injection sample alerts (ALR-1029/1030); test additional adversarial text.
- [ ] Verify IOC/evidence grounding, false-positive suggestions, and long-alert truncation before using real incident data.
- [ ] Notes/status audit and Markdown export persist across a backend restart.

Implementation plan and phase evidence are in `docs/superpowers/plans/` and `docs/implementation-progress.md`.
