"""统一客户端 - 自动选择最佳方式获取 a11y tree。"""

from __future__ import annotations
import logging
import time
from typing import Literal, Optional

from a11y_tool.models import A11yTree
from a11y_tool.adb_client import AdbClient
from a11y_tool.xml_parser import parse_xml_dump
from a11y_tool import grpc_provider

logger = logging.getLogger(__name__)

Mode = Literal["grpc", "uiautomator", "auto"]


class A11yTreeClient:
    """获取 Android 设备 a11y tree 的统一客户端。

    用法:
        # 自动模式：优先 gRPC，fallback 到 uiautomator
        client = A11yTreeClient()
        tree = client.get_tree()
        print(tree.to_text())
        print(tree.to_json())

        # 强制 uiautomator 模式（无需 android_env）
        client = A11yTreeClient(mode="uiautomator")
        tree = client.get_tree()

        # 强制 gRPC 模式
        client = A11yTreeClient(mode="grpc", grpc_port=8554)
        tree = client.get_tree()
    """

    def __init__(
        self,
        mode: Mode = "auto",
        adb_path: Optional[str] = None,
        serial: Optional[str] = None,
        console_port: int = 5554,
        grpc_port: int = 8554,
        install_a11y_app: bool = True,
        docker_host: Optional[str] = None,
        docker_adb_port: Optional[int] = None,
        docker_container: Optional[str] = None,
    ):
        """初始化 A11yTreeClient。

        Args:
            mode: 获取模式 - "auto", "grpc", "uiautomator"
            adb_path: adb 可执行文件路径
            serial: 设备序列号（如 emulator-5554）
            console_port: 模拟器 console 端口（gRPC 模式用）
            grpc_port: gRPC 端口（gRPC 模式用）
            install_a11y_app: 是否自动安装 a11y forwarder app
            docker_host: Docker 容器宿主机地址（如 "localhost"）
            docker_adb_port: Docker 容器暴露的 ADB 端口（如 5556）
            docker_container: Docker 容器名称或 ID，通过 docker exec 执行 ADB
                推荐用于 MobileWorld 场景（如 "mobile_world_env_0"）
        """
        self.mode = mode
        self.adb_path = adb_path
        self.serial = serial
        self.console_port = console_port
        self.grpc_port = grpc_port
        self.install_a11y_app = install_a11y_app
        self.docker_host = docker_host
        self.docker_adb_port = docker_adb_port
        self.docker_container = docker_container

        self._adb: Optional[AdbClient] = None
        self._grpc: Optional[grpc_provider.GrpcA11yProvider] = None

    def _get_adb(self) -> AdbClient:
        if self._adb is None:
            self._adb = AdbClient(
                adb_path=self.adb_path,
                serial=self.serial,
                docker_container=self.docker_container,
            )
            if self.docker_host and self.docker_adb_port:
                logger.info(
                    "连接 Docker 容器内模拟器: %s:%d",
                    self.docker_host, self.docker_adb_port,
                )
                self._adb.connect_remote(self.docker_host, self.docker_adb_port)
        return self._adb

    def _get_grpc(self) -> grpc_provider.GrpcA11yProvider:
        if self._grpc is None:
            adb = self._get_adb()
            self._grpc = grpc_provider.GrpcA11yProvider(
                adb=adb,
                install_apk=self.install_a11y_app,
            )
        return self._grpc

    def _resolve_mode(self) -> str:
        if self.mode != "auto":
            return self.mode
        if grpc_provider.is_available():
            logger.info("检测到 android_env，使用 gRPC 模式")
            return "grpc"
        logger.info("android_env 不可用，使用 uiautomator 模式")
        return "uiautomator"

    def get_tree(self, exclude_invisible: bool = True) -> A11yTree:
        """获取当前屏幕的 a11y tree。"""
        mode = self._resolve_mode()
        ts = time.time()

        if mode == "grpc":
            return self._get_tree_grpc(exclude_invisible, ts)
        else:
            return self._get_tree_uiautomator(ts)

    def _get_tree_grpc(self, exclude_invisible: bool, ts: float) -> A11yTree:
        provider = self._get_grpc()
        forest = provider.get_forest()
        elements = grpc_provider.forest_to_ui_elements(forest, exclude_invisible)
        return A11yTree(
            elements=elements,
            raw_forest=forest,
            source="grpc",
            timestamp=ts,
        )

    def _get_tree_uiautomator(self, ts: float) -> A11yTree:
        adb = self._get_adb()
        xml_str = adb.uiautomator_dump()
        elements = parse_xml_dump(xml_str)
        return A11yTree(
            elements=elements,
            raw_xml=xml_str,
            source="uiautomator",
            timestamp=ts,
        )

    def get_raw_xml(self) -> str:
        """直接获取 uiautomator dump 的原始 XML。"""
        return self._get_adb().uiautomator_dump()

    def get_raw_forest(self):
        """直接获取原始的 protobuf forest（仅 gRPC 模式）。"""
        return self._get_grpc().get_forest()

    def step(
        self,
        action: str,
        wait: float = 1.0,
        save: Optional[str] = None,
        fmt: str = "json",
        exclude_invisible: bool = True,
    ) -> "A11yTree":
        """执行一个操作，等待界面稳定，获取 a11y tree。

        Args:
            action: 操作描述，支持以下格式：
                "tap 540 1200"          - 点击坐标
                "swipe 540 1800 540 600" - 滑动
                "text hello"            - 输入文字
                "key KEYCODE_BACK"      - 按键
                "home"                  - 回到桌面
                "back"                  - 返回
                "enter"                 - 回车
                "wait"                  - 仅等待，不执行操作
            wait: 操作后等待秒数（默认 1.0）
            save: 保存路径（如 "step1.json"），None 则不保存
            fmt: 保存格式 "json" 或 "text"
            exclude_invisible: 是否排除不可见元素

        Returns:
            A11yTree 对象
        """
        adb = self._get_adb()
        parts = action.strip().split()
        cmd = parts[0].lower()

        if cmd == "tap" and len(parts) >= 3:
            adb.tap(int(parts[1]), int(parts[2]))
        elif cmd == "swipe" and len(parts) >= 5:
            dur = int(parts[5]) if len(parts) > 5 else 300
            adb.swipe(int(parts[1]), int(parts[2]),
                      int(parts[3]), int(parts[4]), dur)
        elif cmd == "text" and len(parts) >= 2:
            adb.input_text(" ".join(parts[1:]))
        elif cmd == "key" and len(parts) >= 2:
            adb.press_key(parts[1])
        elif cmd == "home":
            adb.press_home()
        elif cmd == "back":
            adb.press_back()
        elif cmd == "enter":
            adb.press_key("KEYCODE_ENTER")
        elif cmd == "wait":
            pass
        else:
            adb.shell(f"input {action}")

        time.sleep(wait)
        tree = self.get_tree(exclude_invisible=exclude_invisible)

        if save:
            content = tree.to_json() if fmt == "json" else tree.to_text()
            with open(save, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info("已保存到 %s", save)

        return tree

    def close(self):
        if self._grpc is not None:
            self._grpc.close()
            self._grpc = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
