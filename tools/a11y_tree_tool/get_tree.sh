#!/bin/bash
# 快捷脚本 - 直接运行获取 a11y tree
# 用法:
#   ./get_tree.sh                    # 文本格式输出
#   ./get_tree.sh -f json            # JSON 格式
#   ./get_tree.sh -f json -o out.json  # 保存到文件
#   ./get_tree.sh --mode grpc        # 强制 gRPC 模式
#   ./get_tree.sh --raw-xml          # 原始 XML

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 -m a11y_tool "$@"
