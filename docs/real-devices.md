# Testing on Real Devices

Beyond the containerized emulator environment, MobileWorld supports running frontier models on **real physical Android phones**. This lets you evaluate models like Gemini, Claude, Qwen, and others as true end-to-end mobile agents.

## Prerequisites

- A physical Android phone connected via USB
- ADB (Android Debug Bridge) installed on your local machine
- An API key for the model you want to test

## Step 1: Install ADB

Download the official [ADB platform-tools](https://developer.android.com/tools/releases/platform-tools) and extract it.

**macOS/Linux:**
```bash
# Assuming extracted to ~/Downloads/platform-tools
export PATH=${PATH}:~/Downloads/platform-tools
```

**Windows:** Refer to [this guide](https://blog.csdn.net/x2584179909/article/details/108319973) for configuration steps.

## Step 2: Connect Your Phone & Enable USB Debugging

1. **Enable Developer Mode:** Go to *Settings > About Phone > Build Number* and tap rapidly ~10 times until you see "Developer mode has been enabled."
2. **Enable USB Debugging:** Go to *Settings > Developer Options > USB Debugging* and enable it. Some devices may require a restart.
3. **Verify the connection:**

```bash
adb devices

# Expected output:
# List of devices attached
# <your_device_id>   device
```

## Step 3: Install ADB Keyboard (Optional)

ADB Keyboard is needed for text input. Download the [ADBKeyboard.apk](https://github.com/senzhk/ADBKeyBoard/blob/master/ADBKeyboard.apk) and install it on your device:

```bash
adb install ADBKeyboard.apk
adb shell ime enable com.android.adbkeyboard/.AdbIME
```

> **Note:** This step is optional — MobileWorld will install it automatically if not present.

## Step 4: Clone MobileWorld

```bash
git clone https://github.com/Tongyi-MAI/MobileWorld.git
cd MobileWorld
uv sync
```

## Step 5: Start the MobileWorld Server

```bash
uv run mobile-world server
```

This starts the backend API server that bridges the model and the device.

## Step 6: Run a Task on Your Real Device

```bash
uv run mw test "set an alarm at 8:00 am" \
    --agent-type general_e2e \
    --model_name anthropic/claude-sonnet-4-5 \
    --llm_base_url https://openrouter.ai/api/v1 \
    --aw-host http://127.0.0.1:6800 \
    --api_key YOUR_API_KEY
```

Replace `--model_name`, `--llm_base_url`, and `--api_key` with the model and credentials you want to use. Any OpenAI-compatible endpoint works. The `--agent-type general_e2e` prompt works across most frontier models. For Seed-2.0-Pro, use `--agent-type seed_agent` for better performance.

## Supported End-to-End Models

| Model             | Agent Type    | Coordinate System | Notes                                         |
|-------------------|---------------|-------------------|-----------------------------------------------|
| Claude Opus 4.7   | `general_e2e` | Absolute pixels   | 1 image in history (see leaderboard notes)    |
| Kimi K2.6         | `general_e2e` | Relative (0–1)    |                                               |
| Gemini 3 Pro      | `general_e2e` | Relative (0–1000) | Normalized coordinates                        |
| Claude Sonnet 4.5 | `general_e2e` | Absolute pixels   | Requires image resize to 1280×720             |
| Qwen-3.5          | `general_e2e` | Relative (0–1000) |                                               |
| KIMI K2.5         | `general_e2e` | Relative (0–1)    |                                               |
| Seed-2.0-Pro      | `seed_agent`  | Relative (0–1000) | Best with specialized `seed_agent` agent type |

> **Tip:** You can view the live device screen at any time with `uv run mw device`.
