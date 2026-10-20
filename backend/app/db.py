import json
import sqlite3
from uuid import uuid4
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from app.models import Alert, AlertPage, IngestRequest
from app.services.analyzer import analyze_alert
from app.seed import sample_alerts


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class StaleAlertError(Exception):
    pass


class Store:
    def __init__(self, path: str):
        self.path = str(Path(path).resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS alerts (
              id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, origin TEXT NOT NULL,
              timestamp TEXT NOT NULL, raw_alert TEXT NOT NULL, baseline TEXT NOT NULL,
              type TEXT NOT NULL, severity TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'New');
            CREATE TABLE IF NOT EXISTS copilot_results (
              alert_id INTEGER NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
              cache_key TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL,
              PRIMARY KEY(alert_id,cache_key));
            CREATE TABLE IF NOT EXISTS chat_messages (
              id INTEGER PRIMARY KEY, alert_id INTEGER NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
              role TEXT NOT NULL, content TEXT NOT NULL, timestamp TEXT NOT NULL, metadata TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS notes (
              alert_id INTEGER PRIMARY KEY REFERENCES alerts(id) ON DELETE CASCADE,
              text TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS status_history (
              id INTEGER PRIMARY KEY, alert_id INTEGER NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
              old_status TEXT NOT NULL, new_status TEXT NOT NULL, timestamp TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS alerts_filters ON alerts(status,severity,type);
            CREATE INDEX IF NOT EXISTS messages_alert ON chat_messages(alert_id,id);
            ''')
            if 'revision' not in {r[1] for r in db.execute('PRAGMA table_info(alerts)')}:
                db.execute("ALTER TABLE alerts ADD COLUMN revision TEXT NOT NULL DEFAULT ''")
                db.execute('UPDATE alerts SET revision=?',(uuid4().hex,))
            empty = db.execute('SELECT COUNT(*) FROM alerts').fetchone()[0] == 0
        if empty:
            self.seed()

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def _insert(self, db, request, origin, aid=None):
        baseline = analyze_alert(request.raw_alert)
        timestamp = request.timestamp.isoformat() if request.timestamp else utcnow()
        cur = db.execute('INSERT INTO alerts(id,source,origin,timestamp,raw_alert,baseline,type,severity,revision) VALUES(?,?,?,?,?,?,?,?,?)',
                         (aid, request.source, origin, timestamp, request.raw_alert, baseline.model_dump_json(), baseline.incident_type, baseline.severity.value,uuid4().hex))
        return cur.lastrowid

    def seed(self):
        with self.connection() as db:
            db.execute("DELETE FROM alerts WHERE origin='simulated feed'")
            for row in sample_alerts():
                self._insert(db, IngestRequest(**{k:v for k,v in row.items() if k != 'id'}), 'simulated feed', row['id'])
        return {'reloaded':30, 'source':'simulated feed'}

    def ingest(self, request: IngestRequest) -> Alert:
        with self.connection() as db:
            aid = self._insert(db, request, 'webhook')
        return self.get(aid)

    @staticmethod
    def decode(row) -> Alert:
        return Alert(id=row['id'], revision=row['revision'], display_id=f"ALR-{row['id']}", title=json.loads(row['baseline'])['title'],
                     source=row['source'], origin=row['origin'], timestamp=row['timestamp'], status=row['status'],
                     raw_alert=row['raw_alert'], baseline=json.loads(row['baseline']))

    def get(self, aid: int) -> Alert:
        with self.connection() as db:
            row = db.execute('SELECT * FROM alerts WHERE id=?', (aid,)).fetchone()
        if row is None:
            raise KeyError(aid)
        return self.decode(row)

    def list(self, severity=None, status=None, type=None, q=None, page=1, page_size=20) -> AlertPage:
        clauses, values = [], []
        for key, value in [('severity',severity), ('status',status), ('type',type)]:
            if value:
                clauses.append(f'{key}=?')
                values.append(value)
        if q:
            clauses.append("(raw_alert LIKE ? OR source LIKE ? OR ('ALR-' || id) LIKE ?)")
            values.extend([f'%{q}%']*3)
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        with self.connection() as db:
            total = db.execute('SELECT COUNT(*) FROM alerts'+where, values).fetchone()[0]
            rows = db.execute('SELECT * FROM alerts'+where+' ORDER BY timestamp DESC,id DESC LIMIT ? OFFSET ?', values+[page_size, (page-1)*page_size]).fetchall()
        return AlertPage(items=[self.decode(r) for r in rows], total=total, page=page, page_size=page_size)

    def status(self, aid, status):
        with self.connection() as db:
            row = db.execute('SELECT status FROM alerts WHERE id=?', (aid,)).fetchone()
            if row is None:
                raise KeyError(aid)
            if row['status'] != status:
                db.execute('UPDATE alerts SET status=? WHERE id=?', (status,aid))
                db.execute('INSERT INTO status_history(alert_id,old_status,new_status,timestamp) VALUES(?,?,?,?)', (aid,row['status'],status,utcnow()))
        return self.get(aid)

    def notes(self, aid, text=None):
        self.get(aid)
        with self.connection() as db:
            if text is not None:
                db.execute('INSERT INTO notes VALUES(?,?,?) ON CONFLICT(alert_id) DO UPDATE SET text=excluded.text,updated_at=excluded.updated_at', (aid,text,utcnow()))
            row = db.execute('SELECT text,updated_at FROM notes WHERE alert_id=?', (aid,)).fetchone()
        return dict(row) if row else {'text':'', 'updated_at':None}

    def stats(self):
        with self.connection() as db:
            result = {f'by_{col}': {r[0]:r[1] for r in db.execute(f'SELECT {col},COUNT(*) FROM alerts GROUP BY {col}')} for col in ('severity','status','type')}
            result['over_time'] = [dict(time=r[0],count=r[1]) for r in db.execute('SELECT substr(timestamp,1,10),COUNT(*) FROM alerts GROUP BY substr(timestamp,1,10) ORDER BY 1')]
        result['open_count'] = sum(v for k,v in result['by_status'].items() if k != 'Closed')
        return result

    def history(self, page=1, page_size=20):
        with self.connection() as db:
            changes = db.execute('SELECT * FROM status_history ORDER BY id DESC LIMIT ? OFFSET ?', (page_size,(page-1)*page_size)).fetchall()
            total = db.execute('SELECT COUNT(*) FROM status_history').fetchone()[0]
        return {'closed':self.list(status='Closed',page=page,page_size=page_size).model_dump(), 'changes':[dict(r) for r in changes], 'changes_total':total}

    def cached(self, aid, key):
        with self.connection() as db:
            row = db.execute('SELECT result FROM copilot_results WHERE alert_id=? AND cache_key=?', (aid,key)).fetchone()
        return json.loads(row[0]) if row else None

    def cache(self, aid, key, result, revision):
        with self.connection() as db:
            self._check_revision(db,aid,revision)
            db.execute('INSERT INTO copilot_results VALUES(?,?,?,?) ON CONFLICT(alert_id,cache_key) DO UPDATE SET result=excluded.result,created_at=excluded.created_at', (aid,key,json.dumps(result),utcnow()))

    def messages(self, aid, limit=100):
        self.get(aid)
        with self.connection() as db:
            rows = db.execute('SELECT * FROM chat_messages WHERE alert_id=? ORDER BY id DESC LIMIT ?', (aid,limit)).fetchall()
        return [dict(r, metadata=json.loads(r['metadata'])) for r in reversed(rows)]

    @staticmethod
    def _check_revision(db,aid,revision):
        # Reserve the writer lock before checking, so reset cannot interleave.
        db.execute('UPDATE alerts SET revision=revision WHERE id=?',(aid,))
        row = db.execute('SELECT revision FROM alerts WHERE id=?',(aid,)).fetchone()
        if row is None or row['revision'] != revision:
            raise StaleAlertError('Sample alerts were reloaded while this request ran. Reload the alert and retry.')

    def exchange(self, aid, question, response, revision):
        with self.connection() as db:
            self._check_revision(db,aid,revision)
            for role, content in [('user',question), ('assistant',response['answer'])]:
                db.execute('INSERT INTO chat_messages(alert_id,role,content,timestamp,metadata) VALUES(?,?,?,?,?)', (aid,role,content,utcnow(),json.dumps({k:v for k,v in response.items() if k != 'answer'})))
