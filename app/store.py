from __future__ import annotations
import json, sqlite3, time
from contextlib import contextmanager
from pathlib import Path

class Store:
    def __init__(self, path: str | Path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript('''
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT NOT NULL UNIQUE,password TEXT NOT NULL,admin INTEGER NOT NULL DEFAULT 0,prefs TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS locations(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,data TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS loc_owner ON locations(user_id);
            CREATE TABLE IF NOT EXISTS launches(id TEXT PRIMARY KEY,data TEXT NOT NULL,seen REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS tracks(launch_id TEXT PRIMARY KEY,data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS subscriptions(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS deliveries(key TEXT PRIMARY KEY,user_id INTEGER NOT NULL,subscription_id TEXT NOT NULL,launch_id TEXT,location_id TEXT,net TEXT,kind TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',attempts INTEGER NOT NULL DEFAULT 0,next_try REAL NOT NULL,expires REAL NOT NULL,error TEXT);
            CREATE INDEX IF NOT EXISTS due_delivery ON deliveries(status,next_try);
            ''')
        self.path.chmod(0o600)
    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path,timeout=15)
        c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON")
        try:
            yield c; c.commit()
        except BaseException:
            c.rollback(); raise
        finally: c.close()
    def rows(self,sql,args=()):
        with self.connect() as c: return [dict(r) for r in c.execute(sql,args).fetchall()]
    def one(self,sql,args=()):
        rows=self.rows(sql,args); return rows[0] if rows else None
    def execute(self,sql,args=()):
        with self.connect() as c: return c.execute(sql,args).lastrowid
    def meta(self,key,default=None):
        r=self.one("SELECT value FROM meta WHERE key=?",(key,)); return json.loads(r["value"]) if r else default
    def set_meta(self,key,value):
        self.execute("INSERT INTO meta VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,json.dumps(value)))
    def hydrate(self, launch):
        from .acquisition import identity
        result=dict(launch)
        acquired=self.meta('acquired:'+launch['id'],{})
        if acquired.get('identity')==identity(launch) and acquired.get('valid_until',0)>time.time():
            result['acquisition']=acquired
        return result
    def launches(self, hydrate=True):
        rows=[json.loads(r["data"]) for r in self.rows("SELECT data FROM launches")]
        return sorted([self.hydrate(r) if hydrate else r for r in rows],key=lambda x:x['net'])
    def track(self,launch_id):
        r=self.one("SELECT data FROM tracks WHERE launch_id=?",(launch_id,)); return json.loads(r["data"]) if r else None
    def locations(self,user_id):
        return [{"id":r["id"],**json.loads(r["data"])} for r in self.rows("SELECT id,data FROM locations WHERE user_id=? ORDER BY rowid",(user_id,))]
