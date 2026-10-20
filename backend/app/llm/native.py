"""Managed, offline llama.cpp CPU inference using only Python's standard library."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
from threading import Lock
import time
from urllib.error import URLError
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler, Request
from app.llm.schema import SCHEMA
from app.models import ActionPlan


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class LlamaCppProvider:
    name = 'llamacpp'

    def __init__(self):
        self.model_name = os.getenv('MODEL_PATH','')
        self.binary = Path(os.getenv('LLAMA_SERVER_PATH','llama-server.exe')).resolve()
        port = int(os.getenv('LLAMA_PORT','8081'))
        if not 1024 <= port <= 65535:
            raise ValueError('LLAMA_PORT must be between 1024 and 65535.')
        self.port = port
        # Never accept a configurable hostname, proxy, or redirect to a cloud API.
        self.base_url = f'http://127.0.0.1:{port}'
        self._opener = build_opener(ProxyHandler({}),NoRedirects())
        self._key = secrets.token_urlsafe(32)
        self._process = None
        self._log = None
        self._load_lock = Lock()
        self.status, self.error = 'not_loaded', None
        self.progress = {'phase':'idle','input_tokens':0,'generated_tokens':0}
        self.last_timings = {}

    def _request(self, path, timeout, body=None):
        request = Request(self.base_url+path,
            data=json.dumps(body).encode('utf-8') if body is not None else None,
            headers={'Content-Type':'application/json','Authorization':'Bearer '+self._key})
        with self._opener.open(request,timeout=max(.001,timeout)) as response:
            return json.load(response)

    def _load(self, deadline):
        with self._load_lock:
            if self.status == 'ready' and self._process is not None and self._process.poll() is None:
                return
            if self.status == 'error':
                raise RuntimeError(self.error or 'Restart the backend after fixing the local runtime.')
            self.status = 'loading'
            try:
                model = Path(self.model_name).resolve()
                if not self.binary.is_file() or not model.is_file() or model.suffix.lower() != '.gguf':
                    raise FileNotFoundError('Set LLAMA_SERVER_PATH to the local executable and MODEL_PATH to a local .gguf file.')
                with socket.socket() as probe:
                    probe.bind(('127.0.0.1',self.port))
                threads = str(max(1,min(16,int(os.getenv('LLAMA_THREADS','4')))))
                batch_threads = str(max(1,min(16,int(os.getenv('LLAMA_BATCH_THREADS','8')))))
                self._log = tempfile.TemporaryFile()
                self._process = subprocess.Popen([str(self.binary),'--model',str(model),
                    '--host','127.0.0.1','--port',str(self.port),'--ctx-size','4096','--parallel','1',
                    '--threads',threads,'--threads-batch',batch_threads,'--batch-size','256','--ubatch-size','128',
                    '--reasoning','off','--offline','--api-key',self._key],
                    stdin=subprocess.DEVNULL,stdout=self._log,stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                while time.monotonic() < deadline:
                    if self._process.poll() is not None:
                        raise RuntimeError('llama-server exited while loading; check CPU/runtime compatibility and available memory.')
                    try:
                        if self._request('/health',min(1,deadline-time.monotonic())).get('status') == 'ok':
                            self.status, self.error = 'ready', None
                            return
                    except (URLError,TimeoutError,OSError):
                        pass
                    time.sleep(.1)
                raise TimeoutError('Local runtime startup exceeded the request deadline; retry after checking the model.')
            except Exception as exc:
                self.close()
                self.status,self.error = 'error',str(exc)[:300]
                raise

    def generate(self, messages, deadline):
        return self._generate_json(messages,deadline,SCHEMA,400)

    def generate_plan(self, messages, deadline):
        return self._generate_json(messages,deadline,ActionPlan.model_json_schema(),240)

    def _generate_json(self, messages, deadline, schema, token_limit):
        if time.monotonic() >= deadline:
            raise TimeoutError('Generation deadline exceeded.')
        self._load(deadline)
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Generation deadline exceeded.')
        self.progress = {'phase':'generating','input_tokens':0,'generated_tokens':0}
        try:
            result = self._request('/v1/chat/completions',remaining,{
                'messages':messages,'temperature':0,'max_tokens':max(32,min(token_limit,int(os.getenv('MAX_NEW_TOKENS','300')))),
                'response_format':{'type':'json_object','schema':schema},
                'chat_template_kwargs':{'enable_thinking':False},'reasoning_effort':'none','cache_prompt':True})
            if time.monotonic() >= deadline:
                raise TimeoutError('Local generation timed out.')
            choice = result['choices'][0]
            if choice.get('finish_reason') != 'stop':
                raise ValueError('Local model output was truncated; retry with a focused alert.')
            content = choice['message']['content']
            if not isinstance(content,str):
                raise ValueError('Local model returned no text.')
            self.last_timings = result.get('timings',{})
            self.progress.update(input_tokens=result.get('usage',{}).get('prompt_tokens',0),
                                 generated_tokens=result.get('usage',{}).get('completion_tokens',0))
            return content
        finally:
            self.progress['phase'] = 'idle'

    def close(self):
        process,self._process = self._process,None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        if self._log is not None:
            self._log.close()
            self._log = None
