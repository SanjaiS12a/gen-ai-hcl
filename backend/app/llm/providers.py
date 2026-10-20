import json
import os
import time
from threading import Lock


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
                from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration
                torch.set_num_threads(max(1,min(8,int(os.getenv('TORCH_THREADS','4')))))
                tokenizer = AutoTokenizer.from_pretrained(self.model_name, local_files_only=True, trust_remote_code=False)
                model = Qwen3_5ForConditionalGeneration.from_pretrained(self.model_name,
                    local_files_only=True, trust_remote_code=False, dtype=torch.bfloat16,
                    attn_implementation='eager').to('cpu').eval()
                self._tokenizer, self._model = tokenizer, model
                self.status = 'ready'
            except Exception as exc:
                self.status = 'error'
                self.error = 'Windows paging-file/commit limit (1455)' if getattr(exc,'winerror',None)==1455 or '1455' in str(exc) else type(exc).__name__
                raise RuntimeError('Local model could not load. Check MODEL_PATH, RAM and pinned dependencies.') from exc

    def generate(self, messages, deadline):
        self._load()
        import torch
        from transformers import StoppingCriteria, StoppingCriteriaList

        class Deadline(StoppingCriteria):
            def __call__(self, input_ids, scores, **kwargs):
                return time.monotonic() >= deadline

        if time.monotonic() >= deadline:
            raise TimeoutError('Model load exceeded generation deadline; retry once loading has finished.')
        tokens = self._tokenizer.apply_chat_template(messages, add_generation_prompt=True,
            tokenize=True, return_tensors='pt', return_dict=True, enable_thinking=False)
        if tokens['input_ids'].shape[-1] > 4096:
            raise ValueError('Context exceeds 4096-token local memory budget.')
        with torch.inference_mode():
            outputs = self._model.generate(**tokens, max_new_tokens=max(32,min(400,int(os.getenv('MAX_NEW_TOKENS','400')))),
                do_sample=False, use_cache=True, stopping_criteria=StoppingCriteriaList([Deadline()]),
                pad_token_id=self._tokenizer.eos_token_id)
        if time.monotonic() >= deadline:
            raise TimeoutError('Local generation timed out.')
        return self._tokenizer.decode(outputs[0][tokens['input_ids'].shape[-1]:],skip_special_tokens=True).strip()


class UnavailableProvider:
    status = 'error'
    def __init__(self, name):
        self.name = name
        self.model_name = 'unavailable'

    def generate(self, messages, deadline):
        raise RuntimeError('Provider is a stub or unsupported. Use transformers or mock; no HTTP request was made.')


def get_provider():
    name = os.getenv('LLM_PROVIDER','transformers').lower()
    return MockProvider() if name == 'mock' else TransformersProvider() if name == 'transformers' else UnavailableProvider(name)
