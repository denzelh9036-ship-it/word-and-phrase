import json
import mimetypes
import os
import sys
import traceback
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import auth
import db
import dictionary
import srs


HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8765"))
OPEN_BROWSER = os.environ.get("OPEN_BROWSER", "1") != "0"
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

PUBLIC_API = {"/api/register", "/api/login", "/api/me"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        if "/api/" in (self.path or ""):
            print(f"[{self.log_date_time_string()}] {self.command} {self.path} → {fmt % args}")

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except Exception:
            print(f"[ERROR] {self.command} {self.path}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            try:
                self._json(500, {"error": "internal_error"})
            except Exception:
                pass

    # ---------- helpers ----------

    def _json(self, status, payload, extra_headers=None):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _current_user(self):
        token = auth.parse_cookie(self.headers.get("Cookie"))
        user = db.find_user_by_session(token)
        return user, token

    def _require_user(self):
        user, _ = self._current_user()
        if not user:
            self._json(401, {"error": "unauthenticated"})
            return None
        return user

    def _serve_static(self, rel_path):
        if rel_path in ("", "/"):
            rel_path = "index.html"
        rel_path = rel_path.lstrip("/")
        safe_path = os.path.normpath(os.path.join(STATIC_DIR, rel_path))
        if not safe_path.startswith(STATIC_DIR):
            self.send_error(403)
            return
        if not os.path.isfile(safe_path):
            self.send_error(404)
            return
        ctype, _ = mimetypes.guess_type(safe_path)
        with open(safe_path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    # ---------- routing ----------

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # /api/me is public (returns null if not logged in)
        if path == "/api/me":
            user, _ = self._current_user()
            if not user:
                self._json(200, {"user": None})
            else:
                self._json(200, {"user": {"id": user["id"], "username": user["username"]}})
            return

        # All other /api/* requires auth
        if path.startswith("/api/"):
            user = self._require_user()
            if not user:
                return
            self._handle_authed_get(path, parsed, user)
            return

        # static files
        self._serve_static(path)

    def _handle_authed_get(self, path, parsed, user):
        if path == "/api/counts":
            self._json(200, db.counts(user["id"]))
            return

        if path == "/api/words":
            self._json(200, db.list_saved_words(user["id"]))
            return

        if path.startswith("/api/words/"):
            try:
                wid = int(path.rsplit("/", 1)[-1])
            except ValueError:
                self.send_error(404)
                return
            data = db.get_word_with_defs(user["id"], wid)
            if not data:
                self.send_error(404)
                return
            if not data.get("image_url"):
                url = dictionary.fetch_image(data["text"])
                if url:
                    db.set_image_url(user["id"], wid, url)
                    data["image_url"] = url
            if not data.get("audio_url"):
                aurl = dictionary.fetch_audio(data["text"])
                if aurl:
                    db.set_audio_url(user["id"], wid, aurl)
                    data["audio_url"] = aurl
            self._json(200, data)
            return

        if path == "/api/suggest":
            qs = urllib.parse.parse_qs(parsed.query)
            q = (qs.get("q") or [""])[0].strip()
            self._json(200, {"suggestions": list(dictionary.suggest(q))})
            return

        if path == "/api/study/session":
            ids = db.due_word_ids(user["id"])
            words = [db.get_word_with_defs(user["id"], i) for i in ids]
            self._json(200, [w for w in words if w])
            return

        if path == "/api/search":
            qs = urllib.parse.parse_qs(parsed.query)
            q = (qs.get("q") or [""])[0].strip()
            if not q:
                self._json(400, {"error": "missing q"})
                return
            try:
                entry = dictionary.lookup(q)
            except dictionary.WordNotFound:
                self._json(404, {"error": "not_found"})
                return
            except dictionary.LookupError_ as e:
                self._json(502, {"error": str(e)})
                return
            existing = db.find_word(user["id"], entry["word"])
            entry["already_saved"] = bool(existing)
            entry["image_url"] = dictionary.fetch_image(entry["word"])
            self._json(200, entry)
            return

        self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json()

        # Public auth routes
        if path == "/api/register":
            self._handle_register(body)
            return
        if path == "/api/login":
            self._handle_login(body)
            return
        if path == "/api/logout":
            self._handle_logout()
            return

        if path.startswith("/api/"):
            user = self._require_user()
            if not user:
                return
            self._handle_authed_post(path, body, user)
            return

        self.send_error(404)

    def _handle_register(self, body):
        username = (body.get("username") or "").strip()
        password = body.get("password") or ""

        err = auth.validate_username(username) or auth.validate_password(password)
        if err:
            self._json(400, {"error": err})
            return
        if db.find_user_by_username(username):
            self._json(409, {"error": "Username already taken"})
            return

        h, s = auth.hash_password(password)
        user_id = db.create_user(username, h, s)
        token = auth.new_session_token()
        db.create_session(token, user_id, auth.session_expiry())
        self._json(
            200,
            {"user": {"id": user_id, "username": username}},
            extra_headers={"Set-Cookie": auth.set_cookie_header(token)},
        )

    def _handle_login(self, body):
        username = (body.get("username") or "").strip()
        password = body.get("password") or ""
        if not username or not password:
            self._json(400, {"error": "Username and password required"})
            return
        user = db.find_user_by_username(username)
        if not user or not auth.verify_password(password, user["password_hash"], user["salt"]):
            self._json(401, {"error": "Invalid username or password"})
            return
        token = auth.new_session_token()
        db.create_session(token, user["id"], auth.session_expiry())
        self._json(
            200,
            {"user": {"id": user["id"], "username": user["username"]}},
            extra_headers={"Set-Cookie": auth.set_cookie_header(token)},
        )

    def _handle_logout(self):
        _, token = self._current_user()
        if token:
            db.destroy_session(token)
        self._json(
            200,
            {"ok": True},
            extra_headers={"Set-Cookie": auth.clear_cookie_header()},
        )

    def _handle_authed_post(self, path, body, user):
        if path == "/api/words":
            word = (body.get("word") or "").strip()
            if not word:
                self._json(400, {"error": "missing word"})
                return
            if db.find_word(user["id"], word):
                self._json(409, {"error": "already_saved"})
                return
            defs = body.get("definitions") or []
            clean = []
            for d in defs:
                meaning = (d.get("meaning") or "").strip()
                if not meaning:
                    continue
                clean.append(
                    {
                        "pos": (d.get("pos") or "").strip(),
                        "meaning": meaning,
                        "example": (d.get("example") or "").strip(),
                    }
                )
            if not clean:
                self._json(400, {"error": "no definitions"})
                return
            image_url = (body.get("image_url") or "").strip()
            if not image_url:
                image_url = dictionary.fetch_image(word)
            audio_url = (body.get("audio_url") or "").strip()
            wid = db.add_word(
                user["id"],
                word,
                (body.get("phonetic") or "").strip(),
                clean,
                image_url=image_url,
                audio_url=audio_url,
            )
            self._json(200, {"id": wid, "image_url": image_url, "audio_url": audio_url})
            return

        if path == "/api/answer":
            wid = body.get("word_id")
            knew = bool(body.get("knew"))
            if not isinstance(wid, int):
                self._json(400, {"error": "missing word_id"})
                return
            data = db.get_word_with_defs(user["id"], wid)
            if not data:
                self.send_error(404)
                return
            stage = data["progress"]["stage"] if data["progress"] else 0
            if knew:
                new_stage, next_date = srs.on_correct(stage)
                db.update_progress(user["id"], wid, new_stage, next_date, correct_delta=1)
            else:
                new_stage, next_date = srs.on_wrong(stage)
                db.update_progress(user["id"], wid, new_stage, next_date, wrong_delta=1)
            self._json(200, {"stage": new_stage, "next_review_date": next_date})
            return

        self.send_error(404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            user = self._require_user()
            if not user:
                return

            if path.startswith("/api/words/"):
                try:
                    wid = int(path.rsplit("/", 1)[-1])
                except ValueError:
                    self.send_error(404)
                    return
                if not db.delete_word(user["id"], wid):
                    self.send_error(404)
                    return
                self._json(200, {"ok": True})
                return

        self.send_error(404)

    def do_PATCH(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json()

        if path.startswith("/api/"):
            user = self._require_user()
            if not user:
                return

            if path.startswith("/api/definitions/"):
                try:
                    def_id = int(path.rsplit("/", 1)[-1])
                except ValueError:
                    self.send_error(404)
                    return
                ok = db.update_example(user["id"], def_id, (body.get("example") or "").strip())
                if not ok:
                    self.send_error(404)
                    return
                self._json(200, {"ok": True})
                return

        self.send_error(404)


def main():
    db.init_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"Word & Phrase running at {url}")
    print("Press Ctrl+C to stop.")
    if OPEN_BROWSER:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
