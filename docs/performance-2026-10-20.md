# Local Qwen CPU response improvement

Date: 2026-10-20. Hardware: AMD Ryzen 7 5825U, 8 cores / 16 logical processors. Windows reports about 5.85 GiB usable physical RAM. No Windows memory settings were changed.

## Observed response times

| Request | Provider | Input/output tokens | Elapsed |
| --- | --- | --- | --- |
| Previous warm scoped chat, ALR-1002 | Transformers dynamic int8 | 691 / 190 | 90.8 s |
| Same full-explanation question, native Q8_0, original prompt | llama.cpp | 605 / 162 | 17.914 s |
| Focused plan, ALR-1002, standalone | llama.cpp | 500 / 78 | 10.962 s |
| Focused plan, ALR-1001, standalone | llama.cpp | 509 / 92 | 11.846 s |
| First real browser scoped plan, including native startup and existing history | llama.cpp | see saved API evidence | 15.3 s |
| Warm real browser scoped plan, existing history | llama.cpp | see saved API evidence | 13.3 s |
| Later fresh browser scoped plan, existing history | llama.cpp | see saved API evidence | 22.0 s |
| Full explanation through application API | llama.cpp | 535 / 176 | 27.0 s |

These are individual observations, not a controlled like-for-like throughput comparison or a latency guarantee. The three fresh browser plans ranged from 13.3 to 22.0 seconds; context, CPU load and memory paging can affect latency. The focused plan intentionally produces fewer tokens than the old chat. Runtime, quantization implementation, prompt, and context lengths changed. Native generation in these standalone runs was approximately 12.6–12.8 tokens/s, with prompt processing around 110 tokens/s. A two-repeat, 32-token CPU microbenchmark observed 15.42 tokens/s at four generation threads and 14.52 at eight; the active profile uses four generation threads and eight batch/prompt threads.

Saved API evidence: [benchmark JSON](qa/fast-qwen-benchmark.json). Browser proof showing the latest 22.0-second Local AI answer: [screenshot](qa/fast-qwen-step-by-step.png).

The portable native server reported ready in approximately 3.5 seconds in the initial standalone startup. By comparison, the old Python format-filter tokenizer preparation alone took 38.3 seconds in a formatting probe; that probe did not complete its per-token validation, so no valid per-token formatting speed is claimed.

The separate native smoke script also completed successfully and released its temporary port after shutdown. Its run overlapped a frontend build and is not used as an uncontended speed comparison. The model child reached a peak working set of approximately 897 MiB in the application run. The memory helper reports native-child memory separately from the small Python parent; neither measurement is whole-system commit use.

## Implementation

- Same Qwen3.5-0.8B family, Q8_0 GGUF text checkpoint, retaining more precision than a Q4 speed profile. The original safetensors download is preserved.
- Portable CPU-native kernels and native JSON grammar replace Python tensor/large-vocabulary filter overhead for the active runtime. No Torch import is needed on this code path.
- Step-by-step / next-check questions request only three ordered instructions through a strict `ActionPlan` schema. The full explanation button retains its separate narrative/checklist schema.
- The chat scrolls its own message area to each new response so older slow answers do not hide the current result.
- Local guidance supplies investigation, verification, and conditional response topics. It is marked as guidance, not observed facts. The model still writes the returned instructions.
- Strict Pydantic validation, one retry, shared inference lock/deadline, and explicitly labeled rule fallback remain. Invented emails, IPs, URLs and hashes are rejected; derived origins of supplied URLs are allowed. This narrow grounding check cannot detect every factual error.
- Model process is hidden, local, reused, authenticated with an ephemeral key, and closed on normal backend shutdown. HTTP is restricted to loopback, without proxies or redirects. No automatic download occurs during runtime.

## Reproducibility

Runtime: official ggml-org/llama.cpp build b11755 (`704366d76`), Windows CPU x64 archive.

- Archive SHA-256: `450b11d263c34e521ef0800bce69e3262d6657546fdedbd6f3005769f21a2568`.
- Model: `ggml-org/Qwen3.5-0.8B-GGUF`, revision `807dfd9a6fadbf703207aac3bfb0b2b3040d077c`.
- File: `Qwen3.5-0.8B-Q8_0.gguf`, 833592096 bytes.
- Model SHA-256: `37ae482d336108d23516fa35e8e0c4126688d81018b87178a18d752a1357814f`.
- Generation threads 4, batch threads 8, context 4096, one slot, thinking disabled, temperature 0, maximum 300 tokens (240 for focused plans), 90-second application deadline.

Explicit setup: `scripts/setup_fast_model.ps1`. Native smoke-check/benchmark:

```powershell
# Stop the backend first, or select a separate free loopback port.
$env:LLAMA_PORT='8082'
$env:LLAMA_THREADS='4'
$env:LLAMA_BATCH_THREADS='8'
.\.venv\Scripts\python.exe scripts\check_model.py --provider llamacpp --server-path D:\HCL\tools\llama-b11755\llama-server.exe --model-path D:\HCL\models\Qwen3.5-0.8B-GGUF\Qwen3.5-0.8B-Q8_0.gguf --alert-id 1002 --question 'How do I resolve this alert step by step?' --runs 2 --timeout 90 --max-new-tokens 300
```

Review the returned instructions and `engine`, not just the time. Short synthetic checks do not establish incident-response accuracy or resistance to malicious input.
