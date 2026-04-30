import html
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache


API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{}"
WIKTIONARY_DEF_URL = "https://en.wiktionary.org/api/rest_v1/page/definition/{}"
WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
LOREMFLICKR_URL = "https://loremflickr.com/json/480/360/{}/all"
DATAMUSE_URL = "https://api.datamuse.com/words?sp={}&max={}"

USER_AGENT = "WordAndPhrase/1.0"
_TAG_RE = re.compile(r"<[^>]+>")


class WordNotFound(Exception):
    pass


class LookupError_(Exception):
    pass


def lookup(text):
    query = text.strip()
    if not query:
        raise LookupError_("Empty query")
    try:
        return _lookup_dictionaryapi(query)
    except WordNotFound:
        result = _lookup_wiktionary(query)
        if result:
            return result
        raise


def _lookup_dictionaryapi(query):
    url = API_URL.format(urllib.parse.quote(query))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise WordNotFound(query)
        raise LookupError_(f"HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        raise LookupError_(f"Network error: {e.reason}")
    except Exception as e:
        raise LookupError_(str(e))
    return _parse(query, data)


def _parse(query, data):
    if not isinstance(data, list) or not data:
        raise WordNotFound(query)

    phonetic = ""
    audio_url = ""
    definitions = []

    for entry in data:
        for p in entry.get("phonetics", []) or []:
            if not phonetic and p.get("text"):
                phonetic = p["text"]
            if not audio_url and p.get("audio"):
                audio_url = p["audio"]
        if not phonetic and entry.get("phonetic"):
            phonetic = entry["phonetic"]
        for meaning in entry.get("meanings", []) or []:
            pos = meaning.get("partOfSpeech", "")
            for d in meaning.get("definitions", []) or []:
                text = d.get("definition")
                if not text:
                    continue
                definitions.append(
                    {
                        "pos": pos,
                        "meaning": text,
                        "example": d.get("example", "") or "",
                    }
                )

    if not definitions:
        raise WordNotFound(query)

    return {
        "word": query,
        "phonetic": phonetic,
        "audio_url": audio_url,
        "definitions": definitions,
    }


def _strip_html(s):
    if not s:
        return ""
    return html.unescape(_TAG_RE.sub("", s)).strip()


def _lookup_wiktionary(query):
    slug = urllib.parse.quote(query.strip().replace(" ", "_"))
    url = WIKTIONARY_DEF_URL.format(slug)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    entries = data.get("en") or []
    definitions = []
    for entry in entries:
        pos = (entry.get("partOfSpeech") or "").lower()
        for d in entry.get("definitions", []) or []:
            meaning = _strip_html(d.get("definition") or "")
            if not meaning:
                continue
            example = ""
            for ex in d.get("examples", []) or []:
                example = _strip_html(ex)
                if example:
                    break
            definitions.append({"pos": pos, "meaning": meaning, "example": example})

    if not definitions:
        return None

    return {
        "word": query,
        "phonetic": "",
        "audio_url": "",
        "definitions": definitions,
    }


def fetch_audio(word):
    """Fetch just the MP3 URL for a word — used to backfill words saved
    before audio_url was tracked. Returns '' on any failure."""
    if not word or not word.strip():
        return ""
    try:
        result = _lookup_dictionaryapi(word.strip())
    except (WordNotFound, LookupError_):
        return ""
    return result.get("audio_url") or ""


@lru_cache(maxsize=512)
def suggest(query, limit=8):
    q = (query or "").strip()
    if len(q) < 2:
        return ()
    url = DATAMUSE_URL.format(urllib.parse.quote(q), int(limit))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=4, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return ()
    if not isinstance(data, list):
        return ()
    return tuple(item["word"] for item in data if item.get("word"))


def fetch_image(word):
    """Return an image URL for `word` via Wikipedia (canonical) with a
    Loremflickr keyword fallback so abstract / adverb / verb words still
    get a picture. Returns '' only if both sources fail."""
    if not word or not word.strip():
        return ""
    return _fetch_wikipedia(word) or _fetch_loremflickr(word) or ""


def _fetch_wikipedia(word):
    slug = urllib.parse.quote(word.strip().replace(" ", "_"))
    url = WIKI_SUMMARY_URL.format(slug)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=6, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return ""
    thumb = (data.get("thumbnail") or {}).get("source") or ""
    orig = (data.get("originalimage") or {}).get("source") or ""
    return thumb or orig


def _fetch_loremflickr(word):
    keyword = word.strip().split()[0] if word.strip() else ""
    if not keyword:
        return ""
    url = LOREMFLICKR_URL.format(urllib.parse.quote(keyword))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=6, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return ""
    return data.get("file") or ""
