import io
import threading
import urllib.error
import urllib.request

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False


_cache = {}  # url -> PhotoImage
_cache_lock = threading.Lock()


def load_image(label, url, max_w=240, max_h=200, timeout=8):
    """Load an image from URL into the given tk.Label asynchronously.

    - Resizes to fit within (max_w, max_h) preserving aspect ratio.
    - Caches PhotoImage by URL.
    - Silent no-op if Pillow is missing, URL is empty, or the fetch fails.
    """
    if not _PIL_OK or not url:
        return

    cache_key = (url, max_w, max_h)
    with _cache_lock:
        cached = _cache.get(cache_key)
    if cached is not None:
        _set(label, cached)
        return

    def worker():
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "WordAndPhrase/1.0"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            im = Image.open(io.BytesIO(raw))
            im.thumbnail((max_w, max_h), Image.LANCZOS)
            # Convert to a mode Tk can handle
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGBA")
        except (urllib.error.URLError, OSError, Exception):
            return

        def apply():
            try:
                photo = ImageTk.PhotoImage(im)
            except Exception:
                return
            with _cache_lock:
                _cache[cache_key] = photo
            _set(label, photo)

        # Schedule Tk work on main thread
        try:
            label.after(0, apply)
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True).start()


def _set(label, photo):
    try:
        label.configure(image=photo)
        label.image = photo  # keep a reference
    except Exception:
        pass
