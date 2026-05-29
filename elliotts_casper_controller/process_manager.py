"""Launch, monitor, and stop the CasparCG server process."""
import os
import subprocess
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
            # Strip characters that would break the cmd title command
            safe_title = self.window_title.replace('"', "'").replace('&', 'and')
            # cmd_str runs inside the new console: set colour, set title, run exe
            cmd_str = f'color {_CONSOLE_COLOR} && title {safe_title} && "{exe_name}"'
            self._process = subprocess.Popen(
                ['cmd', '/k', cmd_str],
                cwd=self._exe_dir(),
            )
            deadline = time.time() + self.startup_delay + 5
            while time.time() < deadline:
                time.sleep(1)
                if self._client.ping():
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
