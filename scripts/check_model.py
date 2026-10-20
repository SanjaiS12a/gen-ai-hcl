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


def memory_mb(pid=None):
    if os.name == 'nt':
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(x,ctypes.c_size_t) for x in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.OpenProcess.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        psapi = ctypes.WinDLL('psapi',use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
        handle = kernel.OpenProcess(0x0410,False,pid) if pid is not None else kernel.GetCurrentProcess()
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not psapi.GetProcessMemoryInfo(handle,ctypes.byref(counters),counters.cb):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            if pid is not None:
                kernel.CloseHandle(handle)
        return {'current_mb':round(counters.WorkingSetSize/1024**2,1), 'peak_mb':round(counters.PeakWorkingSetSize/1024**2,1)}
    if pid is not None:
        return {'unavailable':'Child-process memory is measured only on Windows.'}
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {'peak_mb':round(peak/(1024**2 if sys.platform == 'darwin' else 1024),1)}


def runtime_memory(provider):
    process = getattr(provider,'_process',None)
    return {'python_parent':memory_mb(),
            'native_model_child':memory_mb(process.pid) if process is not None and process.poll() is None else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-path',default=os.getenv('MODEL_PATH','Qwen/Qwen3.5-0.8B'))
    parser.add_argument('--provider',choices=['transformers','llamacpp'],default=os.getenv('LLM_PROVIDER','transformers'))
    parser.add_argument('--server-path',default=os.getenv('LLAMA_SERVER_PATH','llama-server.exe'))
    parser.add_argument('--alert-id',type=int,default=1001)
    parser.add_argument('--question',default=None,help='Optional scoped chat question instead of a full explanation.')
    parser.add_argument('--runs',type=int,choices=range(1,6),default=1)
    parser.add_argument('--timeout',type=float,default=180)
    parser.add_argument('--max-new-tokens',type=int,default=400)
    parser.add_argument('--cpu-int8',action='store_true',default=os.getenv('MODEL_CPU_INT8')=='1')
    parser.add_argument('--disable-mmap',action='store_true',default=os.name=='nt')
    args = parser.parse_args()
    os.environ.update(MODEL_PATH=args.model_path,LLM_PROVIDER=args.provider,LLAMA_SERVER_PATH=args.server_path,HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1',MAX_NEW_TOKENS=str(args.max_new_tokens))
    os.environ['MODEL_CPU_INT8']='1' if args.cpu_int8 else '0'
    os.environ['MODEL_DISABLE_MMAP']='1' if args.disable_mmap else '0'
    from app.db import Store
    from app.llm.providers import get_provider
    from app.llm.copilot import Copilot
    with tempfile.TemporaryDirectory() as folder:
        store = Store(str(Path(folder)/'check.db'))
        provider = get_provider()
        started = time.monotonic()
        try:
            if args.provider == 'llamacpp':
                provider._load(time.monotonic()+args.timeout)
            else:
                provider._load()
            print(json.dumps({'model_status':provider.status,'load_seconds':round(time.monotonic()-started,2),'ram':runtime_memory(provider)}),flush=True)
            copilot = Copilot(store,provider,timeout=args.timeout)
            try:
                results=[]
                for run in range(args.runs):
                    alert = store.get(args.alert_id)
                    result = copilot.chat(alert,args.question) if args.question else copilot.explain(alert,regenerate=True)
                    results.append(result)
                    print(result.model_dump_json(indent=2),flush=True)
                    print(json.dumps({'run':run+1,'elapsed_seconds':round(time.monotonic()-started,2),
                                      'ram':runtime_memory(provider),'native_timings':getattr(provider,'last_timings',None)}),flush=True)
                return 0 if all(x.engine == 'llm' for x in results) else 2
            finally:
                copilot.close()
        except Exception as exc:
            cause = exc
            while cause.__cause__ is not None:
                cause = cause.__cause__
            print(json.dumps({'model_status':provider.status,'error':str(exc),'cause':str(cause),'ram':memory_mb()}),flush=True)
            return 1
        finally:
            close = getattr(provider,'close',None)
            if close:
                close()


if __name__ == '__main__':
    raise SystemExit(main())
