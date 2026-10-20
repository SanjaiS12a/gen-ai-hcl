"""Small labeled regression evaluation; not a measure of operational detection quality."""
import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.analyzer import analyze_alert


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--llm',action='store_true',help='Explicitly load the local model and evaluate narrative availability (slow).')
    parser.add_argument('--provider',choices=['transformers','llamacpp'],default=os.getenv('LLM_PROVIDER','transformers'))
    parser.add_argument('--model-path',default=None)
    parser.add_argument('--server-path',default=None)
    parser.add_argument('--timeout',type=float,default=90)
    args = parser.parse_args()
    cases = json.loads(Path(__file__).with_name('eval_set.json').read_text())
    correct_type, correct_severity = 0,0
    for case in cases:
        result = analyze_alert(case['raw_alert'])
        correct_type += result.incident_type == case['type']
        correct_severity += result.severity.value == case['severity']
        if result.incident_type != case['type'] or result.severity.value != case['severity']:
            print('Mismatch:',case['raw_alert'][:70], 'expected',case['type'],case['severity'],'got',result.incident_type,result.severity.value)
    n = len(cases)
    print(f'Cases: {n}; benign: {sum(x["benign"] for x in cases)}')
    print(f'{"Metric":30} | {"Rules":15} | LLM pipeline')
    print('-'*80)
    print(f'{"Classification accuracy":30} | {correct_type/n:14.1%} | inherited from rules; no model classification')
    print(f'{"Severity agreement":30} | {correct_severity/n:14.1%} | inherited from rules; no model severity')
    if not args.llm:
        print('LLM narrative evaluation skipped (pass --llm to explicitly load local weights).')
        return 0
    from app.db import Store
    from app.models import IngestRequest
    from app.llm.copilot import Copilot
    from app.llm.providers import get_provider
    os.environ['LLM_PROVIDER'] = args.provider
    if args.model_path:
        os.environ['MODEL_PATH'] = args.model_path
    if args.server_path:
        os.environ['LLAMA_SERVER_PATH'] = args.server_path
    provider = get_provider()
    try:
        if args.provider == 'llamacpp':
            provider._load(time.monotonic()+args.timeout)
        else:
            provider._load()
    except Exception as exc:
        print('LLM column skipped: local model unavailable:',exc)
        close = getattr(provider,'close',None)
        if close:
            close()
        return 0
    with tempfile.TemporaryDirectory() as folder:
        store = Store(str(Path(folder)/'eval.db'))
        copilot = Copilot(store,provider,timeout=args.timeout)
        valid, elapsed = 0,[]
        try:
            for case in cases:
                alert = store.ingest(IngestRequest(raw_alert=case['raw_alert'],source='Evaluation'))
                result = copilot.explain(alert)
                valid += result.engine == 'llm'
                elapsed.append(result.generation_ms)
            print(f'LLM valid narrative (after at most one retry): {valid}/{n}; fallback: {n-valid}/{n}; mean generation: {sum(elapsed)/n:.0f} ms')
            print('Narrative correctness/injection resistance requires analyst review; JSON validity does not prove factual accuracy.')
        finally:
            copilot.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
