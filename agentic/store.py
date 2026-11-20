"""SQLite med stdlib. To tabeller: tråder vi har sett, og forslag per kjøring."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS threads (
    thread_id TEXT PRIMARY KEY, last_message_id TEXT, status TEXT NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT, thread_id TEXT NOT NULL, created_at TEXT NOT NULL,
    model TEXT, kind TEXT, summary TEXT, backoffice_action TEXT, reply_draft TEXT,
    needs_human INTEGER NOT NULL, confidence REAL, tool_calls TEXT, usage TEXT, outcome TEXT);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def close(self):
        self.db.close()

    def seen(self, thread_id, last_message_id):
        row = self.db.execute('SELECT last_message_id FROM threads WHERE thread_id=?', (thread_id,)).fetchone()
        return row is not None and row['last_message_id'] == last_message_id

    def mark(self, thread_id, last_message_id, status):
        self.db.execute('INSERT INTO threads VALUES (?,?,?,?,?) ON CONFLICT(thread_id) DO UPDATE SET '
                        'last_message_id=excluded.last_message_id, status=excluded.status, updated_at=excluded.updated_at',
                        (thread_id, last_message_id, status, now(), now()))
        self.db.commit()

    def add_proposal(self, thread_id, proposal, *, model, tool_calls, usage):
        self.db.execute('INSERT INTO proposals (thread_id, created_at, model, kind, summary, backoffice_action, reply_draft,'
                        ' needs_human, confidence, tool_calls, usage) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                        (thread_id, now(), model, proposal.get('kind'), proposal.get('summary'),
                         proposal.get('backoffice_action'), proposal.get('reply_draft'), int(bool(proposal.get('needs_human'))),
                         proposal.get('confidence'), json.dumps(tool_calls, ensure_ascii=False), json.dumps(usage)))
        self.db.commit()

    def proposals(self, limit=50):
        return [dict(r) for r in self.db.execute('SELECT * FROM proposals ORDER BY id DESC LIMIT ?', (limit,))]

    def set_outcome(self, proposal_id, outcome):
        """Bjørns dom etter kontroll i BRP: resolved | wrong | manual. Grunnlag for pris per løst sak."""
        self.db.execute('UPDATE proposals SET outcome=? WHERE id=?', (outcome, proposal_id))
        self.db.commit()
