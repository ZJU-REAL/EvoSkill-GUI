"""Background worker for processing eval job queue."""

import os
import json
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from loguru import logger

from mobile_world.core.eval_server import db

MAX_CONTAINERS = 40  # Default, overridden by CLI arg
POLL_INTERVAL = 5    # seconds
LOG_BASE_DIR = "eval_server_logs"
SHELL_PREFIX = ""    # Optional prefix for shell commands (e.g. "sg docker -c" for docker group)


def _tmux_session_exists(session_name: str) -> bool:
    result = subprocess.run(
        ["tmux", "has-session", "-t", session_name],
        capture_output=True,
    )
    return result.returncode == 0


def _run_shell(cmd: str) -> subprocess.CompletedProcess:
    """Run a shell command, optionally wrapping with SHELL_PREFIX."""
    if SHELL_PREFIX:
        return subprocess.run(
            [*SHELL_PREFIX.split(), cmd],
            capture_output=True, text=True, shell=False,
        )
    return subprocess.run(cmd, capture_output=True, text=True, shell=True)


def get_docker_containers() -> list[dict]:
    """Get running Docker containers with name, status, and image."""
    result = _run_shell("docker ps --format '{{.Names}}\\t{{.Status}}\\t{{.Image}}'")
    if result.returncode != 0:
        logger.warning("Failed to list docker containers: {}", result.stderr)
        return []
    containers = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        containers.append({
            "name": parts[0] if len(parts) > 0 else "",
            "status": parts[1] if len(parts) > 1 else "",
            "image": parts[2] if len(parts) > 2 else "",
        })
    return containers


def count_docker_containers() -> int:
    """Count running Docker containers."""
    return len(get_docker_containers())


def get_available_images(repo: str = "ghcr.io/tongyi-mai/mobile_world") -> list[dict]:
    """List locally available Docker images for the given repo, newest first."""
    result = _run_shell(
        f"docker images --filter reference='{repo}' "
        f"--format '{{{{.Tag}}}}\\t{{{{.CreatedAt}}}}\\t{{{{.ID}}}}'"
    )
    if result.returncode != 0:
        logger.warning("Failed to list docker images: {}", result.stderr)
        return []
    images = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        images.append({
            "tag": parts[0] if len(parts) > 0 else "",
            "created": parts[1] if len(parts) > 1 else "",
            "id": parts[2] if len(parts) > 2 else "",
            "full": f"{repo}:{parts[0]}" if len(parts) > 0 else repo,
        })
    # Already sorted by creation date (newest first) from docker images
    return images


def _start_job(job: dict) -> None:
    """Launch containers and start eval in a tmux session."""
    job_id = job["id"]
    prefix = job["container_prefix"]
    env_count = job["env_count"]
    log_dir = os.path.join(LOG_BASE_DIR, f"job_{job_id}")
    os.makedirs(log_dir, exist_ok=True)

    tmux_session = f"eval_{job_id}"
    log_file = os.path.join(log_dir, "output.log")
    traj_log_dir = os.path.join(log_dir, "traj_logs")

    # Build the eval command
    eval_cmd_parts = [
        "uv", "run", "mw", "eval",
        "--agent-type", job["agent_type"],
        "--tasks", "ALL",
        "--max-round", str(job["max_round"]),
        "--model-name", job["model_name"],
        "--llm-base-url", job["llm_base_url"],
        "--step-wait-time", str(job["step_wait_time"]),
        "--log-file-root", traj_log_dir,
        "--env-prefix", prefix,
    ]
    if job.get("api_key"):
        eval_cmd_parts.extend(["--api-key", job["api_key"]])
    if job.get("auto_retry", 0) > 0:
        eval_cmd_parts.extend(["--auto-retry", str(job["auto_retry"])])
    if job.get("enable_user_interaction"):
        eval_cmd_parts.append("--enable-user-interaction")
    env_image = job.get("env_image", "")
    if env_image:
        eval_cmd_parts.extend(["--env-image", env_image])

    eval_cmd = " ".join(eval_cmd_parts)

    # Combined command: launch containers, then run eval
    env_cmd = f"uv run mw env run --count {env_count} --mount-src --name-prefix {prefix}"
    if env_image:
        env_cmd += f" --image {env_image}"
    full_cmd = f"{env_cmd} && {eval_cmd}"

    # Wrap with shell prefix if configured (e.g. sg docker -c)
    if SHELL_PREFIX:
        shell_cmd = f"{SHELL_PREFIX} '{full_cmd}' 2>&1 | tee {log_file}"
    else:
        shell_cmd = f"bash -c '{full_cmd}' 2>&1 | tee {log_file}"

    # Launch in tmux session
    tmux_cmd = [
        "tmux", "new-session", "-d", "-s", tmux_session,
        shell_cmd,
    ]

    logger.info("Starting job {}: tmux session={}, prefix={}", job_id, tmux_session, prefix)
    subprocess.run(tmux_cmd, check=True)

    db.update_job(
        job_id,
        status="running",
        started_at=datetime.now().isoformat(),
        tmux_session=tmux_session,
        log_file=log_file,
        log_dir=traj_log_dir,
    )


def _cleanup_containers(prefix: str, image: str = "") -> None:
    """Remove containers with the given prefix."""
    logger.info("Cleaning up containers with prefix: {}", prefix)
    cmd = f"uv run mw env rm --all --name-prefix {prefix}"
    if image:
        cmd += f" --image {image}"
    result = _run_shell(cmd)
    if result.returncode != 0:
        logger.warning("Container cleanup warning: {}", result.stderr)


def _parse_eval_results(log_dir: str) -> dict:
    """Parse eval results from the traj log directory.

    Uses calculate_task_stats for breakdown scores, and eval_report JSON for summary.
    """
    results = {
        "total_tasks": None, "successful_tasks": None, "success_rate": None,
        "scores_json": None,
    }
    if not log_dir or not os.path.isdir(log_dir):
        return results

    # Try to compute breakdown scores using log_viewer utils
    try:
        from mobile_world.core.log_viewer.utils import calculate_task_stats
        stats = calculate_task_stats(log_dir, suite_family="mobile_world")
        if stats.get("finished", 0) > 0:
            results["total_tasks"] = stats["finished"]
            results["successful_tasks"] = stats["success"]
            results["success_rate"] = stats["success_rate"] / 100.0 if stats["success_rate"] else 0.0
            # Store detailed breakdown as JSON
            results["scores_json"] = json.dumps({
                "overall_sr": stats.get("success_rate", 0),
                "standard_sr": stats.get("standard_success_rate", 0),
                "standard_finished": stats.get("standard_finished", 0),
                "standard_success": stats.get("standard_success", 0),
                "mcp_sr": stats.get("mcp_success_rate", 0),
                "mcp_finished": stats.get("mcp_finished", 0),
                "mcp_success": stats.get("mcp_success", 0),
                "ui_sr": stats.get("user_interaction_success_rate", 0),
                "ui_finished": stats.get("user_interaction_finished", 0),
                "ui_success": stats.get("user_interaction_success", 0),
                "uiq": stats.get("uiq", 0),
                "avg_steps": stats.get("avg_steps", 0),
                "avg_queries": stats.get("avg_queries", 0),
                "avg_mcp_calls": stats.get("avg_mcp_calls", 0),
            })
            return results
    except Exception as e:
        logger.warning("Failed to compute breakdown stats: {}", e)

    # Fallback: parse eval_report JSON
    report_files = sorted(Path(log_dir).glob("eval_report_*.json"), reverse=True)
    if not report_files:
        return results

    try:
        with open(report_files[0]) as f:
            report = json.load(f)
        summary = report.get("summary", {})
        results["total_tasks"] = summary.get("total_tasks_with_results")
        results["successful_tasks"] = summary.get("successful_tasks")
        results["success_rate"] = summary.get("overall_success_rate")
    except Exception as e:
        logger.warning("Failed to parse eval report {}: {}", report_files[0], e)

    return results


def _check_running_jobs() -> None:
    """Check if any running jobs have finished."""
    running_jobs = db.list_jobs(status="running")
    for job in running_jobs:
        tmux_session = job.get("tmux_session", "")
        if not tmux_session:
            continue

        if not _tmux_session_exists(tmux_session):
            # Re-read job to check if it was cancelled in the meantime
            fresh_job = db.get_job(job["id"])
            if fresh_job and fresh_job["status"] == "cancelled":
                logger.info("Job {} was cancelled, skipping result collection", job["id"])
                continue

            # Session ended — job finished
            logger.info("Job {} tmux session ended, collecting results", job["id"])

            results = _parse_eval_results(job.get("log_dir", ""))
            _cleanup_containers(job["container_prefix"], job.get("env_image", ""))

            # Determine final status
            status = "completed" if results.get("total_tasks") else "failed"

            db.update_job(
                job["id"],
                status=status,
                finished_at=datetime.now().isoformat(),
                **results,
            )
            logger.info("Job {} finished with status={}", job["id"], status)


def _process_queue(max_containers: int) -> None:
    """Try to start queued jobs if capacity allows."""
    queued_jobs = db.list_jobs(status="queued")
    if not queued_jobs:
        return

    current_containers = count_docker_containers()

    for job in queued_jobs:
        if current_containers + job["env_count"] <= max_containers:
            try:
                _start_job(job)
                current_containers += job["env_count"]
            except Exception as e:
                logger.error("Failed to start job {}: {}", job["id"], e)
                db.update_job(job["id"], status="failed",
                              finished_at=datetime.now().isoformat())


def cancel_job(job_id: str) -> bool:
    """Cancel a running or queued job."""
    job = db.get_job(job_id)
    if not job:
        return False

    if job["status"] == "queued":
        db.update_job(job_id, status="cancelled",
                      finished_at=datetime.now().isoformat())
        return True

    if job["status"] == "running":
        # Update status FIRST to prevent worker from overwriting with 'failed'
        db.update_job(job_id, status="cancelled",
                      finished_at=datetime.now().isoformat())

        # Kill tmux session
        tmux_session = job.get("tmux_session", "")
        if tmux_session:
            subprocess.run(
                ["tmux", "kill-session", "-t", tmux_session],
                capture_output=True,
            )
        # Cleanup containers
        _cleanup_containers(job["container_prefix"], job.get("env_image", ""))
        return True

    return False


def worker_loop(max_containers: int = MAX_CONTAINERS) -> None:
    """Main worker loop — runs in a daemon thread."""
    logger.info("Eval worker started (max_containers={}, shell_prefix='{}')", max_containers, SHELL_PREFIX)
    while True:
        try:
            _check_running_jobs()
            _process_queue(max_containers)
        except Exception as e:
            logger.error("Worker loop error: {}", e)
        time.sleep(POLL_INTERVAL)


def start_worker(max_containers: int = MAX_CONTAINERS, shell_prefix: str = "") -> threading.Thread:
    """Start the background worker thread."""
    global SHELL_PREFIX
    SHELL_PREFIX = shell_prefix

    thread = threading.Thread(
        target=worker_loop,
        args=(max_containers,),
        daemon=True,
        name="eval-worker",
    )
    thread.start()
    return thread
