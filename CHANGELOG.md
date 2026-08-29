# MobileWorld Changelog

This file tracks all dated updates to MobileWorld. The README only keeps the
three most recent entries; everything else lives here.

## 2026-04-29: Head-to-Head Arena & Community Submissions🔥

- 🆚 **New Arena Comparison Page:** Compare any two models side-by-side at [tongyi-mai.github.io/MobileWorld/arena](https://tongyi-mai.github.io/MobileWorld/arena). Renders both trajectories step-by-step with screenshots and thinking traces, plus a confusion matrix to filter tasks by outcome (both pass / both fail / one wins / the other wins).
- 📤 **Submit Your Results:** Community-contributed trajectories are now accepted via the new [`site/bundle_trajs.py`](site/bundle_trajs.py) script. Bundle a `traj_logs/<run>` directory into a single `.json.gz` (with optional `.mp4` of screenshots) and open a PR. See [docs/submit.md](docs/submit.md).
- 📊 **Trajectories now browsable for:** Claude-Opus-4.7 (56.4% GUI / 59.1% User-Int), Claude-Opus-4.6 (44.5% / 34.1%), Kimi-K2.6 (55.6% / 56.8%), Kimi-K2.5 (49.6% / 51.2%), Seed-2.0-Pro (63.2% / 61.4%).

## 2026-04-22

Added **Claude-Opus-4.7** (56.4% GUI-Only) and **Kimi-K2.6** (55.6% GUI-Only) to the [leaderboard](https://tongyi-mai.github.io/MobileWorld/#leaderboard). Trajectory viewer now available for inspecting per-task agent traces.

## 2026-04-15: Important Fix — Mattermost Session Expiry

If you pulled the Docker image before this date, Mattermost task evaluations may produce **false negatives** due to expired authentication tokens in the emulator snapshot. Please **`git pull`** the latest codebase — the fix runs automatically during task initialization (no Docker image rebuild required).

## 2026-03-20: End-to-End Frontier Model Evaluation & Real Device Support🔥

We benchmarked five frontier models — **Seed-2.0-Pro**, **Gemini 3 Pro**, **KIMI K2.5**, **Claude Sonnet 4.5**, and **Qwen-3.5** — for end-to-end mobile-use, and demonstrated real-phone execution. See our [blog post](https://tongyi-mai.github.io/MAI-UI-blog/MobileWorld-Blog-Post) for the full write-up.

- 🏆 **New SOTA:** **Seed-2.0-Pro** leads at **63.2%** GUI-Only and **61.4%** User-Interaction, overtaking Seed-1.8 as the top end-to-end model.
- 📊 **Expanded Leaderboard:**
  - **KIMI K2.5** (49.6% GUI-Only, 51.2% User-Int)
  - **Qwen-3.5-397B-A17B** (42.7% GUI-Only, 54.4% User-Int)
  - **GUI-Owl-1.5-32B** (43.9% GUI-Only, 56.1% User-Int)
  - **UI-Venus-1.5-30B** (17.1% GUI-Only)
- 📱 **Real Device Support:** You can now run frontier models on physical Android phones. See [docs/real-devices.md](docs/real-devices.md).
- **New Agents:** `gui_owl_1_5` ([code](src/mobile_world/agents/implementations/gui_owl_1_5.py)), `ui_venus_agent` ([code](src/mobile_world/agents/implementations/ui_venus_agent.py))

## 2026-01-16: Expanded Model Evaluation Support🔥

We have introduced evaluation implementations for the latest frontier models, covering both end-to-end and agentic workflows.

- 🚀 **Leaderboard Upgrade with Multi-Dimensional Filtering:** We now support focused comparisons within **GUI-Only** and **User-Interaction** categories. This allows for a more balanced assessment of core navigation capabilities, especially for models not yet optimized for MCP-hybrid tool calls or complex user dialogues.
- 🏆 **New Performance Records:**
  - **GUI-Only Tasks:** **Seed-1.8** secured the Top-1 spot for end-to-end performance with a **52.1%** success rate, followed by **Gemini-3-Pro** (**51.3%**) and **Claude-4.5-Sonnet** (**47.8%**).
  - **Combined GUI & User Interaction:** **MAI-UI-235B-A22B** leads the leaderboard with a **45.4%** success rate, surpassing **Claude-4.5-Sonnet** (**43.2%**) and **Seed-1.8** (**40.8%**).
- **Supported Models:**
  - **End-to-End:** MAI-UI, Gemini-3-Pro, Claude-4.5-sonnet, Seed-1.8, and GELab-Zero.
  - **Agentic:** Gemini-3-Pro, Claude-4.5-sonnet, and GPT-5.
- **Implementation Details:**
  - [**MAI-UI**](https://tongyi-mai.github.io/MAI-UI/) ([code](src/mobile_world/agents/implementations/mai_ui_agent.py))
  - [**Gemini-3-Pro**](https://deepmind.google/models/gemini/pro/): End-to-end version adapted from our agentic framework utilizing Gemini's built-in grounding ([code](src/mobile_world/agents/implementations/general_e2e_agent.py)).
  - [**Seed-1.8**](https://seed.bytedance.com/en/seed1_8): Adapted from [OSWorld](https://github.com/xlang-ai/OSWorld/blob/main/mm_agents/seed_agent.py) for mobile action spaces, as GUI capability is not yet officially supported ([code](src/mobile_world/agents/implementations/seed_agent.py)).
  - [**GELab-Zero**](https://arxiv.org/abs/2512.15431) ([code](src/mobile_world/agents/implementations/gelab_agent.py)).
- **Note on GPT-5:** While supported for agentic tasks, **GPT-5** is currently excluded from end-to-end evaluation as its grounding mechanisms remain unclear for standardized testing.

## 2025-12-29

We released [MAI-UI](https://tongyi-mai.github.io/MAI-UI/), achieving SOTA performance with a 41.7% success rate in the end-to-end models category on the MobileWorld benchmark.

## 2025-12-23

- Initial release of MobileWorld benchmark. Check out our [paper](https://arxiv.org/abs/2512.19432) and [website](https://tongyi-mai.github.io/MobileWorld/)🔥.
- Docker image `ghcr.io/Tongyi-MAI/mobile_world:latest` available for public use.
