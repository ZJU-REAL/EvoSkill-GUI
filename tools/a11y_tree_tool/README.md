# a11y-tree-tool

An optional Android accessibility-tree capture utility used by CoEvoSkill. It
supports `adb shell uiautomator dump` without Python dependencies and a richer
gRPC mode backed by `android_env`.

## Install

From the CoEvoSkill repository root:

```bash
uv pip install -e tools/a11y_tree_tool
```

For gRPC support:

```bash
uv pip install -e 'tools/a11y_tree_tool[grpc]'
wget -O tools/a11y_tree_tool/a11y_forwarder.apk \
  https://storage.googleapis.com/android_env-tasks/2024.05.13-accessibility_forwarder.apk
```

The APK is downloaded separately and ignored by Git. CoEvoSkill's default
`--enable-a11y` integration uses `uiautomator` mode and does not need the APK.

## CLI

```bash
# Print a text tree from a MobileWorld container.
python -m a11y_tool \
  --mode uiautomator \
  --docker-container mobile_world_env_0

# Save JSON after a tap action.
python -m a11y_tool \
  --mode uiautomator \
  --docker-container mobile_world_env_0 \
  --action "tap 540 1200" \
  --format json \
  --output tree.json
```

## Python API

```python
from a11y_tool import A11yTreeClient

with A11yTreeClient(
    mode="uiautomator",
    docker_container="mobile_world_env_0",
) as client:
    tree = client.get_tree()
    print(tree.to_text())
```

`a11y_tool.mobileworld.wrap_env` attaches capture hooks to an existing
MobileWorld environment and is used by the evaluation runner.
