import os
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path


_DEFAULT_APP_DIR = Path.home() / "Library" / "Application Support" / "WordAndPhrase"
APP_DIR = Path(os.environ.get("WORDPHRASE_DB_DIR") or _DEFAULT_APP_DIR)
DB_PATH = APP_DIR / "app.db"


def _connect():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with _connect() as conn:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "users" not in tables:
            # Fresh install OR upgrade from pre-accounts single-user data.
            # User chose to wipe on upgrade.
            conn.executescript(
                """
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
            )


# ---------- users ----------

def create_user(username, password_hash, salt):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
            (username, password_hash, salt, now),
        )
        return cur.lastrowid


def find_user_by_username(username):
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)
        ).fetchone()
        return dict(row) if row else None


def find_user_by_id(user_id):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


# ---------- sessions ----------

def create_session(token, user_id, expires_at):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, now, expires_at),
        )


def find_user_by_session(token):
    if not token:
        return None
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT u.* FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ? AND s.expires_at > ?
            """,
            (token, now),
        ).fetchone()
        return dict(row) if row else None


def destroy_session(token):
    if not token:
        return
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


# ---------- words (all scoped by user_id) ----------

def find_word(user_id, text):
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM words WHERE user_id = ? AND text = ? COLLATE NOCASE",
            (user_id, text),
        ).fetchone()
        return dict(row) if row else None


def find_word_by_id(user_id, word_id):
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM words WHERE id = ? AND user_id = ?",
            (word_id, user_id),
        ).fetchone()
        return dict(row) if row else None


def add_word(user_id, text, phonetic, defs, image_url=""):
    today = date.today().isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO words (user_id, text, phonetic, added_at, image_url) VALUES (?, ?, ?, ?, ?)",
            (user_id, text, phonetic, today, image_url or ""),
        )
        word_id = cur.lastrowid
        for d in defs:
            conn.execute(
                "INSERT INTO definitions (word_id, part_of_speech, meaning, example) VALUES (?, ?, ?, ?)",
                (word_id, d.get("pos"), d["meaning"], d.get("example") or ""),
            )
        conn.execute(
            "INSERT INTO progress (word_id, stage, next_review_date) VALUES (?, 0, ?)",
            (word_id, today),
        )
        return word_id


def set_image_url(user_id, word_id, url):
    with _connect() as conn:
        conn.execute(
            "UPDATE words SET image_url = ? WHERE id = ? AND user_id = ?",
            (url or "", word_id, user_id),
        )


def delete_word(user_id, word_id):
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM words WHERE id = ? AND user_id = ?",
            (word_id, user_id),
        )
        return cur.rowcount > 0


def list_saved_words(user_id):
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT w.id, w.text, w.phonetic, w.added_at, w.image_url,
                   p.stage, p.next_review_date, p.correct_count, p.wrong_count
            FROM words w
            JOIN progress p ON p.word_id = w.id
            WHERE w.user_id = ?
            ORDER BY w.added_at DESC, w.id DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_word_with_defs(user_id, word_id):
    with _connect() as conn:
        w = conn.execute(
            "SELECT * FROM words WHERE id = ? AND user_id = ?",
            (word_id, user_id),
        ).fetchone()
        if not w:
            return None
        defs = conn.execute(
            "SELECT id, part_of_speech, meaning, example FROM definitions WHERE word_id = ? ORDER BY id",
            (word_id,),
        ).fetchall()
        p = conn.execute(
            "SELECT stage, next_review_date, correct_count, wrong_count FROM progress WHERE word_id = ?",
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
        # Verify ownership: the definition must belong to a word owned by user_id
        row = conn.execute(
            """
            SELECT d.id FROM definitions d
            JOIN words w ON w.id = d.word_id
            WHERE d.id = ? AND w.user_id = ?
            """,
            (definition_id, user_id),
        ).fetchone()
        if not row:
            return False
        conn.execute(
            "UPDATE definitions SET example = ? WHERE id = ?",
            (new_example, definition_id),
        )
        return True


def update_progress(user_id, word_id, stage, next_review_date, correct_delta=0, wrong_delta=0):
    today = date.today().isoformat()
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE progress
            SET stage = ?,
                next_review_date = ?,
                correct_count = correct_count + ?,
                wrong_count   = wrong_count   + ?,
                last_seen     = ?
            WHERE word_id = ?
              AND word_id IN (SELECT id FROM words WHERE user_id = ?)
            """,
            (stage, next_review_date, correct_delta, wrong_delta, today, word_id, user_id),
        )
        return cur.rowcount > 0


def counts(user_id):
    with _connect() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM words WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        mastered = conn.execute(
            """
            SELECT COUNT(*) FROM progress p
            JOIN words w ON w.id = p.word_id
            WHERE w.user_id = ? AND p.stage >= 5
            """,
            (user_id,),
        ).fetchone()[0]
        due = conn.execute(
            """
            SELECT COUNT(*) FROM progress p
            JOIN words w ON w.id = p.word_id
            WHERE w.user_id = ? AND p.stage < 5 AND p.next_review_date <= date('now')
            """,
            (user_id,),
        ).fetchone()[0]
        return {"total": total, "mastered": mastered, "due": due}


def due_word_ids(user_id):
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT p.word_id FROM progress p
            JOIN words w ON w.id = p.word_id
            WHERE w.user_id = ? AND p.stage < 5 AND p.next_review_date <= date('now')
            ORDER BY p.next_review_date ASC, p.word_id ASC
            """,
            (user_id,),
        ).fetchall()
        return [r[0] for r in rows]
