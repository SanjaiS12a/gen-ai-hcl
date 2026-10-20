import json
import time
from app.db import Store
from app.llm.copilot import Copilot
from app.llm.providers import MockProvider
from app.llm.mitre import validate_mitre
from app.models import MitreTechnique


def setup(tmp_path, provider=None, timeout=2):
    store = Store(str(tmp_path/'test.db'))
    copilot = Copilot(store, provider or MockProvider(), timeout=timeout)
    return store,copilot


def test_mock_cache_regenerate_rules_separation(tmp_path):
    store, c = setup(tmp_path)
    a = store.get(1001)
    assert c.explain(a).engine == 'llm'
    assert c.explain(a).cached
    assert not c.explain(a,regenerate=True).cached
    assert c.explain(a,rules_only=True).engine == 'rules'
    assert c.provider.calls == 2


def test_invalid_json_retry_and_fallback(tmp_path):
    class Invalid(MockProvider):
        def generate(self,messages,deadline):
            self.calls += 1
            return '{"summary":"not complete", "invented_iocs":["8.8.8.8"]}'
    store,c = setup(tmp_path,Invalid())
    result = c.explain(store.get(1001))
    assert result.engine == 'rules'
    assert result.fallback_reason
    assert c.provider.calls == 2


def test_placeholder_steps_are_not_accepted_as_model_advice(tmp_path):
    class Placeholder(MockProvider):
        def generate(self, messages, deadline):
            self.calls += 1
            return json.dumps({'summary':'Possible phishing.', 'why_it_matters':'Credentials could be exposed.',
                              'verify_first':['check one','check two'],
                              'next_steps':['step one','step two','step three']})
    store, c = setup(tmp_path, Placeholder())
    assert c.explain(store.get(1002)).engine == 'rules'
    assert c.provider.calls == 2


def test_fabricated_email_is_retried_instead_of_presented_as_evidence(tmp_path):
    class Invented(MockProvider):
        def generate(self,messages,deadline):
            self.calls += 1
            return json.dumps({'summary':'Phishing targeted analyst@invoice.example.',
                'why_it_matters':'Credentials could be exposed.',
                'verify_first':['Check message headers','Review proxy logs'],
                'next_steps':['Investigate delivery logs','Confirm clicks','Respond if confirmed: reset affected credentials']})
    store,c=setup(tmp_path,Invented())
    assert c.explain(store.get(1002)).engine == 'rules'
    assert c.provider.calls == 2


def test_real_indicator_and_derived_url_origin_are_allowed(tmp_path):
    class Grounded(MockProvider):
        def generate(self,messages,deadline):
            self.calls+=1
            return json.dumps({'summary':'A message from billing@invoice.example needs review.',
                'why_it_matters':'Credentials could be exposed.',
                'verify_first':['Check message headers','Review https://invoice.example proxy records'],
                'next_steps':['Investigate delivery logs','Confirm clicks','Respond if confirmed: reset affected credentials']})
    store,c=setup(tmp_path,Grounded())
    assert c.explain(store.get(1002)).engine == 'llm'


def test_prompt_provides_conditional_incident_guidance(tmp_path):
    store,c=setup(tmp_path)
    message=c.messages(store.get(1002))[-1]['content']
    assert 'delivery trace' in message and 'credential submission' in message


def test_retry_recovers(tmp_path):
    class Retry(MockProvider):
        def generate(self,messages,deadline):
            if not self.calls:
                self.calls += 1
                return 'not json'
            return super().generate(messages,deadline)
    store,c = setup(tmp_path,Retry())
    assert c.explain(store.get(1002)).engine == 'llm'
    assert c.provider.calls == 2


def test_deadline_and_single_generation(tmp_path):
    class Slow(MockProvider):
        def generate(self,messages,deadline):
            time.sleep(.3)
            return super().generate(messages,deadline)
    store,c = setup(tmp_path,Slow(),timeout=.03)
    started = time.monotonic()
    assert c.explain(store.get(1001)).engine == 'rules'
    assert time.monotonic()-started < .25
    assert c.explain(store.get(1002)).engine == 'rules'
    time.sleep(.35)
    assert c.provider.calls == 1


def test_mitre_repair_and_drop():
    items = validate_mitre([MitreTechnique(technique_id='T1110',technique='wrong',tactic='wrong'),MitreTechnique(technique_id='T9999',technique='fake',tactic='fake')])
    assert len(items) == 1
    assert items[0].technique == 'Brute Force'


def test_model_unavailable_falls_back(tmp_path):
    class Missing(MockProvider):
        def generate(self,messages,deadline):
            raise FileNotFoundError('model absent')
    store,c = setup(tmp_path,Missing())
    assert c.explain(store.get(1001)).engine == 'rules'


def test_provider_value_error_with_debug_logging_falls_back(tmp_path, monkeypatch):
    class Malformed(MockProvider):
        def generate(self, messages, deadline):
            self.calls += 1
            raise ValueError('Incomplete JSON object')
    monkeypatch.setenv('LLM_DEBUG_OUTPUT', '1')
    store, c = setup(tmp_path, Malformed())
    result = c.explain(store.get(1001))
    assert result.engine == 'rules'
    assert c.provider.calls == 2
    assert 'invalid JSON' in result.fallback_reason


def test_prompt_requests_practical_step_by_step_actions(tmp_path):
    store,c = setup(tmp_path)
    messages = c.messages(store.get(1001))
    assert 'step-by-step' in messages[-1]['content']
    assert 'expected result' in messages[-1]['content']
    assert 'High severity does not prove compromise' in messages[0]['content']
    assert messages[-1]['content'].index('END_UNTRUSTED_ALERT_DATA') < messages[-1]['content'].index('Return ONLY a JSON object')
    assert 'check one' not in messages[-1]['content']
    assert 'Investigate' in messages[-1]['content']
    assert 'Respond if confirmed' in messages[-1]['content']
    assert 'candidate_actions' not in messages[-1]['content']
