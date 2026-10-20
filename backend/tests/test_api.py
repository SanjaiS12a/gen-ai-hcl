import pytest
from fastapi.testclient import TestClient
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(str(tmp_path / 'test.db'))) as c:
        yield c


def test_seed_and_filters(client):
    data = client.get('/api/alerts').json()
    assert data['total'] == 30
    assert len(data['items']) == 20
    assert client.get('/api/alerts/ALR-1002').json()['id'] == 1002
    assert client.get('/api/alerts?severity=CRITICAL').json()['total'] > 0
    assert client.get('/api/alerts?type=Phishing').json()['total'] > 0
    assert client.get('/api/alerts?q=newsletter').json()['total'] > 0
    assert client.get('/api/alerts?page_size=101').status_code == 422
    assert client.get('/api/alerts/99999').status_code == 404
    assert client.post('/api/chat', json={}).status_code == 404


def test_ingest_notes_status_and_reset(client):
    alert = client.post('/api/alerts', json={'raw_alert':'Failed login\nAttempts: 30\nSource IP: 192.0.2.42', 'source':'Test SIEM'}).json()
    aid = alert['id']
    assert alert['origin'] == 'webhook'
    assert alert['baseline']['incident_type'] == 'Brute Force'
    assert client.put(f'/api/alerts/{aid}/notes', json={'text':'Investigating'}).json()['text'] == 'Investigating'
    assert client.patch(f'/api/alerts/{aid}/status', json={'status':'Closed'}).status_code == 200
    assert client.get('/api/history').json()['changes'][0]['alert_id'] == aid
    assert client.get('/api/stats').json()['by_status']['Closed'] == 1
    assert client.get(f'/api/alerts/{aid}/report.md').headers['content-type'].startswith('text/markdown')
    client.post('/api/seed')
    assert client.get(f'/api/alerts/{aid}/notes').json()['text'] == 'Investigating'
    assert client.get('/api/alerts').json()['total'] == 31
    assert client.post('/api/alerts', json={'raw_alert':'x'*20001}).status_code == 422
    assert client.patch(f'/api/alerts/{aid}/status', json={'status':'Done'}).status_code == 422


def test_health_and_cors(client):
    assert client.get('/health').json()['model_status'] == 'not_loaded'
    allowed = client.options('/api/alerts', headers={'Origin':'http://localhost:5173','Access-Control-Request-Method':'GET'})
    denied = client.options('/api/alerts', headers={'Origin':'http://evil.example','Access-Control-Request-Method':'GET'})
    assert allowed.status_code == 200
    assert denied.status_code == 400
