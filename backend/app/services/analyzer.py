import hashlib
import re

from app.models import EvidenceItem, IncidentAnalysis, MitreTechnique, Severity
from app.services.ioc import extract_iocs
from app.llm.mitre import validate_mitre


class Rule:
    def __init__(
        self,
        incident_type: str,
        title: str,
        severity: Severity,
        keywords: list[str],
        mitre: list[MitreTechnique],
        actions: list[str],
        suspicious_reasons: list[str],
        root_cause: str,
    ):
        self.incident_type = incident_type
        self.title = title
        self.severity = severity
        self.keywords = keywords
        self.mitre = mitre
        self.actions = actions
        self.suspicious_reasons = suspicious_reasons
        self.root_cause = root_cause


RULES = [
    Rule(
        "Brute Force",
        "Possible Brute-Force Authentication Attack",
        Severity.high,
        ["failed login", "failed authentication", "brute", "invalid password", "attempts", "ssh"],
        [MitreTechnique(tactic="Credential Access", technique_id="T1110", technique="Brute Force")],
        [
            "Temporarily block or rate-limit the source IP while investigation is active.",
            "Check whether the targeted account had any successful login after the failed attempts.",
            "Review authentication logs for the same source IP, username, and nearby timestamps.",
            "Reset credentials and verify MFA for the affected account if compromise is suspected.",
            "Search for lateral movement or privilege escalation from the targeted account.",
        ],
        [
            "Repeated failed authentication attempts can indicate password guessing or credential stuffing.",
            "Targeting privileged or generic accounts increases the likelihood of unauthorized access attempts.",
            "A burst of attempts from one source in a short window is abnormal for normal user behavior.",
        ],
        "Likely external credential guessing against an exposed authentication service.",
    ),
    Rule(
        "Phishing",
        "Possible Phishing Email with Malicious Link",
        Severity.high,
        ["phishing", "subject:", "sender:", "email", "credential", "malicious url", "attachment"],
        [MitreTechnique(tactic="Initial Access", technique_id="T1566", technique="Phishing")],
        [
            "Quarantine the email and remove matching messages from other inboxes.",
            "Block the sender, malicious URL, and related domains at email and web gateways.",
            "Check whether recipients clicked the link or opened attachments.",
            "Reset credentials for affected users if a credential-harvesting page was accessed.",
            "Preserve the message headers and artifacts for incident reporting.",
        ],
        [
            "The alert contains email delivery indicators commonly associated with phishing.",
            "External links or attachments can be used to steal credentials or deliver malware.",
            "User-facing lures often attempt to create urgency or impersonate trusted services.",
        ],
        "Likely social-engineering attempt delivered through email.",
    ),
    Rule(
        "Malware",
        "Possible Malware Detection on Endpoint",
        Severity.critical,
        ["malware", "trojan", "ransomware", "virus", "endpoint", "quarantined", "hash"],
        [MitreTechnique(tactic="Execution", technique_id="T1204", technique="User Execution")],
        [
            "Isolate the affected endpoint from the network.",
            "Collect endpoint telemetry, process tree, file path, hash, and user context.",
            "Search for the same hash, filename, or command line across other endpoints.",
            "Run an endpoint scan and preserve suspicious binaries for malware analysis.",
            "Reimage or remediate the endpoint if persistence or credential theft is confirmed.",
        ],
        [
            "Endpoint malware alerts indicate suspicious or known-bad code execution.",
            "File hashes and process paths can reveal whether the detection spread to other hosts.",
            "Malware may establish persistence, steal credentials, or stage additional payloads.",
        ],
        "Likely malicious file execution or endpoint compromise.",
    ),
    Rule(
        "Suspicious Login",
        "Suspicious Login from Unusual Location",
        Severity.medium,
        ["successful login", "impossible travel", "unknown country", "unusual country", "new device", "mfa"],
        [MitreTechnique(tactic="Initial Access", technique_id="T1078", technique="Valid Accounts")],
        [
            "Verify the login with the account owner.",
            "Review MFA status, device fingerprint, source IP, and session activity.",
            "Revoke suspicious sessions and force password reset if the user cannot confirm activity.",
            "Search for mailbox rules, privilege changes, downloads, and unusual access after login.",
            "Add conditional access controls for risky countries or unfamiliar devices.",
        ],
        [
            "A successful login from an unusual location can indicate stolen credentials.",
            "Valid-account abuse is often difficult to detect because authentication succeeds.",
            "New devices, unknown countries, or impossible travel patterns raise account-takeover risk.",
        ],
        "Likely credential misuse or legitimate travel that requires user verification.",
    ),
    Rule(
        "Port Scan",
        "Possible Network Reconnaissance or Port Scan",
        Severity.medium,
        ["port scan", "nmap", "syn scan", "multiple ports", "recon", "connection attempts"],
        [MitreTechnique(tactic="Discovery", technique_id="T1046", technique="Network Service Discovery")],
        [
            "Block or rate-limit the scanning source if it is external and unauthorized.",
            "Identify targeted hosts and exposed services.",
            "Check whether scanning was followed by exploitation attempts.",
            "Validate firewall rules and remove unnecessary internet-facing services.",
            "Correlate with IDS, firewall, and vulnerability-management findings.",
        ],
        [
            "Multiple connection attempts across ports can indicate service discovery.",
            "Reconnaissance often precedes exploitation attempts.",
            "External scanning of sensitive services increases exposure risk.",
        ],
        "Likely reconnaissance against reachable network services.",
    ),
    Rule(
        "Web Attack",
        "Possible Web Application Attack",
        Severity.high,
        ["sql injection", "sqli", "union select", "../", "xss", "script>", "web attack", "http 500"],
        [MitreTechnique(tactic="Initial Access", technique_id="T1190", technique="Exploit Public-Facing Application")],
        [
            "Block the attacking IP or apply WAF rules for the observed payload.",
            "Review web server logs around the request time for successful exploitation signs.",
            "Check application errors, database activity, and suspicious file writes.",
            "Validate input handling for the affected route or parameter.",
            "Patch vulnerable components and add detection for repeated payload patterns.",
        ],
        [
            "The request contains payload patterns associated with web exploitation.",
            "Public-facing applications are common initial-access targets.",
            "Server errors after suspicious payloads can indicate probing or exploitation.",
        ],
        "Likely attempt to exploit a public-facing web application.",
    ),
    Rule(
        "Data Exfiltration",
        "Possible Data Exfiltration Activity",
        Severity.critical,
        ["exfiltration", "large outbound", "data transfer", "upload", "unusual volume", "dns tunneling"],
        [MitreTechnique(tactic="Exfiltration", technique_id="T1041", technique="Exfiltration Over C2 Channel")],
        [
            "Contain the affected host or account and pause suspicious outbound traffic.",
            "Identify the destination, data volume, files accessed, and process responsible.",
            "Review DLP, proxy, DNS, and endpoint telemetry for related transfers.",
            "Determine whether sensitive data was accessed or staged before transfer.",
            "Escalate to incident leadership and preserve evidence for legal or compliance review.",
        ],
        [
            "Large or unusual outbound transfers may indicate unauthorized data movement.",
            "Unknown external destinations increase the likelihood of data loss.",
            "Exfiltration may follow credential compromise or endpoint malware activity.",
        ],
        "Likely unauthorized outbound transfer that requires immediate containment.",
    ),
]


def analyze_alert(raw_alert: str) -> IncidentAnalysis:
    normalized = raw_alert.lower()
    rule = max(RULES, key=lambda item: _score_rule(item, normalized))
    score = _score_rule(rule, normalized)

    if score == 0:
        rule = Rule(
            "Unknown",
            "Unclassified Security Alert Requiring Triage",
            Severity.low,
            [],
            [],
            [
                "Review the raw event details and identify the affected user, host, and source.",
                "Correlate the event with authentication, endpoint, network, and application logs.",
                "Search for repeated activity involving the same indicators.",
                "Escalate if additional suspicious activity or confirmed impact is found.",
            ],
            [
                "The event contains security-relevant telemetry but did not match a high-confidence incident pattern.",
                "Manual triage is needed to determine whether this is benign or malicious.",
            ],
            "Insufficient context to determine root cause from the alert alone.",
        )

    severity = _adjust_severity(rule.severity, raw_alert)
    iocs = extract_iocs(raw_alert)
    evidence = _extract_evidence(raw_alert)
    confidence = "HIGH" if score >= 2 else "MEDIUM" if score == 1 else "LOW"
    reasons = list(rule.suspicious_reasons)
    if score < 2:
        reasons.append("Possible false positive: weak or missing detection signals; verify the event before acting.")
    approved = _contains(normalized, "approved maintenance") or _contains(normalized, "authorized vulnerability scan")
    if approved and rule.incident_type in {'Unknown','Port Scan','Suspicious Login'} and severity != Severity.critical:
        severity = Severity.low
        confidence = "LOW"
        reasons.append("Possible false positive: the alert states approved activity; independently verify the approval.")
    summary = _build_summary(rule, evidence, iocs)
    report = _build_report(rule, severity, summary, evidence, iocs)

    return IncidentAnalysis(
        id=hashlib.sha1(raw_alert.encode("utf-8")).hexdigest()[:12],
        title=rule.title,
        incident_type=rule.incident_type,
        severity=severity,
        confidence=confidence,
        summary=summary,
        why_suspicious=reasons,
        root_cause=rule.root_cause,
        extracted_iocs=iocs,
        evidence=evidence,
        mitre_attack=validate_mitre(rule.mitre),
        recommended_actions=rule.actions,
        analyst_report=report,
        raw_alert=raw_alert,
    )


def answer_incident_question(incident: IncidentAnalysis, question: str) -> str:
    q = question.lower()
    if any(_contains(q, word) for word in ["severe", "severity", "critical", "priority"]):
        return f"The incident is rated {incident.severity.value}. The rating is based on the incident type, observed indicators, and potential impact described in the alert."
    if any(_contains(q, word) for word in ["ioc", "iocs", "indicator", "ip", "domain", "hash", "url"]):
        if not incident.extracted_iocs:
            return "No concrete IOCs were extracted from the alert. Ask for additional logs or enrich the event with source, destination, user, host, and file details."
        values = ", ".join(f"{ioc.type}: {ioc.value}" for ioc in incident.extracted_iocs)
        return f"Extracted IOCs: {values}."
    if any(_contains(q, word) for word in ["mitre", "attack", "technique", "tactic"]):
        mapping = ", ".join(f"{item.technique_id} - {item.technique}" for item in incident.mitre_attack)
        return f"Rule-based MITRE ATT&CK candidates: {mapping}. Verify the behavior." if mapping else "No MITRE technique is supported by the rule baseline."
    if any(_contains(q, word) for word in ["do", "next", "contain", "respond", "action"]):
        return "Recommended next steps: " + " ".join(f"{idx + 1}. {action}" for idx, action in enumerate(incident.recommended_actions[:4]))
    if any(_contains(q, word) for word in ["why", "suspicious", "reason"]):
        return "This is suspicious because " + " ".join(incident.why_suspicious)
    return f"This appears to be {incident.title}. {incident.summary} Start by validating the indicators, checking for successful compromise, and following the recommended response steps."


def _contains(text: str, keyword: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(keyword) + r"(?!\w)", text, re.IGNORECASE) is not None


def _score_rule(rule: Rule, normalized: str) -> int:
    weak = {"subject:", "sender:", "email", "attachment", "endpoint", "hash", "attempts", "ssh", "mfa", "upload", "data transfer", "http 500"}
    return sum(1 for keyword in rule.keywords if keyword not in weak and _contains(normalized, keyword))


def _adjust_severity(base: Severity, raw_alert: str) -> Severity:
    text = raw_alert.lower()
    attempts = _first_int_after(text, ["attempts", "failed", "count"])
    if attempts and attempts >= 100:
        return Severity.critical
    if attempts and attempts >= 25 and base == Severity.medium:
        return Severity.high
    if any(_contains(text, term) for term in ["admin", "root", "domain admin", "privileged"]):
        if base == Severity.medium:
            return Severity.high
    if any(_contains(text, term) for term in ["ransomware", "exfiltration", "confirmed compromise"]):
        return Severity.critical
    return base


def _first_int_after(text: str, labels: list[str]) -> int | None:
    for label in labels:
        if label not in {"attempts", "count"}:
            continue
        match = re.search(rf"\b{re.escape(label)}[ \t]*[:=][ \t]*(\d+)\b", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _extract_evidence(raw_alert: str) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    patterns = {
        "User": r"\buser(?:name)?\s*[:=]\s*([^\n,;]+)",
        "Source IP": r"\bsource\s+ip\s*[:=]\s*([^\n,;]+)",
        "Destination IP": r"\bdestination\s+ip\s*[:=]\s*([^\n,;]+)",
        "Attempts": r"\battempts\s*[:=]\s*(\d+)",
        "Time": r"\btime\s*[:=]\s*([^\n,;]+)",
        "Country": r"\bcountry\s*[:=]\s*([^\n,;]+)",
        "Host": r"\bhost\s*[:=]\s*([^\n,;]+)",
        "Process": r"\bprocess\s*[:=]\s*([^\n,;]+)",
        "URL": r"\burl\s*[:=]\s*([^\n,;]+)",
    }
    for label, pattern in patterns.items():
        pattern = pattern.replace(r"\s*", r"[ \t]*").replace(r"\s+", r"[ \t]+")
        match = re.search(pattern, raw_alert, re.IGNORECASE)
        if match and match.group(1).strip():
            evidence.append(EvidenceItem(label=label, value=match.group(1).strip()))
    return evidence


def _build_summary(rule: Rule, evidence: list[EvidenceItem], iocs: list) -> str:
    details = {item.label.lower(): item.value for item in evidence}
    subject = details.get("user") or details.get("host") or "the affected asset"
    source = details.get("source ip")
    attempts = details.get("attempts")

    if rule.incident_type == "Brute Force" and attempts:
        return f"{attempts} failed authentication attempts were observed against {subject}" + (f" from {source}." if source else ".")
    if source:
        return f"The alert indicates {rule.incident_type.lower()} activity involving {subject} and source {source}."
    if iocs:
        return f"The alert indicates {rule.incident_type.lower()} activity with {len(iocs)} extracted indicator(s) requiring investigation."
    return f"The alert indicates possible {rule.incident_type.lower()} activity that requires SOC triage."


def _build_report(rule: Rule, severity: Severity, summary: str, evidence: list[EvidenceItem], iocs: list) -> str:
    evidence_text = "\n".join(f"- {item.label}: {item.value}" for item in evidence) or "- No structured evidence fields were detected."
    ioc_text = "\n".join(f"- {item.type}: {item.value}" for item in iocs) or "- No IOCs extracted."
    actions = "\n".join(f"{idx + 1}. {action}" for idx, action in enumerate(rule.actions))
    mitre = "\n".join(f"- {item.technique_id} - {item.technique} ({item.tactic})" for item in rule.mitre)
    return f"""INCIDENT: {rule.title}

Severity: {severity.value}

Summary:
{summary}

Evidence:
{evidence_text}

Indicators:
{ioc_text}

Recommended Actions:
{actions}

MITRE ATT&CK:
{mitre}
"""
