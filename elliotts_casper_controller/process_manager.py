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

    def _rename_console_after_delay(self, delay: float = 1.5) -> None:
        """Install a WinEventHook that fires every time the console title changes
        and immediately renames it back to ours.  Polling can't win against
        CasparCG which updates its title every frame (~25 fps)."""
        time.sleep(delay)
        if not self._process:
            return
        try:
            self._run_title_keeper(self._process.pid, self.window_title)
        except Exception:
            pass

    def _run_title_keeper(self, root_pid: int, title: str) -> None:
        import ctypes
        import ctypes.wintypes

        EVENT_OBJECT_NAMECHANGE = 0x800C
        WINEVENT_OUTOFCONTEXT   = 0x0000
        PM_REMOVE               = 0x0001

        user32 = ctypes.windll.user32

        # Build the pid set once (cmd.exe + casparcg.exe children).
        # Refresh every few seconds in the loop in case children change.
        def _get_pids() -> set:
            try:
                p = psutil.Process(root_pid)
                return {root_pid} | {c.pid for c in p.children(recursive=True)}
            except psutil.NoSuchProcess:
                return {root_pid}

        pids: set = _get_pids()
        pid_refresh_counter = [0]

        WinEventProc = ctypes.WINFUNCTYPE(
            None,
            ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD,
            ctypes.wintypes.HWND,   ctypes.wintypes.LONG,
            ctypes.wintypes.LONG,   ctypes.wintypes.DWORD,
            ctypes.wintypes.DWORD,
        )

        def _on_name_change(hook, event, hwnd, id_obj, id_child, thread, time_ms):
            wpid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
            if wpid.value in pids:
                buf = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(hwnd, buf, 256)
                if buf.value != title:
                    user32.SetWindowTextW(hwnd, title)

        proc = WinEventProc(_on_name_change)
        hook = user32.SetWinEventHook(
            EVENT_OBJECT_NAMECHANGE, EVENT_OBJECT_NAMECHANGE,
            None, proc, 0, 0, WINEVENT_OUTOFCONTEXT,
        )

        msg = ctypes.wintypes.MSG()
        while self._process and self._process.poll() is None:
            # Drain message queue so hook callbacks fire
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            # Refresh pid set every ~10 s (500 × 20 ms)
            pid_refresh_counter[0] += 1
            if pid_refresh_counter[0] >= 500:
                pid_refresh_counter[0] = 0
                pids.clear()
                pids.update(_get_pids())
            time.sleep(0.02)

        if hook:
            user32.UnhookWinEvent(hook)

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
