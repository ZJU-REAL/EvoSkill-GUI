"""ADB 通信工具，封装与 Android 模拟器的底层交互。

支持三种连接方式：
1. 本地 ADB 直连（模拟器在宿主机上）
2. ADB connect 远程连接（Docker 端口映射）
3. docker exec 方式（直接在容器内执行 ADB 命令）
"""

import subprocess
import shutil
import time
from typing import Optional


def find_adb() -> str:
    """自动查找 adb 路径。"""
    candidates = [
        shutil.which("adb"),
        "$HOME/Android/Sdk/platform-tools/adb",
    ]
    import os
    for c in candidates:
        if c:
            expanded = os.path.expandvars(os.path.expanduser(c))
            if os.path.isfile(expanded):
                return expanded
    raise FileNotFoundError(
        "找不到 adb，请通过 adb_path 参数指定或将其加入 PATH"
    )


class AdbClient:
    """轻量级 ADB 客户端。"""

    def __init__(
        self,
        adb_path: Optional[str] = None,
        serial: Optional[str] = None,
        docker_container: Optional[str] = None,
    ):
        self.serial = serial
        self.docker_container = docker_container
        if docker_container:
            self.adb_path = "adb"
        else:
            self.adb_path = adb_path or find_adb()

    def _build_cmd(self, args: list[str]) -> list[str]:
        if self.docker_container:
            cmd = ["docker", "exec", self.docker_container, "adb"]
        else:
            cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        cmd += args
        return cmd

    def run(self, args: list[str], timeout: float = 30.0) -> str:
        cmd = self._build_cmd(args)
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"adb 命令失败: {' '.join(cmd)}\nstderr: {result.stderr}"
            )
        return result.stdout

    def shell(self, command: str, timeout: float = 30.0) -> str:
        return self.run(["shell", command], timeout=timeout)

    def uiautomator_dump(self, timeout: float = 30.0) -> str:
        """执行 uiautomator dump 并返回 XML 内容。"""
        self.shell("uiautomator dump /sdcard/window_dump.xml", timeout=timeout)
        time.sleep(0.3)
        return self.shell("cat /sdcard/window_dump.xml", timeout=timeout)

    def list_devices(self) -> list[str]:
        output = self.run(["devices"])
        devices = []
        for line in output.strip().split("\n")[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices

    def connect_remote(self, host: str, port: int) -> str:
        """连接远程 ADB（如 Docker 容器内的模拟器）。

        MobileWorld 等 Docker 环境会通过 socat 将容器内 ADB 端口
        转发到宿主机，典型配置: 宿主机:5556 -> 容器内:5555
        """
        output = self.run(["connect", f"{host}:{port}"])
        if "connected" not in output.lower() and "already" not in output.lower():
            raise RuntimeError(f"ADB 连接失败: {output.strip()}")
        self.serial = f"{host}:{port}"
        return output.strip()

    def tap(self, x: int, y: int):
        self.shell(f"input tap {x} {y}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300):
        self.shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")

    def input_text(self, text: str):
        escaped = text.replace(" ", "%s").replace("'", "\\'")
        self.shell(f"input text '{escaped}'")

    def press_key(self, keycode: str):
        """按键，如 KEYCODE_HOME, KEYCODE_BACK, KEYCODE_ENTER。"""
        self.shell(f"input keyevent {keycode}")

    def press_home(self):
        self.press_key("KEYCODE_HOME")

    def press_back(self):
        self.press_key("KEYCODE_BACK")
