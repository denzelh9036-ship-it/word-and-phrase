import tkinter as tk

from tk_client import APIError

from . import theme as T
from .images import load_image
from .widgets import ghost_button, outline_button, primary_button


class StudyView(tk.Frame):
    def __init__(self, master, client, on_exit):
        super().__init__(master, bg=T.BG_SOFT)
        self.client = client
        self.on_exit = on_exit
        self._queue = []
        self._idx = 0
        self._current = None
        self._revealed = False
        self._build()

    def _build(self):
        top = tk.Frame(self, bg=T.BG_SOFT)
        top.pack(fill="x", padx=32, pady=(20, 0))

        self.back_btn = ghost_button(top, text="← Back", command=self.on_exit)
        self.back_btn.pack(side="left")

        self.progress_label = tk.Label(
            top, bg=T.BG_SOFT, fg=T.TEXT_MUTED, font=T.FONT_SMALL
        )
        self.progress_label.pack(side="right")

        wrap = tk.Frame(self, bg=T.BG_SOFT)
        wrap.pack(fill="both", expand=True, padx=48, pady=24)

        self.card = tk.Frame(
            wrap, bg=T.BG, highlightthickness=1, highlightbackground=T.BORDER
        )
        self.card.pack(fill="both", expand=True)

        self.word_label = tk.Label(
            self.card, bg=T.BG, fg=T.TEXT, font=T.FONT_WORD_HUGE
        )
        self.word_label.pack(pady=(48, 8))

        self.phonetic_label = tk.Label(
            self.card, bg=T.BG, fg=T.TEXT_MUTED, font=T.FONT_ITALIC
        )
        self.phonetic_label.pack()

        self.defs_container = tk.Frame(self.card, bg=T.BG)
        self.defs_container.pack(fill="both", expand=True, padx=40, pady=(20, 12))

        self.button_row = tk.Frame(self.card, bg=T.BG)
        self.button_row.pack(pady=(8, 40))

    def start(self):
        try:
            self._queue = self.client.get("/api/study/session")
        except APIError:
            self._queue = []
        self._idx = 0
        self._show_current()

    def _show_current(self):
        for w in self.defs_container.winfo_children():
            w.destroy()
        for w in self.button_row.winfo_children():
            w.destroy()

        if self._idx >= len(self._queue):
            self.word_label.configure(text="All done for today! 🎉")
            self.phonetic_label.configure(text="")
            tk.Label(
                self.defs_container,
                text="Come back tomorrow, or add more words to your book.",
                bg=T.BG,
                fg=T.TEXT_MUTED,
                font=T.FONT_BASE,
            ).pack(pady=20)
            self.progress_label.configure(text="")
            return

        self._current = self._queue[self._idx]
        self._revealed = False
        self.progress_label.configure(text=f"{self._idx + 1} / {len(self._queue)}")
        self.word_label.configure(text=self._current["text"])
        self.phonetic_label.configure(text=self._current.get("phonetic") or "")

        dont = outline_button(
            self.button_row, text="Don't know", command=lambda: self._answer(False), fg=T.DANGER
        )
        dont.pack(side="left", padx=8)
        know = outline_button(
            self.button_row, text="Know", command=lambda: self._answer(True), fg=T.SUCCESS
        )
        know.pack(side="left", padx=8)

    def _answer(self, knew):
        if self._revealed:
            return
        self._revealed = True
        try:
            self.client.post("/api/answer", {"word_id": self._current["id"], "knew": knew})
        except APIError:
            pass
        self._reveal()

    def _reveal(self):
        if self._current.get("image_url"):
            img_label = tk.Label(self.defs_container, bg=T.BG)
            img_label.pack(pady=(0, 12))
            load_image(img_label, self._current["image_url"], max_w=260, max_h=180)

        for d in self._current["definitions"]:
            box = tk.Frame(self.defs_container, bg=T.BG)
            box.pack(fill="x", pady=(6, 6))

            if d.get("part_of_speech"):
                tk.Label(
                    box,
                    text=d["part_of_speech"],
                    bg=T.BG,
                    fg=T.TEXT_MUTED,
                    font=T.FONT_SMALL,
                ).pack(anchor="w")

            tk.Label(
                box,
                text=d["meaning"],
                bg=T.BG,
                fg=T.TEXT,
                font=T.FONT_BASE,
                wraplength=680,
                justify="left",
                anchor="w",
            ).pack(anchor="w", fill="x", pady=(2, 2))

            ex = (d.get("example") or "").strip()
            if ex:
                tk.Label(
                    box,
                    text=f"“{ex}”",
                    bg=T.BG,
                    fg=T.TEXT_MUTED,
                    font=T.FONT_ITALIC,
                    wraplength=680,
                    justify="left",
                    anchor="w",
                ).pack(anchor="w", fill="x", padx=(16, 0))

        for w in self.button_row.winfo_children():
            w.destroy()
        nxt = primary_button(self.button_row, text="Next →", command=self._next)
        nxt.pack(side="left", padx=8)

    def _next(self):
        self._idx += 1
        self._show_current()
