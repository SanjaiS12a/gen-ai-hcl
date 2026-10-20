from app.llm.copilot import rules_narrative


def render_report(alert, notes, result=None):
    b = alert.baseline
    narrative = result or dict(rules_narrative(alert).model_dump(),engine='rules',provider='rules',model='deterministic',generation_ms=0)
    evidence = '\n'.join(f'- {x.label}: {x.value}' for x in b.evidence) or '- No structured evidence.'
    indicators = '\n'.join(f'- {x.type}: {x.value}' for x in b.extracted_iocs) or '- No IOCs extracted.'
    mitre = '\n'.join(f'- {x.technique_id} — {x.technique} ({x.tactic})' for x in b.mitre_attack) or '- No supported technique.'
    verify = '\n'.join('- [ ] '+x for x in narrative['verify_first'])
    steps = '\n'.join(f'{i+1}. {x}' for i,x in enumerate(narrative['next_steps']))
    # Fence longer than any source backtick run, preserving hostile source text as data.
    import re
    fence = '`'*max(3,1+max((len(x) for x in re.findall(r'`+',alert.raw_alert)),default=0))
    fp = narrative.get('false_positive_likelihood')
    fp_text = f"{fp['likelihood']}: {fp['reason']}" if fp else 'Not assessed.'
    return f'''# {alert.display_id}: {b.incident_type}

Source: {alert.source} ({alert.origin})
Time: {alert.timestamp}
Status: {alert.status}
Severity: {b.severity.value} (rule-based)
Confidence: {b.confidence} (rule-based)

## Explanation provenance
Engine: {narrative['engine']}
Provider: {narrative['provider']}
Model: {narrative['model']}
Generation time: {narrative['generation_ms']} ms
AI-generated text requires verification. All actions below are recommendations only.

## Summary
{narrative['summary']}

## Why it matters
{narrative['why_it_matters']}

## Verify first
{verify}

## Recommended next steps
{steps}

## False-positive likelihood
{fp_text}

## Evidence (deterministic)
{evidence}

## Indicators (deterministic)
{indicators}

## MITRE ATT&CK candidates (rule-based)
{mitre}

## Analyst notes
{notes or 'No notes recorded.'}

## Original alert (untrusted source data)
{fence}text
{alert.raw_alert}
{fence}
'''
