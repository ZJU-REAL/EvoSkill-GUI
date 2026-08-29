"""通过 gRPC 获取完整 a11y forest (方案B)。

独立实现，不依赖 android_env 的 loader，只需要：
1. android_env 包（用其 proto 定义和 a11y_servicer）
2. ADB 连接到模拟器（本地或 docker exec）

工作原理：
- Python 端启动 gRPC server 接收 a11y forest
- 通过 ADB 在模拟器上安装并启动 AccessibilityForwarder app
- Forwarder app 主动向 Python gRPC server 推送 forest protobuf
"""

from __future__ import annotations
import logging
import os
import time
from concurrent import futures
from typing import Any, Optional

from a11y_tool.adb_client import AdbClient
from a11y_tool.models import BoundingBox, UIElement

logger = logging.getLogger(__name__)

_android_env_available = False
try:
    from android_env.components.a11y import a11y_forests
    from android_env.components.a11y import a11y_servicer
    from android_env.proto.a11y import a11y_pb2_grpc
    from android_env.proto.a11y import android_accessibility_forest_pb2
    import grpc
    import portpicker
    _android_env_available = True
except ImportError:
    pass

A11Y_FORWARDER_APK_URL = (
    "https://storage.googleapis.com/android_env-tasks/"
    "2024.05.13-accessibility_forwarder.apk"
)
A11Y_FORWARDER_PACKAGE = "com.google.androidenv.accessibilityforwarder"
A11Y_FORWARDER_SERVICE = (
    f"{A11Y_FORWARDER_PACKAGE}/"
    f"{A11Y_FORWARDER_PACKAGE}.AccessibilityForwarder"
)
A11Y_FORWARDER_RECEIVER = (
    f"{A11Y_FORWARDER_PACKAGE}/"
    f"{A11Y_FORWARDER_PACKAGE}.FlagsBroadcastReceiver"
)


def is_available() -> bool:
    return _android_env_available


class GrpcA11yProvider:
    """通过独立 gRPC server + ADB 获取 a11y tree。"""

    def __init__(
        self,
        adb: AdbClient,
        install_apk: bool = True,
        apk_path: Optional[str] = None,
    ):
        if not _android_env_available:
            raise ImportError(
                "android_env 未安装。请先安装: pip install android_env==1.2.3"
            )
        self._adb = adb
        self._install_apk = install_apk
        self._apk_path = apk_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "a11y_forwarder.apk",
        )
        self._server = None
        self._servicer = None
        self._port = None
        self._started = False

    def start(self):
        """启动 gRPC server 并配置模拟器上的 forwarder。"""
        if self._started:
            return

        if self._install_apk:
            self._install_forwarder()

        self._start_grpc_server()
        self._start_a11y_service()
        self._enable_tree_logs()
        self._configure_grpc_port()

        self._servicer.resume()
        self._started = True
        logger.info("gRPC a11y provider 已启动，端口 %d", self._port)
        time.sleep(2.0)

    def _install_forwarder(self):
        """安装 AccessibilityForwarder APK。"""
        installed = self._adb.shell(
            f"pm list packages {A11Y_FORWARDER_PACKAGE}"
        )
        if A11Y_FORWARDER_PACKAGE in installed:
            logger.info("Forwarder APK 已安装，跳过")
            return

        import os
        if not os.path.isfile(self._apk_path):
            raise FileNotFoundError(
                f"APK 文件不存在: {self._apk_path}\n"
                "请先下载: wget -O /tmp/a11y_forwarder.apk "
                f'"{A11Y_FORWARDER_APK_URL}"'
            )

        logger.info("安装 APK 到模拟器...")
        if self._adb.docker_container:
            import subprocess
            subprocess.run(
                ["docker", "cp", self._apk_path,
                 f"{self._adb.docker_container}:/tmp/a11y_forwarder.apk"],
                check=True,
            )
            self._adb.run(["install", "-r", "/tmp/a11y_forwarder.apk"],
                          timeout=60)
        else:
            self._adb.run(["install", "-r", self._apk_path], timeout=60)
        time.sleep(5.0)
        logger.info("APK 安装完成")

    def _start_grpc_server(self):
        """启动 Python 端 gRPC server。"""
        self._server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=10)
        )
        self._servicer = a11y_servicer.A11yServicer(latest_forest_only=True)
        a11y_pb2_grpc.add_A11yServiceServicer_to_server(
            self._servicer, self._server
        )
        self._port = portpicker.pick_unused_port()
        self._server.add_insecure_port(f"[::]:{self._port}")
        self._server.start()
        logger.info("gRPC server 启动在端口 %d", self._port)

    def _start_a11y_service(self):
        """在模拟器上启动 AccessibilityService。"""
        self._adb.shell(
            "settings put secure enabled_accessibility_services "
            f"'{A11Y_FORWARDER_SERVICE}'"
        )
        time.sleep(3.0)
        logger.info("AccessibilityService 已启动")

    def _enable_tree_logs(self):
        """启用 a11y tree 日志。"""
        self._adb.shell(
            "am broadcast -a "
            "accessibility_forwarder.intent.action.ENABLE_ACCESSIBILITY_TREE_LOGS "
            f"-n '{A11Y_FORWARDER_RECEIVER}'"
        )
        logger.info("a11y tree 日志已启用")

    def _configure_grpc_port(self):
        """告诉 forwarder app 连接到我们的 gRPC server。

        网络拓扑:
        - 本地模拟器: 模拟器 10.0.2.2:PORT → 宿主机:PORT (直连)
        - Docker 模拟器:
            1. adb reverse tcp:PORT tcp:PORT (模拟器 localhost:PORT → 容器 localhost:PORT)
            2. 容器内 Python 端口转发 (容器 localhost:PORT → 宿主机:PORT)
            3. forwarder 连 localhost:PORT
        """
        if self._adb.docker_container:
            self._setup_docker_port_forward()
            host_ip = "localhost"
        else:
            host_ip = "10.0.2.2"

        self._adb.shell(
            f"settings put global no_proxy '{host_ip}:{self._port}'"
        )
        self._adb.shell(
            "am broadcast -a "
            "accessibility_forwarder.intent.action.SET_GRPC "
            f"--ei port {self._port} "
            f"-n '{A11Y_FORWARDER_RECEIVER}'"
        )
        time.sleep(1.0)

        self._adb.shell(
            "am broadcast -a "
            "accessibility_forwarder.intent.action.ENABLE_GRPC "
            f"-n '{A11Y_FORWARDER_RECEIVER}'"
        )
        logger.info("已配置 forwarder 连接到 %s:%d", host_ip, self._port)

    def _setup_docker_port_forward(self):
        """在 Docker 容器内设置端口转发链路。

        adb reverse: 模拟器 localhost:PORT → 容器 localhost:PORT
        Python 转发: 容器 localhost:PORT → 宿主机(Docker网关):PORT
        """
        import subprocess

        # 1. adb reverse: 模拟器 localhost → 容器 localhost
        self._adb.shell(f"settings put global no_proxy 'localhost:{self._port}'")
        result = self._adb.run(
            ["reverse", f"tcp:{self._port}", f"tcp:{self._port}"]
        )
        logger.info("adb reverse 设置完成: %s", result.strip())

        # 2. 获取宿主机 IP（Docker 网关）
        host_gateway = "172.17.0.1"
        try:
            r = subprocess.run(
                ["docker", "exec", self._adb.docker_container,
                 "bash", "-c",
                 "route -n 2>/dev/null | grep '^0.0.0.0' | awk '{print $2}'"],
                capture_output=True, text=True, timeout=5,
            )
            gw = r.stdout.strip()
            if gw:
                host_gateway = gw
        except Exception:
            pass

        # 3. 在容器内启动 Python 端口转发
        fwd_script = (
            "import socket,threading,select\\n"
            f"def fwd(src,dst):\\n"
            "  try:\\n"
            "    while True:\\n"
            "      d=src.recv(4096)\\n"
            "      if not d:break\\n"
            "      dst.sendall(d)\\n"
            "  except:pass\\n"
            "  src.close();dst.close()\\n"
            f"s=socket.socket()\\n"
            f"s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)\\n"
            f"s.bind(('0.0.0.0',{self._port}))\\n"
            f"s.listen(5)\\n"
            f"while True:\\n"
            f"  c,_=s.accept()\\n"
            f"  r=socket.socket()\\n"
            f"  r.connect(('{host_gateway}',{self._port}))\\n"
            f"  threading.Thread(target=fwd,args=(c,r),daemon=True).start()\\n"
            f"  threading.Thread(target=fwd,args=(r,c),daemon=True).start()\\n"
        )
        subprocess.run(
            ["docker", "exec", "-d", self._adb.docker_container,
             "python3", "-c", f"exec(\"{fwd_script}\")"],
            timeout=5,
        )
        logger.info(
            "容器内 Python 转发: localhost:%d → %s:%d",
            self._port, host_gateway, self._port,
        )
        time.sleep(0.5)

    def get_forest(
        self, max_retries: int = 10, sleep_duration: float = 1.0
    ) -> Any:
        """获取原始的 AndroidAccessibilityForest protobuf。"""
        if not self._started:
            self.start()

        for attempt in range(max_retries):
            forests = self._servicer.gather_forests()
            if forests:
                return forests[-1]
            logger.debug(
                "等待 a11y forest... (%d/%d)", attempt + 1, max_retries
            )
            time.sleep(sleep_duration)

        raise RuntimeError(
            f"经过 {max_retries} 次重试仍无法获取 a11y forest"
        )

    def get_ui_elements(
        self, exclude_invisible: bool = True
    ) -> list[UIElement]:
        """获取解析后的 UIElement 列表。"""
        forest = self.get_forest()
        return forest_to_ui_elements(forest, exclude_invisible)

    def close(self):
        if self._server is not None:
            self._server.stop(None)
            self._server = None
        self._started = False


def forest_to_ui_elements(
    forest: Any, exclude_invisible: bool = True
) -> list[UIElement]:
    """将 AndroidAccessibilityForest protobuf 转换为 UIElement 列表。"""
    elements = []
    for window in forest.windows:
        for node in window.tree.nodes:
            if (not node.child_ids
                    or node.content_description
                    or node.is_scrollable):
                if exclude_invisible and not node.is_visible_to_user:
                    continue
                elements.append(_node_to_element(node))
    return elements


def _node_to_element(node: Any) -> UIElement:
    bbox = BoundingBox(
        x_min=node.bounds_in_screen.left,
        x_max=node.bounds_in_screen.right,
        y_min=node.bounds_in_screen.top,
        y_max=node.bounds_in_screen.bottom,
    )
    return UIElement(
        text=node.text or None,
        content_description=node.content_description or None,
        class_name=node.class_name or None,
        bbox=bbox,
        resource_id=getattr(node, "view_id_resource_name", None) or None,
        package_name=node.package_name or None,
        is_clickable=node.is_clickable,
        is_scrollable=node.is_scrollable,
        is_editable=node.is_editable,
        is_checkable=node.is_checkable,
        is_checked=node.is_checked,
        is_enabled=node.is_enabled,
        is_focused=getattr(node, "is_focused", False),
        is_focusable=node.is_focusable,
        is_long_clickable=node.is_long_clickable,
        is_selected=node.is_selected,
        is_visible=node.is_visible_to_user,
        hint_text=getattr(node, "hint_text", None) or None,
        tooltip=getattr(node, "tooltip_text", None) or None,
        depth=getattr(node, "depth", 0),
    )
