"""Launch, monitor, and stop the CasparCG server process."""
import os
import subprocess
import threading
import time
from typing import Optional

import psutil

from elliotts_casper_controller.amcp_client import AMCPClient

# Console colour: black bg (0), cyan text (B)
_CONSOLE_COLOR = "0B"


class CasparProcessManager:
    def __init__(self, exe_path: str, amcp_port: int = 5250, startup_delay: int = 8,
                 window_title: str = "PCR3 CasparCG - NDI Server"):
        self.exe_path = exe_path
        self.amcp_port = amcp_port
        self.startup_delay = startup_delay
        self.window_title = window_title
        self._process: Optional[subprocess.Popen] = None
        self._client = AMCPClient(port=amcp_port)

    def start(self, config: dict | None = None) -> bool:
        if self.is_running():
            return True
        if config:
            from elliotts_casper_controller.config_manager import regenerate_caspar_config
            regenerate_caspar_config(config)
        try:
            # Launch via cmd /k so we can set the console title and colour.
            # Using list form (no shell=True) avoids cmd quoting pitfalls.
            # cwd is already set to the exe directory so we just use the basename.
            exe_name = os.path.basename(self.exe_path)
            # Strip characters that break cmd title or quoting
            safe_title = self.window_title.replace('"', "'").replace('&', 'and')
            # Pass as a plain STRING (not a list) so Python skips list2cmdline.
            # list2cmdline would escape the inner quotes as \" which cmd.exe then
            # tries to execute literally as part of the filename.
            # casparcg.exe has no spaces so no inner quoting is needed.
            cmd = f'cmd /k "color {_CONSOLE_COLOR} && title {safe_title} && {exe_name}"'
            self._process = subprocess.Popen(
                cmd,
                cwd=self._exe_dir(),
            )
            deadline = time.time() + self.startup_delay + 5
            while time.time() < deadline:
                time.sleep(1)
                if self._client.ping():
                    # CasparCG sets its own console title at startup.
                    # Rename after a short delay so ours wins.
                    threading.Thread(
                        target=self._rename_console_after_delay,
                        daemon=True,
                    ).start()
                    return True
            return False
        except Exception:
            return False

    def stop(self) -> None:
        """Gracefully stop CasparCG then kill only our specific process tree."""
        self._client.send("BYE")
        time.sleep(1.5)
        if self._process and self._process.poll() is None:
            self._kill_tree(self._process.pid)
        self._process = None

    def is_running(self) -> bool:
        """Check if OUR process is still alive and AMCP responds."""
        if self._process and self._process.poll() is None:
            return self._client.ping()
        # Don't fall back to scanning all processes — that would detect
        # other CasparCG instances that we don't own.
        return False

    @property
    def pid(self) -> Optional[int]:
        return self._process.pid if self._process else None

    def _rename_console_after_delay(self, delay: float = 2.0) -> None:
        """Set console appearance after CasparCG finishes its own startup.

        Two independent mechanisms:
        1. Custom icon via WM_SETICON — CasparCG never changes the icon,
           so it persists permanently in the taskbar and Alt-Tab view.
        2. AttachConsole + SetConsoleTitleW — the same kernel32 path that
           CasparCG uses, so we compete on equal footing. Called every 1 s.

        Note: SetWindowTextW silently fails on console windows from another
        process (conhost owns the window, not the client). Only AttachConsole
        + SetConsoleTitleW is authoritative for the title.
        """
        time.sleep(delay)
        if not self._process:
            return
        try:
            self._run_console_appearance(self._process.pid, self.window_title)
        except Exception:
            pass

    def _run_console_appearance(self, root_pid: int, title: str) -> None:
        import ctypes
        import ctypes.wintypes

        user32   = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # --- Find child PIDs (conhost + casparcg) ---
        conhost_pid  = None
        caspar_pid   = root_pid
        for _ in range(10):
            try:
                for child in psutil.Process(root_pid).children(recursive=True):
                    name = child.name().lower()
                    if 'conhost' in name:
                        conhost_pid = child.pid
                    if 'caspar' in name:
                        caspar_pid  = child.pid
                if conhost_pid and caspar_pid != root_pid:
                    break
            except psutil.NoSuchProcess:
                break
            time.sleep(0.5)

        # --- Set custom icon on console window via conhost HWND ---
        # GetWindowThreadProcessId returns conhost's PID for console windows.
        # WM_SETICON is permanent — CasparCG never overrides the window icon.
        if conhost_pid:
            icon_path = self._find_icon()
            if icon_path:
                try:
                    LR_LOADFROMFILE = 0x10
                    IMAGE_ICON      = 1
                    WM_SETICON      = 0x0080
                    ICON_SMALL, ICON_BIG = 0, 1

                    hwnd = self._find_hwnd_for_pid(conhost_pid)
                    if hwnd:
                        for icon_size, icon_type in [(16, ICON_SMALL), (32, ICON_BIG)]:
                            hIcon = user32.LoadImageW(
                                None, icon_path, IMAGE_ICON,
                                icon_size, icon_size, LR_LOADFROMFILE,
                            )
                            if hIcon:
                                user32.SendMessageW(hwnd, WM_SETICON, icon_type, hIcon)
                except Exception:
                    pass

        # --- AttachConsole + SetConsoleTitleW loop ---
        # FreeConsole is a no-op for a windowed app with no console.
        kernel32.FreeConsole()
        attached = bool(kernel32.AttachConsole(caspar_pid))
        if not attached:
            attached = bool(kernel32.AttachConsole(root_pid))

        if attached:
            while self._process and self._process.poll() is None:
                kernel32.SetConsoleTitleW(title)
                time.sleep(1.0)
            kernel32.FreeConsole()

    @staticmethod
    def _find_hwnd_for_pid(pid: int):
        """Return the first visible HWND whose owning process is `pid`."""
        import ctypes
        import ctypes.wintypes
        user32 = ctypes.windll.user32
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        def _cb(hwnd, _):
            wpid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
            if wpid.value == pid and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
            return True

        user32.EnumWindows(_cb, 0)
        return found[0] if found else None

    @staticmethod
    def _find_icon() -> str | None:
        """Locate esc_icon.ico bundled with the app."""
        import sys
        candidates = []
        if getattr(sys, 'frozen', False):
            candidates.append(os.path.join(sys._MEIPASS, 'static', 'esc_icon.ico'))
        candidates.append(
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'static', 'esc_icon.ico')
        )
        for p in candidates:
            if os.path.isfile(p):
                return p
        return None

    @staticmethod
    def _kill_tree(pid: int) -> None:
        """Kill a process and all its children (cmd.exe + casparcg.exe)."""
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
            parent.terminate()
            psutil.wait_procs([parent] + children, timeout=5)
            # Force-kill anything still alive
            for proc in [parent] + children:
                try:
                    proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except psutil.NoSuchProcess:
            pass

    def _exe_dir(self) -> str:
        return os.path.dirname(os.path.abspath(self.exe_path))
