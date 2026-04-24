import json
import urllib.error
import urllib.parse
import urllib.request


class APIError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class Client:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.cookie = ""

    def _request(self, method, path, body=None, timeout=20):
        url = self.base_url + path
        data = None
        headers = {"Accept": "application/json", "User-Agent": "WordAndPhrase-Tk/1.0"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.cookie:
            headers["Cookie"] = self.cookie

        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                set_cookie = resp.headers.get("Set-Cookie", "")
                if set_cookie:
                    self._absorb_set_cookie(set_cookie)
                text = resp.read().decode("utf-8")
                return json.loads(text) if text else None
        except urllib.error.HTTPError as e:
            try:
                payload = json.loads(e.read().decode("utf-8"))
                msg = payload.get("error") or f"HTTP {e.code}"
            except Exception:
                msg = f"HTTP {e.code}"
            raise APIError(e.code, msg)
        except urllib.error.URLError as e:
            raise APIError(0, f"Network error: {e.reason}")

    def _absorb_set_cookie(self, header_value):
        first = header_value.split(";", 1)[0].strip()
        if "=" in first:
            name, value = first.split("=", 1)
            if value == "":
                self.cookie = ""
            else:
                self.cookie = f"{name}={value}"

    def get(self, path):
        return self._request("GET", path)

    def post(self, path, body=None):
        return self._request("POST", path, body)

    def patch(self, path, body=None):
        return self._request("PATCH", path, body)

    def delete(self, path):
        return self._request("DELETE", path)
