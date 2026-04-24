import tkinter as tk

from tk_client import APIError

from . import theme as T
from .book_view import BookView
from .search_view import SearchView
from .study_view import StudyView
from .widgets import ghost_button


class MainView(tk.Frame):
    def __init__(self, master, client, user, on_logout):
        super().__init__(master, bg=T.BG)
        self.client = client
        self.user = user
        self.on_logout = on_logout

        self._tab_buttons = {}
        self._views = {}
        self._current_tab = None
        self._build()

    def _build(self):
        top = tk.Frame(self, bg=T.BG)
        top.pack(fill="x")

        tk.Label(
            top, text="Word & Phrase", bg=T.BG, fg=T.TEXT, font=T.FONT_BRAND, padx=24
        ).pack(side="left", pady=14)

        self._search_tab_btn = self._make_tab(top, "search", "Search")
        self._search_tab_btn.pack(side="left", pady=14)
        self._book_tab_btn = self._make_tab(top, "book", "My Book")
        self._book_tab_btn.pack(side="left", pady=14)

        user_wrap = tk.Frame(top, bg=T.BG)
        user_wrap.pack(side="right", padx=24, pady=14)
        tk.Label(
            user_wrap, text=self.user["username"], bg=T.BG, fg=T.TEXT_MUTED, font=T.FONT_SMALL
        ).pack(side="left", padx=(0, 8))
        ghost_button(user_wrap, text="Log out", command=self._logout).pack(side="left")

        tk.Frame(self, height=1, bg=T.BORDER).pack(fill="x")

        self.body = tk.Frame(self, bg=T.BG)
        self.body.pack(fill="both", expand=True)

        self._views["search"] = SearchView(self.body, self.client, on_added=self._on_word_added)
        self._views["book"] = BookView(self.body, self.client, on_start_study=self._start_study)
        self._views["study"] = StudyView(self.body, self.client, on_exit=self._exit_study)

        self._switch("search")

    def _make_tab(self, parent, name, label):
        btn = tk.Button(
            parent,
            text=label,
            command=lambda: self._switch(name),
            bg=T.BG,
            fg=T.TEXT_MUTED,
            activebackground=T.BG,
            activeforeground=T.TEXT,
            relief="flat",
            font=T.FONT_BASE,
            padx=14,
            pady=6,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self._tab_buttons[name] = btn
        return btn

    def _switch(self, name):
        # highlight the active tab
        for n, btn in self._tab_buttons.items():
            if n == name:
                btn.configure(fg=T.TEXT, font=(T.FONT_FAMILY, 13, "bold"))
            else:
                btn.configure(fg=T.TEXT_MUTED, font=T.FONT_BASE)

        for v in self._views.values():
            v.pack_forget()

        self._views[name].pack(fill="both", expand=True)
        self._current_tab = name

        if name == "book":
            self._views["book"].refresh()

    def _on_word_added(self):
        # Book will refresh on next switch
        pass

    def _start_study(self):
        for btn in self._tab_buttons.values():
            btn.configure(state="disabled")
        for v in self._views.values():
            v.pack_forget()
        self._views["study"].pack(fill="both", expand=True)
        self._views["study"].start()

    def _exit_study(self):
        for btn in self._tab_buttons.values():
            btn.configure(state="normal")
        self._views["study"].pack_forget()
        self._switch("book")

    def _logout(self):
        try:
            self.client.post("/api/logout")
        except APIError:
            pass
        self.on_logout()
