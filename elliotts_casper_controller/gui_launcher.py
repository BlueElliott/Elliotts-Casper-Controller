"""Tkinter desktop launcher for Elliott's Casper Controller."""
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import scrolledtext, messagebox
import webbrowser

import pystray
from PIL import Image, ImageDraw

from elliotts_casper_controller import __version__
from elliotts_casper_controller.config_manager import load as load_config
from elliotts_casper_controller.core import start_server, stop_server, api_server_start, api_server_stop
from elliotts_casper_controller.amcp_client import AMCPClient

# ---------------------------------------------------------------------------
# Colours (matching web UI)
# ---------------------------------------------------------------------------
BG      = "#1a1a1a"
CARD    = "#2d2d2d"
BORDER  = "#3d3d3d"
ACCENT  = "#00bcd4"
TEXT    = "#ffffff"
MUTED   = "#888888"
SUCCESS = "#22c55e"
ERROR   = "#ef4444"
WARNING = "#f59e0b"

# ---------------------------------------------------------------------------
# Tray icon
# ---------------------------------------------------------------------------

def _make_tray_icon() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([4, 4, 60, 60], fill=ACCENT)
    d.rectangle([22, 20, 42, 44], fill="white")
    return img


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class CasperLauncher:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"Elliott's Casper Controller v{__version__}")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._cfg = load_config()
        self._web_port = self._cfg.get("web_port", 5280)
        self._log_lines: list[str] = []
        self._tray: pystray.Icon | None = None
        self._build_ui()
        self._start_web_server()
        self._poll_status()

    def _build_ui(self):
        root = self.root

        # Title bar
        title_frame = tk.Frame(root, bg=CARD, padx=16, pady=12)
        title_frame.pack(fill="x")
        tk.Label(title_frame, text="Elliott's Casper Controller",
                 bg=CARD, fg=TEXT, font=("Segoe UI", 14, "bold")).pack(side="left")
        tk.Label(title_frame, text=f"v{__version__}",
                 bg=CARD, fg=MUTED, font=("Segoe UI", 10)).pack(side="left", padx=8)

        # Status bar
        status_frame = tk.Frame(root, bg=BG, padx=16, pady=10)
        status_frame.pack(fill="x")
        self._status_canvas = tk.Canvas(status_frame, width=14, height=14, bg=BG, highlightthickness=0)
        self._status_canvas.pack(side="left")
        self._status_dot = self._status_canvas.create_oval(2, 2, 12, 12, fill=ERROR, outline="")
        self._status_label = tk.Label(status_frame, text="CasparCG: Stopped",
                                       bg=BG, fg=TEXT, font=("Segoe UI", 11))
        self._status_label.pack(side="left", padx=8)

        # Control buttons
        ctrl_frame = tk.Frame(root, bg=BG, padx=16, pady=4)
        ctrl_frame.pack(fill="x")
        self._btn_start = tk.Button(ctrl_frame, text="Start CasparCG", command=self._start_caspar,
                                     bg=SUCCESS, fg="white", relief="flat", padx=14, pady=8,
                                     font=("Segoe UI", 10, "bold"), cursor="hand2", activebackground="#16a34a")
        self._btn_start.pack(side="left", padx=(0, 6))
        self._btn_stop = tk.Button(ctrl_frame, text="Stop", command=self._stop_caspar,
                                    bg=ERROR, fg="white", relief="flat", padx=14, pady=8,
                                    font=("Segoe UI", 10), cursor="hand2", activebackground="#dc2626",
                                    state="disabled")
        self._btn_stop.pack(side="left", padx=(0, 6))
        tk.Button(ctrl_frame, text="Open Web UI", command=self._open_browser,
                  bg=ACCENT, fg="white", relief="flat", padx=14, pady=8,
                  font=("Segoe UI", 10), cursor="hand2", activebackground="#0097a7").pack(side="left")

        # Channel restart buttons
        ch_outer = tk.Frame(root, bg=BG, padx=16, pady=8)
        ch_outer.pack(fill="x")
        tk.Label(ch_outer, text="CHANNEL RESTARTS", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 6))
        ch_frame = tk.Frame(ch_outer, bg=BG)
        ch_frame.pack(fill="x")
        self._cfg = load_config()
        for ch in self._cfg["channels"]:
            btn = tk.Button(
                ch_frame,
                text=f"↺  {ch['name']}",
                command=lambda n=ch["number"], name=ch["name"]: self._restart_channel(n, name),
                bg=BORDER, fg=TEXT, relief="flat", padx=10, pady=6,
                font=("Segoe UI", 9), cursor="hand2", activebackground="#555555",
            )
            btn.pack(side="left", padx=(0, 6))
        tk.Button(
            ch_frame, text="↺  All",
            command=self._restart_all,
            bg=WARNING, fg="black", relief="flat", padx=10, pady=6,
            font=("Segoe UI", 9, "bold"), cursor="hand2", activebackground="#d97706",
        ).pack(side="left", padx=(0, 6))

        # Separator
        tk.Frame(root, bg=BORDER, height=1).pack(fill="x", padx=16, pady=6)

        # Log
        log_outer = tk.Frame(root, bg=BG, padx=16, pady=4)
        log_outer.pack(fill="both", expand=True)
        tk.Label(log_outer, text="LOG", bg=BG, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self._log_widget = scrolledtext.ScrolledText(
            log_outer, bg="#111111", fg="#aaaaaa", relief="flat",
            font=("Consolas", 9), height=10, state="disabled",
            insertbackground=TEXT,
        )
        self._log_widget.pack(fill="both", expand=True, pady=(4, 0))
        self._log_widget.tag_config("ok",    foreground=SUCCESS)
        self._log_widget.tag_config("error", foreground=ERROR)
        self._log_widget.tag_config("warn",  foreground=WARNING)

        # Bottom padding
        tk.Frame(root, bg=BG, height=8).pack()

        root.geometry("640x500")

    def _log(self, msg: str, tag: str = "") -> None:
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        self._log_widget.configure(state="normal")
        self._log_widget.insert("end", line, tag if tag else ())
        self._log_widget.see("end")
        self._log_widget.configure(state="disabled")

    def _start_web_server(self):
        self._log(f"Starting web server on port {self._web_port}...")
        threading.Thread(target=lambda: start_server(self._web_port, open_browser=False), daemon=True).start()
        self._log(f"Web UI: http://127.0.0.1:{self._web_port}", "ok")

    def _open_browser(self):
        webbrowser.open(f"http://127.0.0.1:{self._web_port}")

    def _start_caspar(self):
        self._btn_start.config(state="disabled", text="Starting...")
        self._log("Starting CasparCG...")
        def run():
            try:
                api_server_start()
                self.root.after(0, lambda: self._log("CasparCG started and channels loaded.", "ok"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"Failed to start: {e}", "error"))
            finally:
                self.root.after(0, lambda: self._btn_start.config(state="normal", text="Start CasparCG"))
        threading.Thread(target=run, daemon=True).start()

    def _stop_caspar(self):
        def run():
            api_server_stop()
            self.root.after(0, lambda: self._log("CasparCG stopped.", "warn"))
        threading.Thread(target=run, daemon=True).start()

    def _restart_channel(self, number: int, name: str):
        self._log(f"Restarting CH{number} ({name})...")
        cfg = load_config()
        channels = {ch["number"]: ch for ch in cfg["channels"]}
        ch = channels.get(number)
        if not ch:
            return
        def run():
            client = AMCPClient(port=cfg["amcp_port"])
            client.stop_channel(number)
            time.sleep(0.5)
            res = client.play_html(number, ch["url"])
            self.root.after(0, lambda: self._log(f"CH{number} ({name}) restarted -> {res[:60]}", "ok"))
        threading.Thread(target=run, daemon=True).start()

    def _restart_all(self):
        self._log("Restarting all channels...")
        cfg = load_config()
        def run():
            client = AMCPClient(port=cfg["amcp_port"])
            for ch in cfg["channels"]:
                client.stop_channel(ch["number"])
                time.sleep(0.3)
                res = client.play_html(ch["number"], ch["url"])
                self.root.after(0, lambda n=ch["number"], r=res: self._log(f"CH{n} restarted -> {r[:60]}", "ok"))
        threading.Thread(target=run, daemon=True).start()

    def _poll_status(self):
        def check():
            try:
                cfg = load_config()
                client = AMCPClient(port=cfg["amcp_port"])
                running = client.ping()
                color = SUCCESS if running else ERROR
                label = "CasparCG: Running" if running else "CasparCG: Stopped"
                self.root.after(0, lambda: self._status_canvas.itemconfig(self._status_dot, fill=color))
                self.root.after(0, lambda: self._status_label.config(text=label))
                stop_state = "normal" if running else "disabled"
                self.root.after(0, lambda: self._btn_stop.config(state=stop_state))
            except Exception:
                pass
            self.root.after(3000, self._poll_status)
        threading.Thread(target=check, daemon=True).start()

    def _setup_tray(self):
        icon_img = _make_tray_icon()
        menu = pystray.Menu(
            pystray.MenuItem("Open Web UI", lambda: webbrowser.open(f"http://127.0.0.1:{self._web_port}")),
            pystray.MenuItem("Restart All Channels", lambda: self._restart_all()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit),
        )
        self._tray = pystray.Icon("ElliotsCasperController", icon_img, "Casper Controller", menu)
        threading.Thread(target=self._tray.run, daemon=True).start()

    def _on_close(self):
        self.root.withdraw()
        self._setup_tray()

    def _quit(self):
        if messagebox.askokcancel("Quit", "Stop the web server and quit?"):
            stop_server()
            if self._tray:
                self._tray.stop()
            self.root.destroy()
            sys.exit(0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def launch():
    root = tk.Tk()
    app = CasperLauncher(root)
    root.mainloop()


def main():
    launch()


if __name__ == "__main__":
    main()
