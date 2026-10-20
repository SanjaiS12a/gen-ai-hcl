import json
import logging
import os
import time
from threading import Lock


def _complete_json(raw):
    text = raw.lstrip()
    value, end = json.JSONDecoder().raw_decode(text)
    if not isinstance(value,dict) or text[end:].strip() not in {'','}'}:
        raise ValueError('Expected one JSON object without trailing prose or another object.')
    return text[:end]


def _quantize_cpu_model(model, torch):
    # Convert one Linear at a time, avoiding a full float32 copy of all weights.
    for name, child in list(model.named_children()):
        if isinstance(child, torch.nn.Linear):
            wrapper = torch.nn.Sequential(child.float())
            packed = torch.ao.quantization.quantize_dynamic(
                wrapper, {torch.nn.Linear}, dtype=torch.qint8, inplace=True)
            setattr(model, name, packed[0])
        else:
            _quantize_cpu_model(child, torch)
    return model.float()


class MockProvider:
    name = 'mock'
    model_name = 'deterministic-mock (no model)'
    status = 'ready'

    def __init__(self):
        self.calls = 0

    def generate(self, messages, deadline):
        self.calls += 1
        return json.dumps(dict(summary='Mock explanation: review the selected alert and its rule-based evidence.',
            why_it_matters='The baseline indicates potential security activity; impact is not confirmed.',
            verify_first=['Confirm the event with the original sensor logs.'],
            next_steps=['Correlate the selected alert with authorized activity before recommending containment.'],
            false_positive_likelihood={'likelihood':'MEDIUM','reason':'Additional evidence is needed.'}))


class TransformersProvider:
    name = 'transformers'

    def __init__(self):
        self.model_name = os.getenv('MODEL_PATH','Qwen/Qwen3.5-0.8B')
        self.status = 'not_loaded'
        self.error = None
        self._load_lock = Lock()
        self._model = None
        self._tokenizer = None
        self._constraint_data = None
        self.progress = {'phase':'idle','input_tokens':0,'generated_tokens':0}

    def _load(self):
        with self._load_lock:
            if self._model is not None:
                return
            if self.status == 'error':
                raise RuntimeError('Model unavailable; check local files/dependencies and restart the backend.')
            self.status = 'loading'
            # Disable Hub telemetry before importing the HF stack.
            os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
            os.environ['DO_NOT_TRACK'] = '1'
            try:
                import torch
                from transformers import AutoTokenizer, Qwen3_5ForCausalLM, Qwen3_5TextConfig
                torch.set_num_threads(max(1,min(8,int(os.getenv('TORCH_THREADS','4')))))
                tokenizer = AutoTokenizer.from_pretrained(self.model_name, local_files_only=True, trust_remote_code=False)
                config = Qwen3_5TextConfig.from_pretrained(self.model_name, local_files_only=True, trust_remote_code=False)
                model, loading_info = Qwen3_5ForCausalLM.from_pretrained(self.model_name, config=config,
                    local_files_only=True, trust_remote_code=False, dtype=torch.bfloat16,
                    disable_mmap=os.getenv('MODEL_DISABLE_MMAP','0') == '1',
                    attn_implementation='eager', output_loading_info=True)
                if loading_info.get('missing_keys') or loading_info.get('mismatched_keys'):
                    raise ValueError('Text checkpoint has missing or mismatched weights; refusing uninitialized parameters.')
                model = model.to('cpu').eval()
                if os.getenv('MODEL_CPU_INT8','0') == '1':
                    # AVX2 CPUs may emulate bf16 matrix multiplication slowly.
                    # Dynamic int8 Linear kernels use float32 activations; no extra package is required.
                    model = _quantize_cpu_model(model, torch)
                self._tokenizer, self._model = tokenizer, model
                self.status = 'ready'
            except Exception as exc:
                self.status = 'error'
                self.error = 'Windows paging-file/commit limit (1455)' if getattr(exc,'winerror',None)==1455 or '1455' in str(exc) else f'{type(exc).__name__}: {str(exc)[:300]}'
                logging.getLogger(__name__).exception('Local model loading failed')
                raise RuntimeError('Local model could not load. Check MODEL_PATH, RAM and pinned dependencies.') from exc

    def _json_filter(self, prefix):
        from app.llm.structured import build_tokenizer_data, json_filter
        if self._constraint_data is None:
            self._constraint_data = build_tokenizer_data(self._tokenizer)
        return json_filter(self._constraint_data, prefix)

    def generate(self, messages, deadline):
        self._load()
        import torch
        from transformers import StoppingCriteria, StoppingCriteriaList

        provider = self
        prompt_length = 0
        class Deadline(StoppingCriteria):
            def __call__(self, input_ids, scores, **kwargs):
                provider.progress['generated_tokens'] = input_ids.shape[-1]-prompt_length
                if time.monotonic() >= deadline:
                    return True
                try:
                    _complete_json(json_prefix+provider._tokenizer.decode(input_ids[0][prompt_length:],skip_special_tokens=True))
                    return True
                except ValueError:
                    return False

        if time.monotonic() >= deadline:
            raise TimeoutError('Model load exceeded generation deadline; retry once loading has finished.')
        json_prefix = '{"summary": "The alert reports '
        tokens = self._tokenizer.apply_chat_template(messages+[{'role':'assistant','content':json_prefix}], add_generation_prompt=False,
            tokenize=True, return_tensors='pt', return_dict=True, enable_thinking=False,continue_final_message=True)
        if tokens['input_ids'].shape[-1] > 4096:
            raise ValueError('Context exceeds 4096-token local memory budget.')
        prompt_length = tokens['input_ids'].shape[-1]
        allowed_tokens = self._json_filter(json_prefix)
        if time.monotonic() >= deadline:
            raise TimeoutError('JSON constraint preparation exceeded the deadline; retry with the warm model.')
        self.progress = {'phase':'generating','input_tokens':prompt_length,'generated_tokens':0}
        try:
            with torch.inference_mode():
                outputs = self._model.generate(**tokens, max_new_tokens=max(32,min(400,int(os.getenv('MAX_NEW_TOKENS','400')))),
                    do_sample=False, use_cache=True, stopping_criteria=StoppingCriteriaList([Deadline()]),
                    prefix_allowed_tokens_fn=allowed_tokens,
                    pad_token_id=self._tokenizer.eos_token_id)
        finally:
            self.progress['phase'] = 'idle'
        if time.monotonic() >= deadline:
            raise TimeoutError('Local generation timed out.')
        raw = json_prefix+self._tokenizer.decode(outputs[0][tokens['input_ids'].shape[-1]:],skip_special_tokens=True).strip()
        try:
            return _complete_json(raw)
        except ValueError:
            if os.getenv('LLM_DEBUG_OUTPUT','0') == '1':
                logging.getLogger(__name__).warning('Malformed LOCAL MODEL OUTPUT (untrusted data): %r',raw)
            raise


class UnavailableProvider:
    status = 'error'
    def __init__(self, name):
        self.name = name
        self.model_name = 'unavailable'

    def generate(self, messages, deadline):
        raise RuntimeError('Provider is a stub or unsupported. Use transformers or mock; no HTTP request was made.')


def get_provider():
    name = os.getenv('LLM_PROVIDER','transformers').lower()
    if name == 'llamacpp':
        from app.llm.native import LlamaCppProvider
        return LlamaCppProvider()
    return MockProvider() if name == 'mock' else TransformersProvider() if name == 'transformers' else UnavailableProvider(name)
