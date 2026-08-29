#!/usr/bin/env bash
# CoEvoSkill self-evolving GUI agent — Claude Sonnet runner.
#
# Prerequisites:
#   1. Build / start MobileWorld containers:
#        sudo mw env run --count 5 --launch-interval 20
#   2. Make sure your model name contains "claude" (the agent uses partial match
#      to enable Claude-specific image resize logic).
#   3. Optional but recommended: install the a11y_tree_tool so the verifier can
#      consume per-step a11y data:
#        uv pip install -e tools/a11y_tree_tool
#
# This script excludes the 12 google-proxy tasks the paper does not evaluate.

set -euo pipefail

# ----------------------------------------------------------------------------
# Configuration — fill in the deployment-specific values before running.
# ----------------------------------------------------------------------------
MODEL_NAME="${MODEL_NAME:-claude-sonnet-4-6-20260217}"
LLM_BASE_URL="${LLM_BASE_URL:?Please set LLM_BASE_URL to a Claude OpenAI-compatible endpoint}"
API_KEY="${API_KEY:-}"
LOG_FILE_ROOT="${LOG_FILE_ROOT:-traj_logs/coevoskill_claude}"
SKILLS_STORE="${SKILLS_STORE:-${LOG_FILE_ROOT}/_skills_store}"
MAX_EVO_ITER="${MAX_EVO_ITER:-3}"
RETRIEVAL_THRESHOLD="${RETRIEVAL_THRESHOLD:-0.6}"

# 12 tasks that require external Google proxies — excluded per paper protocol.
EXCLUDED_TASKS=(
    ThanksgivingPrepTask
    SuggestPaperTask
    GraduationMassEmailTask
    CheckConferenceLocationTask
    ChromeSearchBeijingWeatherTask
    CheckGithubInfoTask
    MastodonPostPollTask
    MastodonShareLocationTask
    TextArrivalTimeTask
    GoogleMapsAlibabaPhoneContactTask
    GoogleMapsAlibabaSouthNeighborTask
    MattermostReadingGroupTask
)

# Build comma-separated TASK list = ALL_TASKS - EXCLUDED_TASKS using `mw eval`'s
# discovery + a small Python helper. Falls back to "ALL" if mw is unavailable.
TASKS_ARG="ALL"
if command -v mw >/dev/null 2>&1; then
  ALL_TASKS=$(python3 - <<'PY'
import json, subprocess, sys
try:
    out = subprocess.check_output(["mw", "info", "--list-tasks"], text=True, timeout=30)
    items = [line.strip() for line in out.splitlines() if line.strip()]
    print(",".join(items))
except Exception:
    print("")
PY
)
  if [ -n "${ALL_TASKS}" ]; then
    EXCLUDED_CSV=$(IFS=,; echo "${EXCLUDED_TASKS[*]}")
    TASKS_ARG=$(python3 - "$ALL_TASKS" "$EXCLUDED_CSV" <<'PY'
import sys
all_tasks = [t for t in sys.argv[1].split(",") if t]
excluded = set(t for t in sys.argv[2].split(",") if t)
kept = [t for t in all_tasks if t not in excluded]
print(",".join(kept))
PY
)
  fi
fi

if [ "${TASKS_ARG}" = "ALL" ]; then
  echo "[run_evo_skill_claude] WARNING: could not enumerate tasks; falling back to ALL."
  echo "[run_evo_skill_claude] You may manually drop the 12 excluded tasks from the eval report."
fi

echo "[run_evo_skill_claude] model=${MODEL_NAME}"
echo "[run_evo_skill_claude] llm_base_url=${LLM_BASE_URL}"
echo "[run_evo_skill_claude] log_file_root=${LOG_FILE_ROOT}"
echo "[run_evo_skill_claude] skills_store=${SKILLS_STORE}"
echo "[run_evo_skill_claude] max_evo_iter=${MAX_EVO_ITER}"

API_KEY_ARG=()
if [ -n "${API_KEY}" ]; then
  API_KEY_ARG=(--api_key "${API_KEY}")
fi

sudo HISTORY_N_IMAGES=3 mw eval \
    --agent_type evo_skill \
    --task "${TASKS_ARG}" \
    --max_round 50 \
    --step_wait_time 3 \
    --model_name "${MODEL_NAME}" \
    --llm_base_url "${LLM_BASE_URL}" \
    --log_file_root "${LOG_FILE_ROOT}" \
    --enable_mcp \
    --enable_evolution \
    --skills_store "${SKILLS_STORE}" \
    --max_evolution_iterations "${MAX_EVO_ITER}" \
    --retrieval_threshold "${RETRIEVAL_THRESHOLD}" \
    --enable_a11y \
    "${API_KEY_ARG[@]}"
