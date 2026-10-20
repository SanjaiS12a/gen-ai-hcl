import re

from app.models import Indicator


IOC_PATTERNS = {
    "ip": re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "url": re.compile(r"https?://[^\s,;\"')>\]]+", re.IGNORECASE),
    "hash": re.compile(r"\b(?:[a-fA-F0-9]{32}|[a-fA-F0-9]{40}|[a-fA-F0-9]{64})\b"),
    "domain": re.compile(r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+(?:[a-zA-Z]{2,63}|xn--[a-zA-Z0-9-]+)\b"),
}

USERNAME_PATTERNS = [
    re.compile(r"\buser(?:name)?\s*[:=]\s*([A-Za-z0-9._@\\-]+)", re.IGNORECASE),
    re.compile(r"\baccount\s*[:=]\s*([A-Za-z0-9._@\\-]+)", re.IGNORECASE),
    re.compile(r"\blogin\s+for\s+([A-Za-z0-9._@\\-]+)", re.IGNORECASE),
]


def extract_iocs(raw_alert: str) -> list[Indicator]:
    found: list[Indicator] = []
    seen: set[tuple[str, str]] = set()
    occupied = [m.span() for name in ("email", "url") for m in IOC_PATTERNS[name].finditer(raw_alert)]

    for indicator_type, pattern in IOC_PATTERNS.items():
        for match in pattern.finditer(raw_alert):
            if indicator_type == "domain" and any(start <= match.start() and match.end() <= end for start, end in occupied):
                continue
            value = match.group().rstrip(".")
            key = (indicator_type, value.lower())
            if key not in seen:
                seen.add(key)
                found.append(Indicator(type=indicator_type.upper(), value=value))

    for pattern in USERNAME_PATTERNS:
        for match in pattern.findall(raw_alert):
            value = match.strip().rstrip(".")
            key = ("username", value.lower())
            if key not in seen:
                seen.add(key)
                found.append(Indicator(type="USERNAME", value=value))

    return found
