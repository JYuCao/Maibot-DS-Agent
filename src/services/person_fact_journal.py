"""按真实用户证据持久去重，避免回复拆分、重启或删除后重复提取。"""

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List

import json
import sqlite3
import time


class PersonFactJournal:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=5)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS evidence_jobs (
                    session_id TEXT NOT NULL, person_id TEXT NOT NULL, message_id TEXT NOT NULL,
                    state TEXT NOT NULL, updated REAL NOT NULL,
                    PRIMARY KEY(session_id,person_id,message_id));
                CREATE TABLE IF NOT EXISTS journal_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
            self.path.chmod(0o600)
            with db:
                yield db
        finally:
            db.close()

    def claim(self, session_id: str, person_id: str, message_ids: List[str]) -> List[str]:
        if not session_id or not person_id or not message_ids or any(not mid for mid in message_ids):
            raise ValueError("人物事实去重必须使用真实会话、人物和消息 ID")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM journal_meta WHERE key='historical_seed'").fetchone():
                self._seed_history(db)
                db.execute("INSERT INTO journal_meta VALUES('historical_seed','1')")
            claimed = []
            for mid in dict.fromkeys(message_ids):
                if db.execute("INSERT OR IGNORE INTO evidence_jobs VALUES(?,?,?,'processing',?)",
                              (session_id, person_id, mid, time.time())).rowcount:
                    claimed.append(mid)
            return claimed

    def _seed_history(self, db: sqlite3.Connection) -> None:
        metadata_path = self.path.parent / "metadata" / "metadata.db"
        if not metadata_path.exists():
            return
        # 包括软删除的旧事实：删除不是请求从同一条聊天重新生成它。
        source = sqlite3.connect(metadata_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
        try:
            for (raw,) in source.execute("SELECT metadata FROM paragraphs"):
                meta = json.loads(raw or "{}")
                if meta.get("source_type") != "person_fact":
                    continue
                sid, pid = meta.get("chat_id", ""), meta.get("person_id", "")
                if sid and pid:
                    for mid in meta.get("evidence_message_ids", []):
                        if isinstance(mid, str) and mid:
                            db.execute("INSERT OR IGNORE INTO evidence_jobs VALUES(?,?,?,'historical',?)",
                                       (sid, pid, mid, time.time()))
        finally:
            source.close()

    def finish(self, session_id: str, person_id: str, message_ids: List[str], *, succeeded: bool) -> None:
        with self._connect() as db:
            db.executemany("UPDATE evidence_jobs SET state=?,updated=? WHERE session_id=? AND person_id=? AND message_id=?",
                           [("done" if succeeded else "failed", time.time(), session_id, person_id, mid) for mid in message_ids])
