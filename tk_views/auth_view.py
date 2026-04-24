import tkinter as tk

from tk_client import APIError

from . import theme as T
from .widgets import primary_button, styled_entry


class AuthView(tk.Frame):
    def __init__(self, master, client, on_success):
        super().__init__(master, bg=T.BG_SOFT)
        self.client = client
        self.on_success = on_success
        self.mode = "login"  # or "register"
        self._build()

    def _build(self):
        outer = tk.Frame(self, bg=T.BG_SOFT)
        outer.pack(expand=True)

        card = tk.Frame(
            outer,
            bg=T.BG,
            highlightthickness=1,
            highlightbackground=T.BORDER,
        )
        card.pack(padx=24, pady=24, ipadx=28, ipady=24)
        card.configure(width=360)

        tk.Label(
            card, text="Word & Phrase", bg=T.BG, fg=T.TEXT, font=T.FONT_HEAD
        ).pack(anchor="w", pady=(8, 2))
        self.sub_label = tk.Label(
            card, bg=T.BG, fg=T.TEXT_MUTED, font=T.FONT_SMALL
        )
        self.sub_label.pack(anchor="w", pady=(0, 16))

        tk.Label(
            card, text="Username", bg=T.BG, fg=T.TEXT, font=T.FONT_SMALL
        ).pack(anchor="w")
        self.username = styled_entry(card)
        self.username.pack(fill="x", ipady=6, pady=(2, 10))

        tk.Label(
            card, text="Password", bg=T.BG, fg=T.TEXT, font=T.FONT_SMALL
        ).pack(anchor="w")
        self.password = styled_entry(card, show="•")
        self.password.pack(fill="x", ipady=6, pady=(2, 8))

        self.error_label = tk.Label(
            card, text="", bg=T.BG, fg=T.DANGER, font=T.FONT_SMALL, wraplength=320, justify="left"
        )
        self.error_label.pack(anchor="w", pady=(0, 6))

        self.submit_btn = primary_button(card, text="", command=self._submit)
        self.submit_btn.pack(fill="x", ipady=2, pady=(2, 12))

        toggle = tk.Frame(card, bg=T.BG)
        toggle.pack()
        self.toggle_text = tk.Label(toggle, bg=T.BG, fg=T.TEXT_MUTED, font=T.FONT_SMALL)
        self.toggle_text.pack(side="left")
        self.toggle_link = tk.Label(
            toggle, bg=T.BG, fg=T.ACCENT, font=T.FONT_SMALL, cursor="hand2"
        )
        self.toggle_link.pack(side="left", padx=(6, 0))
        self.toggle_link.bind("<Button-1>", lambda _: self._toggle_mode())

        self.username.bind("<Return>", lambda _: self.password.focus_set())
        self.password.bind("<Return>", lambda _: self._submit())

        self._apply_mode()
        self.username.focus_set()

    def _apply_mode(self):
        if self.mode == "login":
            self.sub_label.configure(text="Sign in to your account")
            self.submit_btn.configure(text="Sign in")
            self.toggle_text.configure(text="New here?")
            self.toggle_link.configure(text="Create an account")
        else:
            self.sub_label.configure(text="Create a new account")
            self.submit_btn.configure(text="Create account")
            self.toggle_text.configure(text="Already have an account?")
            self.toggle_link.configure(text="Sign in instead")
        self.error_label.configure(text="")

    def _toggle_mode(self):
        self.mode = "register" if self.mode == "login" else "login"
        self._apply_mode()

    def _submit(self):
        username = self.username.get().strip()
        password = self.password.get()
        if not username or not password:
            self.error_label.configure(text="Username and password required.")
            return

        path = "/api/login" if self.mode == "login" else "/api/register"
        self.submit_btn.set_state("disabled")
        self.error_label.configure(text="")

        try:
            res = self.client.post(path, {"username": username, "password": password})
        except APIError as e:
            self.error_label.configure(text=e.message)
            self.submit_btn.set_state("normal")
            return

        self.submit_btn.set_state("normal")
        self.password.delete(0, "end")
        self.on_success(res["user"])
