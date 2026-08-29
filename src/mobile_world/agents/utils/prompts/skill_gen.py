"""技能包初始化生成 prompt。

让 VLM 仅根据任务 instruction（以及可选的初始截图 + 初始 a11y 树）产出
一个完整的 JSON 描述，由 SkillGenerator 写入磁盘。

技能包生成被拆为三步：
1. ``SKILL_GEN_META_PLAN_USER_PROMPT_TEMPLATE`` —— 同时产出 meta 字段与
   ``plan_md``（执行时被 step-by-step 跟读的主文档）。
2. ``SKILL_GEN_BACKUP_USER_PROMPT_TEMPLATE`` —— 在已确定的 plan 之上为每一步
   提供备用 locator 策略。
3. ``SKILL_GEN_RECOVER_USER_PROMPT_TEMPLATE`` —— 在已确定的 plan + backup
   之上为可能出现的中断写恢复规则。

这样可以避免"一次 JSON 输出三段 markdown"导致的 plan 被人为切短、关键
pitfall 被分流到 backup/recover、JSON 转义错误等问题。
"""

from jinja2 import Template

SKILL_GEN_SYSTEM_PROMPT = """You are a senior GUI automation architect. You design \
"skill packages" that an Android automation agent will follow to complete a user task.

A skill package is a structured set of markdown documents and metadata. You must
produce CONCRETE, ACTIONABLE plans that reference real Android UI elements rather
than vague suggestions. Always anticipate common failure modes (popups, permission
dialogs, login walls, network errors, stale a11y nodes)."""


# ----------------------------------------------------------------------
# Sequential generation prompts
#
# 三步生成：每步独立一次 LLM 调用，下游能看到上游已确定的内容。
# 让模型在生成 plan 时不再为了"省字数留给 backup/recover"而切短主文档。
# ----------------------------------------------------------------------


SKILL_GEN_META_PLAN_USER_PROMPT_TEMPLATE = Template(
    """# Task
You will produce the META fields and `plan.md` of a skill package for the
following task. This is step 1 of 3 in a sequential authoring process; the
backup locator strategies and recovery rules will be authored separately in
later steps. Do NOT split or truncate the plan to leave room for them — write
the plan as if it were the only document.

## Task name
{{ task_name }}

## Task instruction (verbatim)
{{ instruction }}

{% if initial_a11y -%}
## Initial accessibility tree (truncated)
```
{{ initial_a11y }}
```
{% endif %}

# Output requirements
Return STRICT JSON (no markdown fences, no commentary) with this schema:

{
  "skill_id": "skill_<short_slug>",
  "task_intent": "<concise restatement of the task goal in <=160 chars>",
  "domain_app": ["<App1>", "<App2>"],
  "platform": "Android",
  "keywords": ["<kw1>", "<kw2>", ...],
  "arguments": ["<arg1>", "<arg2>", ...],
  "plan_md": "<markdown content for plan.md>"
}

Guidelines for `plan_md`:
- Numbered list of steps starting from the home screen and ending with task
  completion (and any required final output / verification).
- Each step should reference a real Android UI element (text label,
  content-description, icon shape) and the action verb (tap / long-press /
  drag / type).
- Be COMPLETE and self-contained. Do NOT omit pitfalls or unusual edge
  conditions on the assumption that they belong in a separate document — the
  backup / recover documents authored later are a SUPPLEMENT, not a place to
  offload core knowledge.
- If the task has a specific final output format (e.g. "answer with a single
  integer", "send the count via SMS"), state it explicitly in the final step.
- Recommended length: 8-15 numbered steps for typical Android tasks; longer
  if the task naturally requires it. Do NOT artificially shorten.

Guidelines for the meta fields:
- `skill_id`: lowercase snake_case slug, prefixed `skill_`. e.g.
  `skill_check_invoice_total`.
- `task_intent`: succinct goal restatement.
- `domain_app`: list of Android app names involved.
- `keywords`: lowercased canonical keywords for retrieval.
- `arguments`: placeholders for parametric values (use angle brackets).

Return ONLY the JSON object. Do NOT wrap it in code fences."""
)


SKILL_GEN_BACKUP_USER_PROMPT_TEMPLATE = Template(
    """# Task
You will produce `backup.md` for a skill package. This is step 2 of 3 in a
sequential authoring process. The plan has already been written (shown
below) and is FINAL. Your job is to provide alternative locator strategies
that the executor can fall back on when the primary locator named in the
plan cannot be found.

## Task instruction (verbatim)
{{ instruction }}

## Final plan.md (do NOT modify; just provide alternates)
```
{{ plan_md }}
```

# Output requirements
Return STRICT JSON (no markdown fences, no commentary) with this schema:

{
  "backup_md": "<markdown content for backup.md>"
}

Guidelines for `backup_md`:
- For each UI element referenced in plan.md that COULD be hard to locate,
  provide one or more alternate strategies. Skip elements whose locator is
  obvious and stable (e.g. system-level back button).
- Use bullets organized per element. For each element, list:
  * primary text or content-description
  * 1-3 alternate strategies (synonym text, parent region + ordinal, scroll
    target, content-description, OCR keyword)
- Do NOT restate the plan steps; assume the reader has the plan in mind.
- Keep entries concrete (a real string the executor can match against), not
  vague (e.g. "look around the screen").
- It is OK for `backup.md` to be short or even empty if every plan step
  uses a stable locator. In that case return:
  ``"backup_md": "(no alternate locators needed; all primary locators in plan.md are stable)"``

Return ONLY the JSON object. Do NOT wrap it in code fences."""
)


SKILL_GEN_RECOVER_USER_PROMPT_TEMPLATE = Template(
    """# Task
You will produce `recover.md` for a skill package. This is step 3 of 3 in a
sequential authoring process. The plan and backup have already been
written (shown below) and are FINAL. Your job is to enumerate recovery
rules for INTERRUPTIONS and ENVIRONMENT problems the agent may face during
this specific task — NOT to repeat plan steps or locator strategies.

## Task instruction (verbatim)
{{ instruction }}

## Final plan.md (do NOT modify)
```
{{ plan_md }}
```

## Final backup.md (do NOT modify)
```
{{ backup_md }}
```

# Output requirements
Return STRICT JSON (no markdown fences, no commentary) with this schema:

{
  "recover_md": "<markdown content for recover.md>"
}

Guidelines for `recover_md`:
- Cover only INTERRUPTIONS / ENVIRONMENT issues that are realistic for this
  task. Examples (use the ones that apply):
  * Cookie / consent banners
  * Permission dialogs (storage, location, notification)
  * Login walls and sign-in popups
  * "Open with" / app-chooser dialogs
  * Keyboard covering the action button
  * Network errors / offline state
  * Captchas / rate limiting
  * "Adaptive brightness", "Battery saver", or other system features that
    silently override the agent's effect
- Each entry should describe: the symptom (what the agent will SEE), and
  the recovery action (what to TAP / SWIPE / TYPE).
- Skip generic guidance that is not anchored to this task.
- It is OK for `recover.md` to be short. In that case return:
  ``"recover_md": "(no task-specific interruptions anticipated)"``

Return ONLY the JSON object. Do NOT wrap it in code fences."""
)
