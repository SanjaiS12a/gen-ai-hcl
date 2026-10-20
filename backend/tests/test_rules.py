import pytest
from app.services.analyzer import analyze_alert, _first_int_after, answer_incident_question
from app.services.ioc import extract_iocs


def test_substrings_do_not_classify():
    assert analyze_alert('Document reconstruction account uploadable').incident_type == 'Unknown'


def test_ip_not_attempt_count():
    assert analyze_alert('Failed login\nSource IP: 185.199.111.45').severity.value != 'CRITICAL'
    assert _first_int_after('account: 200\nfailed login 999', ['attempts', 'count']) is None
    assert _first_int_after('Attempts:\n200', ['attempts']) is None
    assert _first_int_after('Attempts: 125', ['attempts']) == 125


def test_unknown_confidence_and_mitre():
    result = analyze_alert('Telemetry 192.0.2.1 and admin@example.technology')
    assert result.confidence == 'LOW'
    assert result.mitre_attack == []


@pytest.mark.parametrize('text', ['Email attachment subject: newsletter sender: news@example.org', 'Endpoint inventory hash: ' + 'a'*64])
def test_generic_terms_not_high_confidence(text):
    result = analyze_alert(text)
    assert result.confidence != 'HIGH'
    assert 'possible false positive' in ' '.join(result.why_suspicious).lower()


def test_domain_deduplication_and_tlds():
    result = extract_iocs('sender@news.technology https://portal.security/route standalone.solutions STANDALONE.solutions')
    assert [x.value.lower() for x in result if x.type == 'DOMAIN'] == ['standalone.solutions']


def test_chat_word_boundaries():
    incident = analyze_alert('Phishing credential harvesting email')
    answer = answer_incident_question(incident, 'Explain recipient document')
    assert not answer.startswith('Extracted IOCs:')
    assert not answer.startswith('Recommended next steps:')


def test_empty_evidence_fields_do_not_borrow_next_line():
    incident = analyze_alert('Failed login\nUser:\nSource IP: 192.0.2.1\nAttempts:\n200')
    evidence = {x.label:x.value for x in incident.evidence}
    assert 'Attempts' not in evidence
    assert 'User' not in evidence
    assert evidence['Source IP'] == '192.0.2.1'
