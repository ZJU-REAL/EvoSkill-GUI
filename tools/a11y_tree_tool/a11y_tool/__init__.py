"""a11y_tool - 独立的 Android Accessibility Tree 获取工具包。

支持两种模式：
- gRPC 模式 (方案B): 通过 android_env + A11yGrpcWrapper 获取完整的 protobuf 格式 a11y tree
- uiautomator 模式 (fallback): 通过 adb uiautomator dump 获取 XML 格式 UI 树

用法:
    from a11y_tool import A11yTreeClient

    client = A11yTreeClient()
    tree = client.get_tree()
    print(tree.to_text())

MobileWorld 集成:
    from a11y_tool.mobileworld import wrap_env
    env = wrap_env(env, container="mobile_world_env_0")
"""

from a11y_tool.client import A11yTreeClient

__version__ = "0.1.0"
__all__ = ["A11yTreeClient"]
