import sys
import pytest
from types import SimpleNamespace
from app.llm.providers import TransformersProvider, UnavailableProvider
import app.llm.providers as providers


@pytest.mark.parametrize('int8',[False,True])
def test_provider_loads_once_from_local_files(monkeypatch,int8):
    monkeypatch.setenv('MODEL_DISABLE_MMAP','1')
    monkeypatch.setenv('MODEL_CPU_INT8','1' if int8 else '0')
    calls=[]
    class Loaded:
        def to(self,device):
            assert device == 'cpu'
            return self
        def eval(self): return self
        def float(self):
            calls.append(('float',{}))
            return self
    def load_model(path,**kwargs):
        calls.append(('model',kwargs))
        return Loaded(), {'missing_keys':[], 'mismatched_keys':[]}
    text_config = object()
    def load_config(path,**kwargs):
        calls.append(('config',kwargs))
        return text_config
    def load_tokenizer(path,**kwargs):
        calls.append(('tokenizer',kwargs))
        return object()
    def quantize(model,types,**options):
        assert types == {object}
        calls.append(('quantize',options))
        return model
    def quantize_model(model,torch):
        calls.append(('quantize',{'dtype':'int8','inplace':True}))
        return model
    monkeypatch.setattr(providers,'_quantize_cpu_model',quantize_model)
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(bfloat16='bf16',qint8='int8',nn=SimpleNamespace(Linear=object),ao=SimpleNamespace(quantization=SimpleNamespace(quantize_dynamic=quantize)),set_num_threads=lambda n:None))
    monkeypatch.setitem(sys.modules,'transformers',SimpleNamespace(AutoTokenizer=SimpleNamespace(from_pretrained=load_tokenizer),Qwen3_5TextConfig=SimpleNamespace(from_pretrained=load_config),Qwen3_5ForCausalLM=SimpleNamespace(from_pretrained=load_model)))
    provider=TransformersProvider()
    assert provider.status == 'not_loaded'
    provider._load(); provider._load()
    assert provider.status == 'ready'
    assert len(calls) == (4 if int8 else 3)
    assert all(options['local_files_only'] and not options['trust_remote_code'] for name,options in calls if name in {'model','tokenizer','config'})
    assert dict(calls)['model']['disable_mmap'] is True
    assert dict(calls)['model']['config'] is text_config
    assert dict(calls)['model']['output_loading_info'] is True
    if int8:
        assert dict(calls)['quantize'] == {'dtype':'int8','inplace':True}


def test_int8_conversion_never_expands_whole_model_before_quantizing():
    events=[]
    class Linear:
        def __init__(self,name): self.name=name
        def float(self): events.append('float '+self.name); return self
    class Packed: pass
    class Node:
        def __init__(self,**children): self.__dict__.update(children)
        def named_children(self): return list(self.__dict__.items())
        def float(self):
            assert not any(isinstance(x,Linear) for x in self.__dict__.values())
            events.append('container float')
            return self
    def quantize(wrapper,types,**kwargs):
        assert types == {Linear} and kwargs['inplace']
        events.append('quantize '+wrapper[0].name)
        return [Packed()]
    torch=SimpleNamespace(qint8='int8',nn=SimpleNamespace(Linear=Linear,Sequential=lambda x:[x]),ao=SimpleNamespace(quantization=SimpleNamespace(quantize_dynamic=quantize)))
    model=Node(inner=Node(linear=Linear('inner')),head=Linear('head'))
    assert providers._quantize_cpu_model(model,torch) is model
    assert events == ['float inner','quantize inner','container float','float head','quantize head','container float']


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


def test_model_continues_summary_prefill_without_copying_input(monkeypatch):
    import contextlib
    import time
    import json
    seen={}
    class Tokens:
        shape=(1,5)
    class Tokenizer:
        eos_token_id=0
        def apply_chat_template(self,messages,**kwargs):
            seen.update(kwargs)
            assert messages[-1] == {'role':'assistant','content':'{"summary": "The alert reports '}
            return {'input_ids':Tokens()}
        def decode(self,tokens,**kwargs):
            return 'phishing activity.","why_it_matters":"Potential compromise.","verify_first":["Check logs"],"next_steps":["Verify authorization"]}}'
    class Row:
        def __getitem__(self,span): return [1]
    class Model:
        def generate(self,**kwargs): return [Row()]
    p=TransformersProvider()
    p._load=lambda:None
    p._tokenizer,p._model=Tokenizer(),Model()
    p._json_filter=lambda prefix: lambda batch_id, sent: [1]
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(inference_mode=contextlib.nullcontext))
    monkeypatch.setitem(sys.modules,'transformers',SimpleNamespace(StoppingCriteria=object,StoppingCriteriaList=list))
    result=json.loads(p.generate([{'role':'user','content':'Explain selected alert'}],time.monotonic()+10))
    assert result['summary'] == 'The alert reports phishing activity.'
    assert seen['continue_final_message'] is True
    assert seen['enable_thinking'] is False
    assert seen['add_generation_prompt'] is False


def test_json_completion_trims_only_redundant_closing_delimiter():
    assert providers._complete_json('{"summary":"original model words"}}') == '{"summary":"original model words"}'
    for raw in ['{} arbitrary prose','{} {}','not json']:
        with pytest.raises(ValueError):
            providers._complete_json(raw)
