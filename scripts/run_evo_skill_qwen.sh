#!/usr/bin/env bash
# CoEvoSkill self-evolving GUI agent — Qwen3.6-plus runner.
#
# Prerequisites:
#   1. sudo mw env run --count 5 --launch-interval 20
#   2. uv pip install -e tools/a11y_tree_tool   (optional, for verifier a11y)
#
# Excludes the 12 google-proxy tasks per paper protocol.

set -euo pipefail

MODEL_NAME="${MODEL_NAME:-qwen3.6-plus}"
LLM_BASE_URL="${LLM_BASE_URL:?Please set LLM_BASE_URL to a Qwen OpenAI-compatible endpoint}"
API_KEY="${API_KEY:-}"
LOG_FILE_ROOT="${LOG_FILE_ROOT:-traj_logs/coevoskill_qwen}"
SKILLS_STORE="${SKILLS_STORE:-${LOG_FILE_ROOT}/_skills_store}"
MAX_EVO_ITER="${MAX_EVO_ITER:-3}"
RETRIEVAL_THRESHOLD="${RETRIEVAL_THRESHOLD:-0.6}"

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
  echo "[run_evo_skill_qwen] WARNING: could not enumerate tasks; falling back to ALL."
fi

echo "[run_evo_skill_qwen] model=${MODEL_NAME}"
echo "[run_evo_skill_qwen] llm_base_url=${LLM_BASE_URL}"
echo "[run_evo_skill_qwen] log_file_root=${LOG_FILE_ROOT}"
echo "[run_evo_skill_qwen] skills_store=${SKILLS_STORE}"
echo "[run_evo_skill_qwen] max_evo_iter=${MAX_EVO_ITER}"

API_KEY_ARG=()
if [ -n "${API_KEY}" ]; then
  API_KEY_ARG=(--api_key "${API_KEY}")
fi

sudo mw eval \
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
