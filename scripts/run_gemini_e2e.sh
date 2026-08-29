sudo mw env run --count 5 --launch-interval 20

sudo HISTORY_N_IMAGES=3 mw eval \
    --agent_type general_e2e \
    --task ALL \
    --max_round 50 \
    --step_wait_time 3 \
    --model_name gemini-3-pro-preview \
    --llm_base_url [gemini_openai_compatible_base_url] \
    --enable_mcp \
    --enable_user_interaction
