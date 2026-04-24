import socket
import threading
import tkinter as tk
from http.server import ThreadingHTTPServer

import db
from main import Handler
from tk_client import APIError, Client
from tk_views.auth_view import AuthView
from tk_views.main_view import MainView


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_embedded_server():
    db.init_db()
    port = find_free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, port


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Word & Phrase")
        self.geometry("1000x680")
        self.minsize(820, 560)
        self.configure(bg="#FFFFFF")

        self.server, port = start_embedded_server()
        self.client = Client(f"http://127.0.0.1:{port}")

        self.current_view = None
        self._decide_initial_view()

    def _swap(self, factory):
        if self.current_view is not None:
            self.current_view.destroy()
        self.current_view = factory()
        self.current_view.pack(fill="both", expand=True)

    def _decide_initial_view(self):
        try:
            me = self.client.get("/api/me")
        except APIError:
            me = {"user": None}
        if me and me.get("user"):
            self._show_main(me["user"])
        else:
            self._show_auth()

    def _show_auth(self):
        self._swap(lambda: AuthView(self, self.client, on_success=self._show_main))

    def _show_main(self, user):
        self._swap(lambda: MainView(self, self.client, user, on_logout=self._show_auth))


if __name__ == "__main__":
    App().mainloop()
