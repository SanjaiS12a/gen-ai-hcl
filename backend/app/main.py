import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from app.db import Store, StaleAlertError
from app.models import Alert, AlertPage, IngestRequest, NotesRequest, StatusRequest, CopilotResult, QuestionRequest, ScopedChatResponse
from app.llm.providers import get_provider
from app.llm.copilot import Copilot
from app.report import render_report


def alert_id(value: str) -> int:
    try:
        number = int(value.upper().removeprefix('ALR-'))
        if number < 1:
            raise ValueError()
        return number
    except ValueError:
        raise HTTPException(422, 'Use an alert number such as 1002 or ALR-1002.')


def create_app(db_path=None, provider=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        app.state.store = Store(db_path or os.getenv('DB_PATH', 'data/copilot.db'))
        app.state.copilot = Copilot(app.state.store, provider or get_provider())
        yield
        app.state.copilot.close()

    app = FastAPI(title='Local SOC Incident-Response Copilot', lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173'], allow_methods=['GET','POST','PUT','PATCH'], allow_headers=['Content-Type'])

    @app.exception_handler(KeyError)
    async def missing(request: Request, exc: KeyError):
        return JSONResponse(status_code=404, content={'detail':'Alert not found.'})

    @app.exception_handler(StaleAlertError)
    async def stale(request: Request, exc: StaleAlertError):
        return JSONResponse(status_code=409,content={'detail':str(exc)})

    def store() -> Store:
        return app.state.store

    @app.get('/health')
    def health():
        p = app.state.copilot.provider
        return {'status':'ok', 'provider':p.name, 'model':p.model_name, 'model_status':p.status}

    @app.post('/api/alerts/{aid}/explain', response_model=CopilotResult)
    def explain(aid: str, regenerate: bool=False, rules_only: bool=False):
        # FastAPI runs synchronous endpoints in its threadpool.
        return app.state.copilot.explain(store().get(alert_id(aid)),regenerate,rules_only)

    @app.post('/api/alerts/{aid}/chat', response_model=ScopedChatResponse)
    def chat(aid: str, request: QuestionRequest):
        return app.state.copilot.chat(store().get(alert_id(aid)),request.question,request.rules_only)

    @app.get('/api/alerts/{aid}/chat')
    def messages(aid: str):
        return store().messages(alert_id(aid))

    @app.get('/api/alerts', response_model=AlertPage)
    def alerts(severity: str | None=None, status: str | None=None, type: str | None=None, q: str | None=Query(None,max_length=200), page: int=Query(1,ge=1), page_size: int=Query(20,ge=1,le=100)):
        return store().list(severity,status,type,q,page,page_size)

    @app.post('/api/alerts', response_model=Alert, status_code=201)
    def ingest(request: IngestRequest):
        return store().ingest(request)

    @app.get('/api/alerts/{aid}', response_model=Alert)
    def get(aid: str):
        return store().get(alert_id(aid))

    @app.patch('/api/alerts/{aid}/status', response_model=Alert)
    def status(aid: str, request: StatusRequest):
        return store().status(alert_id(aid),request.status)

    @app.get('/api/alerts/{aid}/notes')
    def notes(aid: str):
        return store().notes(alert_id(aid))

    @app.put('/api/alerts/{aid}/notes')
    def save_notes(aid: str, request: NotesRequest):
        return store().notes(alert_id(aid),request.text)

    @app.get('/api/alerts/{aid}/report.md')
    def report(aid: str, rules_only: bool=False):
        alert = store().get(alert_id(aid))
        result = store().cached(alert.id,app.state.copilot.cache_key(rules_only))
        text = render_report(alert,store().notes(alert.id)['text'],result)
        return Response(text, media_type='text/markdown', headers={'Content-Disposition':f'attachment; filename="{alert.display_id}.md"'})

    @app.get('/api/stats')
    def stats():
        return store().stats()

    @app.get('/api/history')
    def history(page: int=Query(1,ge=1), page_size: int=Query(20,ge=1,le=100)):
        return store().history(page,page_size)

    @app.post('/api/seed')
    def seed():
        return store().seed()

    return app


app = create_app()
