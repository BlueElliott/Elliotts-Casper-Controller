"""Launch, monitor, and stop the CasparCG server process."""
import subprocess
import time
from typing import Optional

import psutil

from elliotts_casper_controller.amcp_client import AMCPClient


class CasparProcessManager:
    def __init__(self, exe_path: str, amcp_port: int = 5250, startup_delay: int = 8):
        self.exe_path = exe_path
        self.amcp_port = amcp_port
        self.startup_delay = startup_delay
        self._process: Optional[subprocess.Popen] = None
        self._client = AMCPClient(port=amcp_port)

    def start(self, config: dict | None = None) -> bool:
        if self.is_running():
            return True
        if config:
            from elliotts_casper_controller.config_manager import regenerate_caspar_config
            regenerate_caspar_config(config)
        try:
            self._process = subprocess.Popen(
                [self.exe_path],
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
        self._client.send("BYE")
        time.sleep(1)
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None

    def is_running(self) -> bool:
        if self._process and self._process.poll() is None:
            return self._client.ping()
        for proc in psutil.process_iter(["name"]):
            if proc.info["name"] and "casparcg" in proc.info["name"].lower():
                return self._client.ping()
        return False

    def _exe_dir(self) -> str:
        import os
        return os.path.dirname(os.path.abspath(self.exe_path))
