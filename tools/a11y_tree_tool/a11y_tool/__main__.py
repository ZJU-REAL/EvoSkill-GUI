#!/usr/bin/env python3
"""命令行入口 - 快速获取 Android 设备的 a11y tree。

用法:
    python -m a11y_tool                                          # 获取当前 a11y tree
    python -m a11y_tool -f json -o tree.json                     # 保存为 JSON
    python -m a11y_tool --action "tap 540 1200" -o step1.json    # 点击后获取
    python -m a11y_tool --action "back" --action "wait" -o s.json  # 连续操作
    python -m a11y_tool --docker-container mobile_world_env_0 --action "tap 918 1970" --wait 2 -f json -o step.json
"""

import argparse
import sys
import logging


def main():
    parser = argparse.ArgumentParser(
        description="获取 Android 设备的 Accessibility Tree",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
操作示例 (--action):
  --action "tap 540 1200"              点击坐标
  --action "swipe 540 1800 540 600"    滑动
  --action "text hello"                输入文字
  --action "back"                      返回
  --action "home"                      回到桌面
  --action "enter"                     回车
  --action "key KEYCODE_MENU"          按键

可以多次使用 --action 来连续执行多步操作，最后一步的 a11y tree 会被输出。
""",
    )
    parser.add_argument(
        "--mode", choices=["auto", "grpc", "uiautomator"], default="auto",
        help="获取模式: auto(自动选择), grpc(android_env), uiautomator(adb dump)",
    )
    parser.add_argument(
        "--format", "-f", choices=["text", "json", "xml"], default="text",
        help="输出格式 (default: text)",
    )
    parser.add_argument("--output", "-o", help="输出到文件而非 stdout")
    parser.add_argument(
        "--action", "-a", action="append", default=[],
        help="执行操作后再获取 tree (可多次使用)",
    )
    parser.add_argument(
        "--wait", "-w", type=float, default=1.0,
        help="每步操作后等待秒数 (default: 1.0)",
    )
    parser.add_argument("--adb-path", help="adb 可执行文件路径")
    parser.add_argument("--serial", "-s", help="设备序列号 (多设备时使用)")
    parser.add_argument("--console-port", type=int, default=5554, help="模拟器 console 端口")
    parser.add_argument("--grpc-port", type=int, default=8554, help="gRPC 端口")
    parser.add_argument("--raw-xml", action="store_true", help="输出原始 uiautomator XML")
    parser.add_argument("--no-install", action="store_true", help="不自动安装 a11y forwarder app")
    parser.add_argument("--docker-host", help="Docker 宿主机地址 (如 localhost)")
    parser.add_argument("--docker-adb-port", type=int, help="Docker 暴露的 ADB 端口")
    parser.add_argument("--docker-container", help="Docker 容器名/ID (如 mobile_world_env_0)")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from a11y_tool.client import A11yTreeClient

    client = A11yTreeClient(
        mode=args.mode,
        adb_path=args.adb_path,
        serial=args.serial,
        console_port=args.console_port,
        grpc_port=args.grpc_port,
        install_a11y_app=not args.no_install,
        docker_host=args.docker_host,
        docker_adb_port=args.docker_adb_port,
        docker_container=args.docker_container,
    )

    try:
        if args.action:
            for i, action in enumerate(args.action):
                is_last = (i == len(args.action) - 1)
                tree = client.step(action, wait=args.wait)
                if not is_last:
                    print(f"[{i}] {action} → {len(tree.elements)} elements", file=sys.stderr)
            output = _format_tree(tree, args)
        elif args.raw_xml:
            output = client.get_raw_xml()
        else:
            tree = client.get_tree()
            output = _format_tree(tree, args)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"已保存到 {args.output}", file=sys.stderr)
        else:
            print(output)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        client.close()


def _format_tree(tree, args) -> str:
    if args.format == "json":
        return tree.to_json()
    elif args.format == "xml":
        if tree.raw_xml:
            return tree.raw_xml
        print("gRPC 模式不产生 XML，切换到 JSON", file=sys.stderr)
        return tree.to_json()
    return tree.to_text()


if __name__ == "__main__":
    main()
