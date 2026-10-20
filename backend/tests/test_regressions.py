import threading
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from app.main import create_app
from app.llm.providers import MockProvider
from app.services.analyzer import analyze_alert


def test_long_fields_never_crash_fallback(tmp_path):
    with TestClient(create_app(str(tmp_path/'long.db'),MockProvider())) as c:
        aid = c.post('/api/alerts',json={'raw_alert':'Failed login\nAttempts: 5\nUser: '+'a'*1800}).json()['id']
        assert c.post(f'/api/alerts/{aid}/explain?rules_only=true').status_code == 200
        assert c.post(f'/api/alerts/{aid}/chat',json={'question':'What should I check next?','rules_only':True}).status_code == 200
        assert c.get(f'/api/alerts/{aid}/report.md').status_code == 200


def test_benign_context_cannot_downgrade_confirmed_malware():
    baseline = analyze_alert('Ransomware trojan confirmed compromise\nHost: FILE-01\nApproved maintenance occurred earlier')
    assert baseline.severity.value == 'CRITICAL'


def test_sample_reload_rejects_stale_chat_and_explanation(tmp_path):
    class Reset(MockProvider):
        def generate(self,messages,deadline):
            self.store.seed()
            return super().generate(messages,deadline)
    p = Reset()
    with TestClient(create_app(str(tmp_path/'race.db'),p)) as c:
        p.store = c.app.state.store
        assert c.post('/api/alerts/1001/chat',json={'question':'What should I check next?'}).status_code == 409
        assert c.get('/api/alerts/1001/chat').json() == []
        assert c.post('/api/alerts/1001/explain').status_code == 409


def test_report_uses_saved_provenance_and_rules_mode(tmp_path):
    with TestClient(create_app(str(tmp_path/'report.db'),MockProvider())) as c:
        c.post('/api/alerts/1001/explain')
        text = c.get('/api/alerts/1001/report.md').text
        assert 'Engine: llm' in text and 'Provider: mock' in text
        assert 'Engine: rules' in c.get('/api/alerts/1001/report.md?rules_only=true').text
