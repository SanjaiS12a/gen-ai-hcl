"""Conservative whole-question allowlist. Uncertain intent is refused locally."""
import re

REFUSAL = 'I can only help explain and triage this alert. Please ask a question about this alert.'


def in_scope(question: str, alert_id: int) -> bool:
    text = question.lower().strip().rstrip('?.!').strip()
    ids = re.findall(r'\b(?:alr-)?(\d{4,})\b',text)
    if any(int(x) != alert_id for x in ids):
        return False
    text = re.sub(r'\b(?:alr-)?'+str(alert_id)+r'\b','this',text)
    text = re.sub(r'^please\s+','',text)
    patterns = [
        r'(?:explain|summarize|analyse|analyze|triage) (?:this|the)(?: alert| incident)?',
        r'explain alert this',
        r'summarize (?:this alert )?for my manager',
        r'(?:is this|is this alert|could this be|is it) (?:likely )?(?:a )?false positive',
        r'what (?:should i|do i need to|can i) (?:check|verify|do)(?: first| next)?(?: for this alert)?',
        r'what (?:are|is) (?:the |this alert.s )?(?:iocs?|indicators?|evidence|severity|priority|mitre mapping|next steps|root cause|risk|impact)',
        r'why is (?:this|this alert|it) (?:suspicious|important|high severity|critical|severe)',
        r'why (?:does|might) this (?:alert )?matter',
        r'(?:how should i|how can i) (?:respond|triage|investigate|contain)(?: this| this alert)?',
        r'(?:what|which) (?:logs|evidence|data) (?:should i|do i need to) (?:check|collect|review)',
        r'(?:explain|list|show) (?:the |this alert.s )?(?:iocs?|indicators|evidence|mitre techniques|recommended actions)',
        r'(?:does|could) this (?:alert )?(?:indicate|mean) (?:compromise|phishing|malware|a brute force attack)',
    ]
    return any(re.fullmatch(pattern,text) for pattern in patterns)
