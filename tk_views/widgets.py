import tkinter as tk

from . import theme as T


class ColorButton(tk.Label):
    """A Label that behaves like a button. macOS Aqua's tk.Button ignores bg
    colors; using a Label gives us reliable solid-colored buttons."""

    def __init__(
        self,
        parent,
        text,
        command,
        bg=T.ACCENT,
        fg="white",
        hover_bg=T.ACCENT_HOVER,
        disabled_bg=T.ACCENT_DISABLED,
        disabled_fg="white",
        padx=16,
        pady=8,
        font=None,
    ):
        super().__init__(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=font or T.FONT_BOLD,
            padx=padx,
            pady=pady,
            cursor="hand2",
            bd=0,
            highlightthickness=0,
        )
        self._command = command
        self._normal_bg = bg
        self._normal_fg = fg
        self._hover_bg = hover_bg
        self._disabled_bg = disabled_bg
        self._disabled_fg = disabled_fg
        self._state = "normal"

        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_click(self, _event):
        if self._state == "normal" and self._command:
            self._command()

    def _on_enter(self, _event):
        if self._state == "normal":
            self.configure(bg=self._hover_bg)

    def _on_leave(self, _event):
        if self._state == "normal":
            self.configure(bg=self._normal_bg)

    def set_state(self, state, bg=None, fg=None):
        """state = 'normal' or 'disabled'. Optional bg/fg override disabled styling."""
        self._state = state
        if state == "disabled":
            self.configure(
                bg=bg or self._disabled_bg,
                fg=fg or self._disabled_fg,
                cursor="arrow",
            )
        else:
            self.configure(
                bg=bg or self._normal_bg,
                fg=fg or self._normal_fg,
                cursor="hand2",
            )
            if bg:
                self._normal_bg = bg
            if fg:
                self._normal_fg = fg

    def set_theme(self, bg, hover_bg, fg="white"):
        self._normal_bg = bg
        self._hover_bg = hover_bg
        self._normal_fg = fg
        if self._state == "normal":
            self.configure(bg=bg, fg=fg)


def primary_button(parent, text, command, **kwargs):
    """Back-compat shim — returns a ColorButton (Label-based)."""
    return ColorButton(parent, text=text, command=command, **kwargs)


def ghost_button(parent, text, command, **kwargs):
    b = tk.Button(
        parent,
        text=text,
        command=command,
        bg=T.BG,
        fg=T.TEXT_MUTED,
        activebackground=T.BG_SOFT,
        activeforeground=T.TEXT,
        relief="flat",
        font=T.FONT_BASE,
        padx=10,
        pady=5,
        cursor="hand2",
        bd=0,
        highlightthickness=0,
        **kwargs,
    )
    return b


def danger_button(parent, text, command, **kwargs):
    b = tk.Button(
        parent,
        text=text,
        command=command,
        bg=T.BG,
        fg=T.DANGER,
        activebackground=T.DANGER_SOFT,
        activeforeground=T.DANGER,
        relief="flat",
        font=T.FONT_BASE,
        padx=10,
        pady=5,
        cursor="hand2",
        bd=0,
        highlightthickness=0,
        **kwargs,
    )
    return b


def outline_button(parent, text, command, fg=None, **kwargs):
    b = tk.Button(
        parent,
        text=text,
        command=command,
        bg=T.BG,
        fg=fg or T.TEXT,
        activebackground=T.BG_SOFT,
        activeforeground=fg or T.TEXT,
        relief="flat",
        font=T.FONT_BASE,
        padx=24,
        pady=10,
        cursor="hand2",
        bd=0,
        highlightthickness=1,
        highlightbackground=T.BORDER,
        **kwargs,
    )
    return b


def styled_entry(parent, show=None):
    e = tk.Entry(
        parent,
        font=T.FONT_BASE,
        bg=T.BG_SOFT,
        fg=T.TEXT,
        relief="flat",
        highlightthickness=1,
        highlightbackground=T.BORDER,
        highlightcolor=T.ACCENT,
        insertbackground=T.TEXT,
        show=show or "",
    )
    return e


def styled_text(parent, height=2):
    t = tk.Text(
        parent,
        height=height,
        wrap="word",
        font=T.FONT_ITALIC,
        bg=T.BG_SOFT,
        fg=T.TEXT,
        relief="flat",
        highlightthickness=1,
        highlightbackground=T.BORDER,
        highlightcolor=T.ACCENT,
        padx=8,
        pady=6,
    )
    return t


class VScroll(tk.Frame):
    """A vertically scrollable frame. Children go inside .inner."""

    def __init__(self, master, bg=T.BG, **kwargs):
        super().__init__(master, bg=bg, **kwargs)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        from tkinter import ttk
        self.scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)

        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind(
            "<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind(
            "<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width)
        )
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")

        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel, add="+")

    def _on_mousewheel(self, event):
        # Only scroll if this canvas is rendered
        try:
            self.canvas.yview_scroll(int(-1 * (event.delta)), "units")
        except tk.TclError:
            pass

    def clear(self):
        for w in self.inner.winfo_children():
            w.destroy()
