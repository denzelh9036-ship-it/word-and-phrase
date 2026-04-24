import json
import ssl
import urllib.error
import urllib.parse
import urllib.request


API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{}"
WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
LOREMFLICKR_URL = "https://loremflickr.com/json/480/360/{}/all"


class WordNotFound(Exception):
    pass


class LookupError_(Exception):
    pass


def lookup(text):
    query = text.strip()
    if not query:
        raise LookupError_("Empty query")

    url = API_URL.format(urllib.parse.quote(query))
    req = urllib.request.Request(url, headers={"User-Agent": "WordAndPhrase/1.0"})

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
    definitions = []

    for entry in data:
        if not phonetic:
            if entry.get("phonetic"):
                phonetic = entry["phonetic"]
            else:
                for p in entry.get("phonetics", []) or []:
                    if p.get("text"):
                        phonetic = p["text"]
                        break
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

    return {"word": query, "phonetic": phonetic, "definitions": definitions}


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
    req = urllib.request.Request(url, headers={"User-Agent": "WordAndPhrase/1.0"})
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
    # Keyword search: use the first word only for multi-word phrases so
    # "make up" → "make" gets a hit rather than zero results.
    keyword = word.strip().split()[0] if word.strip() else ""
    if not keyword:
        return ""
    url = LOREMFLICKR_URL.format(urllib.parse.quote(keyword))
    req = urllib.request.Request(url, headers={"User-Agent": "WordAndPhrase/1.0"})
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=6, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return ""
    return data.get("file") or ""
