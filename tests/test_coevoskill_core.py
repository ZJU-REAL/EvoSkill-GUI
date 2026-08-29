from __future__ import annotations

import json

from mobile_world.skills.skill_manager import SkillManager, SkillMeta
from mobile_world.skills.skill_retriever import KeywordSkillRetriever
from mobile_world.skills.verifier import collect_traj_actions, sanitize_action


def test_skill_manager_persists_documents_and_evolution_status(tmp_path):
    manager = SkillManager(tmp_path / "skills")
    package = manager.create(
        SkillMeta(
            skill_id="skill_send_email",
            task_intent="send an email with an attachment",
            domain_app=["Mail", "Files"],
            keywords=["email", "attachment"],
        ),
        plan_md="1. Open the file\n2. Share it with Mail",
        backup_md="Use the attachment picker if Share is unavailable.",
        recover_md="Verify the attachment before sending.",
    )

    package.record_iteration(iteration=1, success=False, summary="attachment missing")
    loaded = manager.load(package.skill_id)

    assert loaded.read_doc("plan.md").startswith("1. Open")
    assert loaded.meta.evolution_status.usage_count == 1
    assert loaded.meta.evolution_status.fail_count == 1
    assert loaded.meta.evolution_status.success_rate == 0.0


def test_keyword_retriever_prefers_matching_skill(tmp_path):
    manager = SkillManager(tmp_path / "skills")
    manager.create(
        SkillMeta(
            skill_id="skill_email",
            task_intent="send a resume by email",
            domain_app=["Mail"],
            keywords=["resume", "email", "attachment"],
        )
    )
    manager.create(
        SkillMeta(
            skill_id="skill_calendar",
            task_intent="create a calendar event",
            domain_app=["Calendar"],
            keywords=["event", "meeting"],
        )
    )

    result = KeywordSkillRetriever(manager, threshold=0.0).best_match(
        "Use Mail to send the resume as an email attachment"
    )

    assert result is not None
    assert result.skill.skill_id == "skill_email"
    assert result.score > 0.5


def test_verifier_action_collection_isolates_predictions(tmp_path):
    trajectory = {
        "task-1": {
            "traj": [
                {
                    "step": 1,
                    "prediction": "private executor reasoning",
                    "action": {
                        "action_type": "click",
                        "x": 10,
                        "y": 20,
                        "internal_note": "must not reach verifier",
                    },
                }
            ]
        }
    }
    path = tmp_path / "traj.json"
    path.write_text(json.dumps(trajectory), encoding="utf-8")

    isolated = collect_traj_actions(path)
    assert "prediction" not in isolated[0]
    assert "internal_note" not in isolated[0]["action_json"]
    assert sanitize_action(trajectory["task-1"]["traj"][0]["action"]) == {
        "action_type": "click",
        "x": 10,
        "y": 20,
    }
