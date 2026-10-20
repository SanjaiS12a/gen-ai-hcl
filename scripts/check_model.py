"""Explicit local model smoke check. Never downloads weights or calls a cloud API."""
import argparse
import ctypes
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))


def memory_mb():
    if os.name == 'nt':
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(x,ctypes.c_size_t) for x in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL('psapi',use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return {'current_mb':round(counters.WorkingSetSize/1024**2,1), 'peak_mb':round(counters.PeakWorkingSetSize/1024**2,1)}
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {'peak_mb':round(peak/(1024**2 if sys.platform == 'darwin' else 1024),1)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-path',default=os.getenv('MODEL_PATH','Qwen/Qwen3.5-0.8B'))
    parser.add_argument('--timeout',type=float,default=180)
    parser.add_argument('--max-new-tokens',type=int,default=400)
    args = parser.parse_args()
    os.environ.update(MODEL_PATH=args.model_path,HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1',MAX_NEW_TOKENS=str(args.max_new_tokens))
    from app.db import Store
    from app.llm.providers import TransformersProvider
    from app.llm.copilot import Copilot
    with tempfile.TemporaryDirectory() as folder:
        store = Store(str(Path(folder)/'check.db'))
        provider = TransformersProvider()
        started = time.monotonic()
        try:
            provider._load()
            print(json.dumps({'model_status':provider.status,'load_seconds':round(time.monotonic()-started,2),'ram':memory_mb()}),flush=True)
            copilot = Copilot(store,provider,timeout=args.timeout)
            try:
                result = copilot.explain(store.get(1001),regenerate=True)
                print(result.model_dump_json(indent=2),flush=True)
                print(json.dumps({'elapsed_seconds':round(time.monotonic()-started,2),'ram':memory_mb()}),flush=True)
                return 0 if result.engine == 'llm' else 2
            finally:
                copilot.close()
        except Exception as exc:
            cause = exc
            while cause.__cause__ is not None:
                cause = cause.__cause__
            print(json.dumps({'model_status':provider.status,'error':str(exc),'cause':str(cause),'ram':memory_mb()}),flush=True)
            return 1


if __name__ == '__main__':
    raise SystemExit(main())
