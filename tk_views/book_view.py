import tkinter as tk
from tkinter import messagebox

from tk_client import APIError

from . import theme as T
from .images import load_image
from .widgets import VScroll, danger_button, primary_button, styled_text


STAGE_NAMES = {
    0: "New", 1: "Learned", 2: "Review 1", 3: "Review 2", 4: "Review 3", 5: "Mastered"
}


class BookView(tk.Frame):
    def __init__(self, master, client, on_start_study):
        super().__init__(master, bg=T.BG)
        self.client = client
        self.on_start_study = on_start_study
        self._selected_id = None
        self._build()

    def _build(self):
        top = tk.Frame(self, bg=T.BG)
        top.pack(fill="x", padx=32, pady=(24, 12))

        self.counts_label = tk.Label(
            top, bg=T.BG, fg=T.TEXT_MUTED, font=T.FONT_BASE, anchor="w"
        )
        self.counts_label.pack(side="left")

        self.start_btn = primary_button(top, text="Start Learning", command=self._start)
        self.start_btn.pack(side="right")

        body = tk.Frame(self, bg=T.BG)
        body.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        left_wrap = tk.Frame(body, bg=T.BG, width=300)
        left_wrap.pack(side="left", fill="y")
        left_wrap.pack_propagate(False)

        self.list_scroll = VScroll(left_wrap, bg=T.BG)
        self.list_scroll.pack(fill="both", expand=True)

        tk.Frame(body, bg=T.BORDER, width=1).pack(side="left", fill="y", padx=16)

        self.detail = tk.Frame(body, bg=T.BG)
        self.detail.pack(side="left", fill="both", expand=True)
        self._empty_detail()

    def refresh(self):
        try:
            words = self.client.get("/api/words")
            counts = self.client.get("/api/counts")
        except APIError:
            return

        self.counts_label.configure(
            text=f"{counts['due']} due today  ·  {counts['total']} total  ·  {counts['mastered']} mastered"
        )
        self.start_btn.set_state("normal" if counts["due"] > 0 else "disabled")

        self.list_scroll.clear()

        if not words:
            tk.Label(
                self.list_scroll.inner,
                text="Your book is empty.\nUse Search to add words.",
                bg=T.BG,
                fg=T.TEXT_MUTED,
                font=T.FONT_SMALL,
                justify="left",
            ).pack(padx=12, pady=16, anchor="w")
            self._selected_id = None
            self._empty_detail()
            return

        for w in words:
            self._render_row(w)

        if self._selected_id and any(w["id"] == self._selected_id for w in words):
            self._show_detail(self._selected_id)
        else:
            self._selected_id = None
            self._empty_detail()

    def _render_row(self, w):
        is_selected = w["id"] == self._selected_id
        row_bg = T.ACCENT_SOFT if is_selected else T.BG

        outer = tk.Frame(self.list_scroll.inner, bg=row_bg, cursor="hand2")
        outer.pack(fill="x")
        inner = tk.Frame(outer, bg=row_bg)
        inner.pack(fill="x", padx=10, pady=8)

        tk.Label(
            inner, text=w["text"], bg=row_bg, fg=T.TEXT, font=T.FONT_BOLD, anchor="w"
        ).pack(anchor="w")

        meta = tk.Frame(inner, bg=row_bg)
        meta.pack(fill="x", pady=(2, 0))
        tk.Label(
            meta,
            text=STAGE_NAMES.get(w["stage"], f"Stage {w['stage']}"),
            bg=row_bg,
            fg=T.STAGE_COLORS.get(w["stage"], T.TEXT_MUTED),
            font=T.FONT_SMALL,
        ).pack(side="left")
        tk.Label(meta, text="  ·  ", bg=row_bg, fg=T.TEXT_MUTED, font=T.FONT_SMALL).pack(side="left")
        tk.Label(
            meta, text=f"next: {w['next_review_date']}", bg=row_bg, fg=T.TEXT_MUTED, font=T.FONT_SMALL
        ).pack(side="left")

        tk.Frame(self.list_scroll.inner, height=1, bg=T.BORDER).pack(fill="x")

        def on_click(_):
            self._selected_id = w["id"]
            self.refresh()

        for widget in (outer, inner, *inner.winfo_children()):
            widget.bind("<Button-1>", on_click)
            for child in widget.winfo_children():
                child.bind("<Button-1>", on_click)

    def _empty_detail(self):
        for w in self.detail.winfo_children():
            w.destroy()
        tk.Label(
            self.detail,
            text="Select a word to view and edit its definitions.",
            bg=T.BG,
            fg=T.TEXT_MUTED,
            font=T.FONT_BASE,
        ).pack(padx=12, pady=40)

    def _show_detail(self, word_id):
        for w in self.detail.winfo_children():
            w.destroy()

        try:
            data = self.client.get(f"/api/words/{word_id}")
        except APIError:
            self._empty_detail()
            return

        header = tk.Frame(self.detail, bg=T.BG)
        header.pack(fill="x", pady=(4, 8))

        tk.Label(
            header, text=data["text"], bg=T.BG, fg=T.TEXT, font=T.FONT_HEAD
        ).pack(side="left")

        if data.get("phonetic"):
            tk.Label(
                header, text=data["phonetic"], bg=T.BG, fg=T.TEXT_MUTED, font=T.FONT_ITALIC
            ).pack(side="left", padx=12, pady=(10, 0))

        del_btn = danger_button(header, text="Remove from book", command=lambda: self._delete(data))
        del_btn.pack(side="right")

        p = data.get("progress") or {}
        tk.Label(
            self.detail,
            text=f"Stage: {STAGE_NAMES.get(p.get('stage', 0), '')}  ·  next review: {p.get('next_review_date', '')}",
            bg=T.BG,
            fg=T.STAGE_COLORS.get(p.get("stage", 0), T.TEXT_MUTED),
            font=T.FONT_SMALL,
            anchor="w",
        ).pack(fill="x", pady=(0, 12))

        if data.get("image_url"):
            img_label = tk.Label(self.detail, bg=T.BG)
            img_label.pack(anchor="w", pady=(0, 8))
            load_image(img_label, data["image_url"], max_w=260, max_h=200)

        scroll = VScroll(self.detail, bg=T.BG)
        scroll.pack(fill="both", expand=True)

        for i, d in enumerate(data["definitions"]):
            row = tk.Frame(scroll.inner, bg=T.BG)
            row.pack(fill="x", pady=(4, 10))

            if d.get("part_of_speech"):
                tk.Label(
                    row, text=d["part_of_speech"], bg=T.BG, fg=T.TEXT_MUTED, font=T.FONT_SMALL
                ).pack(anchor="w")

            tk.Label(
                row,
                text=f"{i+1}. {d['meaning']}",
                bg=T.BG,
                fg=T.TEXT,
                font=T.FONT_BASE,
                wraplength=480,
                justify="left",
                anchor="w",
            ).pack(anchor="w", fill="x", pady=(2, 4))

            tk.Label(
                row, text="Example (auto-saves on blur)", bg=T.BG, fg=T.TEXT_MUTED, font=T.FONT_SMALL
            ).pack(anchor="w")

            txt = styled_text(row, height=2)
            txt.insert("1.0", d.get("example") or "")
            txt.pack(fill="x", pady=(2, 0))

            def_id = d["id"]

            def save(_evt=None, widget=txt, did=def_id):
                try:
                    self.client.patch(f"/api/definitions/{did}", {"example": widget.get("1.0", "end").strip()})
                except APIError:
                    pass

            txt.bind("<FocusOut>", save)
            tk.Frame(scroll.inner, height=1, bg=T.BORDER).pack(fill="x")

    def _delete(self, data):
        if not messagebox.askyesno("Remove word", f'Remove "{data["text"]}" from your book?'):
            return
        try:
            self.client.delete(f"/api/words/{data['id']}")
        except APIError as e:
            messagebox.showerror("Delete failed", e.message)
            return
        self._selected_id = None
        self.refresh()

    def _start(self):
        self.on_start_study()
