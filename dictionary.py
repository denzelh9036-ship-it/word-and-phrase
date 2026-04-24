import json
import ssl
import urllib.error
import urllib.parse
import urllib.request


API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{}"
WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"


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
    """Return a thumbnail URL from Wikipedia summary, or '' if unavailable."""
    if not word or not word.strip():
        return ""
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
