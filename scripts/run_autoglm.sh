#!/usr/bin/env bash
# Evaluate Open-AutoGLM (AutoGLM-Phone-9B / 9B-Multilingual) on MobileWorld.
#
# Prerequisites:
#   1. sudo mw env run --count 5 --launch-interval 20
#   2. An OpenAI-compatible AutoGLM-Phone endpoint, e.g.:
#        - z.ai:    https://api.z.ai/api/paas/v4    (model: autoglm-phone-multilingual)
#        - Novita:  https://api.novita.ai/openai    (model: zai-org/autoglm-phone-9b-multilingual)
#        - Parasail https://api.parasail.io/v1      (model: parasail-auto-glm-9b-multilingual)
#        - vLLM:    http://localhost:8000/v1        (model: autoglm-phone-9b-multilingual)
#
# Usage:
#   LLM_BASE_URL=https://api.z.ai/api/paas/v4 \
#   API_KEY=<your-api-key> \
#   MODEL_NAME=autoglm-phone-multilingual \
#   bash scripts/run_autoglm.sh

set -euo pipefail

MODEL_NAME="${MODEL_NAME:-autoglm-phone-9b-multilingual}"
LLM_BASE_URL="${LLM_BASE_URL:?Please set LLM_BASE_URL to an AutoGLM OpenAI-compatible endpoint}"
API_KEY="${API_KEY:-}"
LOG_FILE_ROOT="${LOG_FILE_ROOT:-traj_logs/autoglm_logs}"
LANG_OPT="${AUTOGLM_LANG:-en}"
HISTORY_N_IMAGES="${HISTORY_N_IMAGES:-3}"
TASK_ARG="${TASK_ARG:-ALL}"
MAX_ROUND="${MAX_ROUND:-50}"
STEP_WAIT_TIME="${STEP_WAIT_TIME:-3}"

echo "[run_autoglm] model=${MODEL_NAME}"
echo "[run_autoglm] llm_base_url=${LLM_BASE_URL}"
echo "[run_autoglm] log_file_root=${LOG_FILE_ROOT}"
echo "[run_autoglm] lang=${LANG_OPT}  history_n_images=${HISTORY_N_IMAGES}"

API_KEY_ARG=()
if [ -n "${API_KEY}" ]; then
    API_KEY_ARG=(--api_key "${API_KEY}")
fi

# Forward the AutoGLM language preference and history depth via env vars so the
# agent picks them up without polluting the CLI surface area.
sudo HISTORY_N_IMAGES="${HISTORY_N_IMAGES}" mw eval \
    --agent_type autoglm \
    --task "${TASK_ARG}" \
    --max_round "${MAX_ROUND}" \
    --step_wait_time "${STEP_WAIT_TIME}" \
    --model_name "${MODEL_NAME}" \
    --llm_base_url "${LLM_BASE_URL}" \
    --log_file_root "${LOG_FILE_ROOT}" \
    --enable_mcp \
    --enable_user_interaction \
    "${API_KEY_ARG[@]}"
