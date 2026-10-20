import sys
from types import SimpleNamespace
from app.llm.providers import TransformersProvider, UnavailableProvider


def test_provider_loads_once_from_local_files(monkeypatch):
    calls=[]
    class Loaded:
        def to(self,device):
            assert device == 'cpu'
            return self
        def eval(self): return self
    def load_model(path,**kwargs):
        calls.append(('model',kwargs))
        return Loaded()
    def load_tokenizer(path,**kwargs):
        calls.append(('tokenizer',kwargs))
        return object()
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(bfloat16='bf16',set_num_threads=lambda n:None))
    monkeypatch.setitem(sys.modules,'transformers',SimpleNamespace(AutoTokenizer=SimpleNamespace(from_pretrained=load_tokenizer),Qwen3_5ForConditionalGeneration=SimpleNamespace(from_pretrained=load_model)))
    provider=TransformersProvider()
    assert provider.status == 'not_loaded'
    provider._load(); provider._load()
    assert provider.status == 'ready'
    assert len(calls) == 2
    assert all(options['local_files_only'] and not options['trust_remote_code'] for _,options in calls)


def test_stub_does_not_use_http():
    import pytest
    with pytest.raises(RuntimeError,match='no HTTP request'):
        UnavailableProvider('ollama').generate([],0)


def test_recommendations_and_whitespace_are_validated(tmp_path):
    from app.db import Store
    from app.llm.copilot import Copilot
    from app.llm.providers import MockProvider
    import json
    class Whitespace(MockProvider):
        def generate(self,messages,deadline):
            self.calls+=1
            return json.dumps({'summary':'   ','why_it_matters':' ','verify_first':['Check logs'],'next_steps':['Review sensor']})
    store=Store(str(tmp_path/'test.db'))
    assert Copilot(store,Whitespace()).explain(store.get(1001)).engine == 'rules'
