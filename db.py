import os
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path


DATABASE_URL = os.environ.get("DATABASE_URL")
USE_PG = bool(DATABASE_URL)

if USE_PG:
    import psycopg
    from psycopg.rows import dict_row


_DEFAULT_APP_DIR = Path.home() / "Library" / "Application Support" / "WordAndPhrase"
APP_DIR = Path(os.environ.get("WORDPHRASE_DB_DIR") or _DEFAULT_APP_DIR)
DB_PATH = APP_DIR / "app.db"


def _connect():
    if USE_PG:
        return psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=False)
    APP_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _q(sql):
    return sql.replace("?", "%s") if USE_PG else sql


def _today_sql():
    return "CURRENT_DATE" if USE_PG else "date('now')"


def _insert_returning_id(conn, sql, params):
    """Run an INSERT and return the new row id, dialect-agnostically."""
    if USE_PG:
        cur = conn.execute(_q(sql) + " RETURNING id", params)
        return cur.fetchone()["id"]
    cur = conn.execute(sql, params)
    return cur.lastrowid


def _row_to_dict(row):
    if row is None:
        return None
    return dict(row)


# ---------- schema ----------

_SQLITE_DDL = """
DROP TABLE IF EXISTS progress;
DROP TABLE IF EXISTS definitions;
DROP TABLE IF EXISTS words;

CREATE TABLE users (
    id            INTEGER PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX idx_sessions_user ON sessions(user_id);

CREATE TABLE words (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text       TEXT NOT NULL COLLATE NOCASE,
    phonetic   TEXT,
    added_at   TEXT NOT NULL,
    image_url  TEXT,
    UNIQUE(user_id, text)
);
CREATE INDEX idx_words_user ON words(user_id);

CREATE TABLE definitions (
    id              INTEGER PRIMARY KEY,
    word_id         INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
    part_of_speech  TEXT,
    meaning         TEXT NOT NULL,
    example         TEXT
);

CREATE TABLE progress (
    word_id           INTEGER PRIMARY KEY REFERENCES words(id) ON DELETE CASCADE,
    stage             INTEGER NOT NULL DEFAULT 0,
    next_review_date  TEXT NOT NULL,
    correct_count     INTEGER NOT NULL DEFAULT 0,
    wrong_count       INTEGER NOT NULL DEFAULT 0,
    last_seen         TEXT
);
"""

_PG_DDL = [
    """
    CREATE TABLE users (
        id            BIGSERIAL PRIMARY KEY,
        username      TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        salt          TEXT NOT NULL,
        created_at    TEXT NOT NULL
    )
    """,
    "CREATE UNIQUE INDEX users_username_lower ON users (LOWER(username))",
    """
    CREATE TABLE sessions (
        token      TEXT PRIMARY KEY,
        user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX idx_sessions_user ON sessions(user_id)",
    """
    CREATE TABLE words (
        id         BIGSERIAL PRIMARY KEY,
        user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        text       TEXT NOT NULL,
        phonetic   TEXT,
        added_at   TEXT NOT NULL,
        image_url  TEXT
    )
    """,
    "CREATE UNIQUE INDEX words_user_text_lower ON words (user_id, LOWER(text))",
    "CREATE INDEX idx_words_user ON words(user_id)",
    """
    CREATE TABLE definitions (
        id              BIGSERIAL PRIMARY KEY,
        word_id         BIGINT NOT NULL REFERENCES words(id) ON DELETE CASCADE,
        part_of_speech  TEXT,
        meaning         TEXT NOT NULL,
        example         TEXT
    )
    """,
    """
    CREATE TABLE progress (
        word_id           BIGINT PRIMARY KEY REFERENCES words(id) ON DELETE CASCADE,
        stage             INTEGER NOT NULL DEFAULT 0,
        next_review_date  TEXT NOT NULL,
        correct_count     INTEGER NOT NULL DEFAULT 0,
        wrong_count       INTEGER NOT NULL DEFAULT 0,
        last_seen         TEXT
    )
    """,
]


def _users_table_exists(conn):
    if USE_PG:
        row = conn.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'users'"
        ).fetchone()
        return row is not None
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchall()
    return len(rows) > 0


def init_db():
    if USE_PG:
        with _connect() as conn:
            if not _users_table_exists(conn):
                for stmt in _PG_DDL:
                    conn.execute(stmt)
            conn.commit()
        return

    with _connect() as conn:
        if not _users_table_exists(conn):
            # Fresh install OR upgrade from pre-accounts single-user data.
            # User chose to wipe on upgrade.
            conn.executescript(_SQLITE_DDL)


# ---------- users ----------

def create_user(username, password_hash, salt):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        new_id = _insert_returning_id(
            conn,
            "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
            (username, password_hash, salt, now),
        )
        if USE_PG:
            conn.commit()
        return new_id


def find_user_by_username(username):
    with _connect() as conn:
        if USE_PG:
            sql = "SELECT * FROM users WHERE LOWER(username) = LOWER(%s)"
        else:
            sql = "SELECT * FROM users WHERE username = ? COLLATE NOCASE"
        row = conn.execute(sql, (username,)).fetchone()
        return _row_to_dict(row)


def find_user_by_id(user_id):
    with _connect() as conn:
        row = conn.execute(_q("SELECT * FROM users WHERE id = ?"), (user_id,)).fetchone()
        return _row_to_dict(row)


# ---------- sessions ----------

def create_session(token, user_id, expires_at):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            _q("INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)"),
            (token, user_id, now, expires_at),
        )
        if USE_PG:
            conn.commit()


def find_user_by_session(token):
    if not token:
        return None
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        row = conn.execute(
            _q(
                """
                SELECT u.* FROM sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token = ? AND s.expires_at > ?
                """
            ),
            (token, now),
        ).fetchone()
        return _row_to_dict(row)


def destroy_session(token):
    if not token:
        return
    with _connect() as conn:
        conn.execute(_q("DELETE FROM sessions WHERE token = ?"), (token,))
        if USE_PG:
            conn.commit()


# ---------- words (all scoped by user_id) ----------

def find_word(user_id, text):
    with _connect() as conn:
        if USE_PG:
            sql = "SELECT * FROM words WHERE user_id = %s AND LOWER(text) = LOWER(%s)"
        else:
            sql = "SELECT * FROM words WHERE user_id = ? AND text = ? COLLATE NOCASE"
        row = conn.execute(sql, (user_id, text)).fetchone()
        return _row_to_dict(row)


def find_word_by_id(user_id, word_id):
    with _connect() as conn:
        row = conn.execute(
            _q("SELECT * FROM words WHERE id = ? AND user_id = ?"),
            (word_id, user_id),
        ).fetchone()
        return _row_to_dict(row)


def add_word(user_id, text, phonetic, defs, image_url=""):
    today = date.today().isoformat()
    with _connect() as conn:
        word_id = _insert_returning_id(
            conn,
            "INSERT INTO words (user_id, text, phonetic, added_at, image_url) VALUES (?, ?, ?, ?, ?)",
            (user_id, text, phonetic, today, image_url or ""),
        )
        for d in defs:
            conn.execute(
                _q(
                    "INSERT INTO definitions (word_id, part_of_speech, meaning, example) VALUES (?, ?, ?, ?)"
                ),
                (word_id, d.get("pos"), d["meaning"], d.get("example") or ""),
            )
        conn.execute(
            _q("INSERT INTO progress (word_id, stage, next_review_date) VALUES (?, 0, ?)"),
            (word_id, today),
        )
        if USE_PG:
            conn.commit()
        return word_id


def set_image_url(user_id, word_id, url):
    with _connect() as conn:
        conn.execute(
            _q("UPDATE words SET image_url = ? WHERE id = ? AND user_id = ?"),
            (url or "", word_id, user_id),
        )
        if USE_PG:
            conn.commit()


def delete_word(user_id, word_id):
    with _connect() as conn:
        cur = conn.execute(
            _q("DELETE FROM words WHERE id = ? AND user_id = ?"),
            (word_id, user_id),
        )
        if USE_PG:
            conn.commit()
        return cur.rowcount > 0


def list_saved_words(user_id):
    with _connect() as conn:
        rows = conn.execute(
            _q(
                """
                SELECT w.id, w.text, w.phonetic, w.added_at, w.image_url,
                       p.stage, p.next_review_date, p.correct_count, p.wrong_count
                FROM words w
                JOIN progress p ON p.word_id = w.id
                WHERE w.user_id = ?
                ORDER BY w.added_at DESC, w.id DESC
                """
            ),
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_word_with_defs(user_id, word_id):
    with _connect() as conn:
        w = conn.execute(
            _q("SELECT * FROM words WHERE id = ? AND user_id = ?"),
            (word_id, user_id),
        ).fetchone()
        if not w:
            return None
        defs = conn.execute(
            _q(
                "SELECT id, part_of_speech, meaning, example FROM definitions WHERE word_id = ? ORDER BY id"
            ),
            (word_id,),
        ).fetchall()
        p = conn.execute(
            _q(
                "SELECT stage, next_review_date, correct_count, wrong_count FROM progress WHERE word_id = ?"
            ),
            (word_id,),
        ).fetchone()
        return {
            "id": w["id"],
            "text": w["text"],
            "phonetic": w["phonetic"],
            "added_at": w["added_at"],
            "image_url": w["image_url"] or "",
            "definitions": [dict(d) for d in defs],
            "progress": dict(p) if p else None,
        }


def update_example(user_id, definition_id, new_example):
    with _connect() as conn:
        row = conn.execute(
            _q(
                """
                SELECT d.id FROM definitions d
                JOIN words w ON w.id = d.word_id
                WHERE d.id = ? AND w.user_id = ?
                """
            ),
            (definition_id, user_id),
        ).fetchone()
        if not row:
            return False
        conn.execute(
            _q("UPDATE definitions SET example = ? WHERE id = ?"),
            (new_example, definition_id),
        )
        if USE_PG:
            conn.commit()
        return True


def update_progress(user_id, word_id, stage, next_review_date, correct_delta=0, wrong_delta=0):
    today = date.today().isoformat()
    with _connect() as conn:
        cur = conn.execute(
            _q(
                """
                UPDATE progress
                SET stage = ?,
                    next_review_date = ?,
                    correct_count = correct_count + ?,
                    wrong_count   = wrong_count   + ?,
                    last_seen     = ?
                WHERE word_id = ?
                  AND word_id IN (SELECT id FROM words WHERE user_id = ?)
                """
            ),
            (stage, next_review_date, correct_delta, wrong_delta, today, word_id, user_id),
        )
        if USE_PG:
            conn.commit()
        return cur.rowcount > 0


def counts(user_id):
    with _connect() as conn:
        total = conn.execute(
            _q("SELECT COUNT(*) AS c FROM words WHERE user_id = ?"), (user_id,)
        ).fetchone()
        mastered = conn.execute(
            _q(
                """
                SELECT COUNT(*) AS c FROM progress p
                JOIN words w ON w.id = p.word_id
                WHERE w.user_id = ? AND p.stage >= 5
                """
            ),
            (user_id,),
        ).fetchone()
        due = conn.execute(
            _q(
                f"""
                SELECT COUNT(*) AS c FROM progress p
                JOIN words w ON w.id = p.word_id
                WHERE w.user_id = ? AND p.stage < 5 AND p.next_review_date <= {_today_sql()}
                """
            ),
            (user_id,),
        ).fetchone()
        return {
            "total": _scalar(total),
            "mastered": _scalar(mastered),
            "due": _scalar(due),
        }


def _scalar(row):
    if row is None:
        return 0
    if USE_PG:
        return row["c"]
    # sqlite3.Row supports both index and key access
    try:
        return row["c"]
    except (IndexError, KeyError):
        return row[0]


def due_word_ids(user_id):
    with _connect() as conn:
        rows = conn.execute(
            _q(
                f"""
                SELECT p.word_id FROM progress p
                JOIN words w ON w.id = p.word_id
                WHERE w.user_id = ? AND p.stage < 5 AND p.next_review_date <= {_today_sql()}
                ORDER BY p.next_review_date ASC, p.word_id ASC
                """
            ),
            (user_id,),
        ).fetchall()
        return [r["word_id"] for r in rows]
