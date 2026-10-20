import json
import time
import pytest
from app.llm.native import LlamaCppProvider
from app.llm.providers import get_provider


def configured(tmp_path, monkeypatch):
    binary = tmp_path/'llama-server.exe'
    model = tmp_path/'Qwen3.5-0.8B-Q8_0.gguf'
    binary.touch(); model.touch()
    monkeypatch.setenv('LLAMA_SERVER_PATH',str(binary))
    monkeypatch.setenv('MODEL_PATH',str(model))
    return LlamaCppProvider()


def test_native_provider_selection_and_local_only_address(tmp_path, monkeypatch):
    configured(tmp_path,monkeypatch)
    monkeypatch.setenv('LLM_PROVIDER','llamacpp')
    monkeypatch.setenv('LLAMA_BASE_URL','https://untrusted.invalid')
    provider = get_provider()
    assert isinstance(provider,LlamaCppProvider)
    assert provider.base_url == 'http://127.0.0.1:8081'


def test_native_generation_uses_schema_and_disabled_thinking(tmp_path,monkeypatch):
    provider = configured(tmp_path,monkeypatch)
    provider._load = lambda deadline: None
    seen = []
    def request(path,timeout,body=None):
        seen.append((path,timeout,body))
        return {'choices':[{'finish_reason':'stop','message':{'content':'{"summary":"Possible phishing"}'}}],
                'usage':{'prompt_tokens':100,'completion_tokens':42}}
    provider._request=request
    assert json.loads(provider.generate([{'role':'user','content':'Explain this alert'}],time.monotonic()+5))['summary'] == 'Possible phishing'
    path,timeout,body=seen[0]
    assert path == '/v1/chat/completions' and 0 < timeout <= 5
    assert body['chat_template_kwargs']['enable_thinking'] is False
    assert body['response_format']['schema']['additionalProperties'] is False
    assert body['temperature'] == 0
    assert provider.progress['generated_tokens'] == 42
    assert provider.progress['phase'] == 'idle'


def test_native_rejects_truncated_and_expired_results(tmp_path,monkeypatch):
    provider = configured(tmp_path,monkeypatch)
    provider._load = lambda deadline: None
    provider._request=lambda *a,**k:{'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}
    with pytest.raises(ValueError,match='truncated'):
        provider.generate([],time.monotonic()+5)
    with pytest.raises(TimeoutError):
        provider.generate([],time.monotonic()-1)
    assert provider.progress['phase'] == 'idle'


def test_native_missing_files_do_not_start_process(tmp_path,monkeypatch):
    monkeypatch.setenv('LLAMA_SERVER_PATH',str(tmp_path/'absent.exe'))
    monkeypatch.setenv('MODEL_PATH',str(tmp_path/'absent.gguf'))
    provider=LlamaCppProvider()
    with pytest.raises(FileNotFoundError):
        provider._load(time.monotonic()+5)
    assert provider.status == 'error'
    assert provider._process is None


def test_native_closes_only_its_owned_process(tmp_path,monkeypatch):
    provider=configured(tmp_path,monkeypatch)
    class Process:
        terminated=False
        def poll(self): return None
        def terminate(self): self.terminated=True
        def wait(self,timeout): return 0
    process=Process(); provider._process=process
    provider.close(); provider.close()
    assert process.terminated


def test_native_plan_uses_small_ordered_schema(tmp_path,monkeypatch):
    provider=configured(tmp_path,monkeypatch)
    provider._load=lambda deadline:None
    bodies=[]
    def request(path,timeout,body):
        bodies.append(body)
        return {'choices':[{'finish_reason':'stop','message':{'content':'{}'}}]}
    provider._request=request
    provider.generate_plan([],time.monotonic()+5)
    schema=bodies[0]['response_format']['schema']
    assert list(schema['properties']) == ['next_steps']
    assert len(schema['properties']['next_steps']['prefixItems']) == 3
    assert bodies[0]['max_tokens'] <= 240
