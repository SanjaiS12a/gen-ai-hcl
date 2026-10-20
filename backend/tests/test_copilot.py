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
