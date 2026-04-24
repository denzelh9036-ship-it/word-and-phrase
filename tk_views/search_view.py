import sys
import threading
import tkinter as tk
import traceback
import urllib.parse

from tk_client import APIError

from . import theme as T
from .images import load_image
from .widgets import VScroll, primary_button, styled_entry, styled_text


class SearchView(tk.Frame):
    def __init__(self, master, client, on_added):
        super().__init__(master, bg=T.BG)
        self.client = client
        self.on_added = on_added
        self._current = None
        self._build()

    def _build(self):
        top = tk.Frame(self, bg=T.BG)
        top.pack(fill="x", padx=32, pady=(24, 8))

        self.entry = styled_entry(top)
        self.entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        self.entry.bind("<Return>", lambda _: self._search())

        self.search_btn = primary_button(top, text="Search", command=self._search)
        self.search_btn.pack(side="right")

        self.status = tk.Label(
            self, text="", bg=T.BG, fg=T.TEXT_MUTED, font=T.FONT_SMALL, anchor="w"
        )
        self.status.pack(fill="x", padx=32)

        self.result = VScroll(self, bg=T.BG)
        self.result.pack(fill="both", expand=True, padx=32, pady=12)

    def _search(self):
        q = self.entry.get().strip()
        if not q:
            return
        self.search_btn.configure(text="Searching…")
        self.search_btn.set_state("disabled")
        self._set_status("Looking up…", T.TEXT_MUTED)
        self.result.clear()
        self._current = None

        def worker():
            try:
                encoded = urllib.parse.quote(q)
                data = self.client.get(f"/api/search?q={encoded}")
            except APIError as e:
                self.after(0, lambda err=e: self._show_error(err))
                return
            except Exception as e:
                traceback.print_exc(file=sys.stderr)
                msg = f"{type(e).__name__}: {e}"
                self.after(0, lambda m=msg: self._show_generic_error(m))
                return
            self.after(0, lambda d=data: self._show(d))

        threading.Thread(target=worker, daemon=True).start()

    def _show_generic_error(self, msg):
        self.search_btn.configure(text="Search")
        self.search_btn.set_state("normal")
        self._set_status(msg, T.DANGER)

    def _set_status(self, text, color):
        self.status.configure(text=text, fg=color)

    def _show_error(self, e):
        self.search_btn.configure(text="Search")
        self.search_btn.set_state("normal")
        if e.status == 404:
            self._set_status(f"\"{self.entry.get().strip()}\" not found.", T.DANGER)
        else:
            self._set_status(e.message or "Lookup failed.", T.DANGER)

    def _show(self, data):
        self.search_btn.configure(text="Search")
        self.search_btn.set_state("normal")
        self._set_status("", T.TEXT_MUTED)
        self._current = data

        header = tk.Frame(self.result.inner, bg=T.BG)
        header.pack(fill="x", pady=(4, 8))

        tk.Label(
            header, text=data["word"], bg=T.BG, fg=T.TEXT, font=T.FONT_WORD
        ).pack(side="left")

        if data.get("phonetic"):
            tk.Label(
                header,
                text=data["phonetic"],
                bg=T.BG,
                fg=T.TEXT_MUTED,
                font=T.FONT_ITALIC,
            ).pack(side="left", padx=12, pady=(10, 0))

        already = data.get("already_saved")
        self.add_btn = primary_button(
            header,
            text="✓ Added" if already else "+ Add to My Book",
            command=self._add,
        )
        self.add_btn.pack(side="right")
        if already:
            self.add_btn.set_state("disabled", bg=T.BG_SOFT, fg=T.TEXT_MUTED)

        if data.get("image_url"):
            img_label = tk.Label(self.result.inner, bg=T.BG)
            img_label.pack(anchor="w", pady=(4, 8))
            load_image(img_label, data["image_url"], max_w=260, max_h=200)

        self._example_widgets = []
        for i, d in enumerate(data["definitions"]):
            row = tk.Frame(self.result.inner, bg=T.BG)
            row.pack(fill="x", pady=(6, 10))

            if d.get("pos"):
                tk.Label(
                    row, text=d["pos"], bg=T.BG, fg=T.TEXT_MUTED, font=T.FONT_SMALL
                ).pack(anchor="w")

            tk.Label(
                row,
                text=f"{i+1}. {d['meaning']}",
                bg=T.BG,
                fg=T.TEXT,
                font=T.FONT_BASE,
                wraplength=680,
                justify="left",
                anchor="w",
            ).pack(anchor="w", fill="x", pady=(2, 4))

            tk.Label(
                row, text="Example", bg=T.BG, fg=T.TEXT_MUTED, font=T.FONT_SMALL
            ).pack(anchor="w")

            ex = styled_text(row, height=2)
            ex.insert("1.0", d.get("example") or "")
            ex.pack(fill="x", pady=(2, 0))
            self._example_widgets.append(ex)

            tk.Frame(self.result.inner, height=1, bg=T.BORDER).pack(fill="x")

    def _add(self):
        if not self._current:
            return
        defs = []
        for i, d in enumerate(self._current["definitions"]):
            example = self._example_widgets[i].get("1.0", "end").strip()
            defs.append(
                {
                    "pos": d.get("pos", ""),
                    "meaning": d["meaning"],
                    "example": example,
                }
            )
        self.add_btn.configure(text="Adding…")
        self.add_btn.set_state("disabled")
        try:
            self.client.post(
                "/api/words",
                {
                    "word": self._current["word"],
                    "phonetic": self._current.get("phonetic", ""),
                    "image_url": self._current.get("image_url", ""),
                    "definitions": defs,
                },
            )
        except APIError as e:
            self._set_status(e.message or "Failed to add.", T.DANGER)
            self.add_btn.configure(text="+ Add to My Book")
            self.add_btn.set_state("normal")
            return
        self.add_btn.configure(text="✓ Added")
        self.add_btn.set_state("disabled", bg=T.BG_SOFT, fg=T.TEXT_MUTED)
        self._set_status("Added to My Book.", T.SUCCESS)
        self.on_added()
