"""Route handlers for the eval server dashboard."""

import json
import os
from urllib.parse import quote

from fasthtml.common import *  # noqa: F403
from loguru import logger

import importlib
import mobile_world.agents.registry as _registry_module
from mobile_world.agents.registry import AGENT_CONFIGS
from mobile_world.core.eval_server import db
from mobile_world.core.eval_server.styles import EVAL_SERVER_CSS
from mobile_world.core.eval_server.worker import cancel_job, get_available_images, get_docker_containers


_total_task_cache: dict[str, int] = {}


def _get_total_tasks(enable_user_interaction: bool) -> int:
    """Get total task count from registry, filtered by tags. Cached."""
    cache_key = f"ui={enable_user_interaction}"
    if cache_key in _total_task_cache:
        return _total_task_cache[cache_key]
    try:
        from mobile_world.core.log_viewer.utils import get_registry, get_task_tags
        registry = get_registry("mobile_world")
        if not registry:
            return 0
        count = 0
        for task_name in registry.list_tasks():
            tags = get_task_tags(task_name, "mobile_world")
            if "agent-mcp" in tags:
                continue
            if not enable_user_interaction and "agent-user-interaction" in tags:
                continue
            count += 1
        _total_task_cache[cache_key] = count
        return count
    except Exception:
        return 0


def _get_job_progress(log_dir: str, enable_user_interaction: bool = False) -> tuple[int, int]:
    """Get (finished, total) task count for a running job."""
    if not log_dir or not os.path.isdir(log_dir):
        return 0, 0
    finished = 0
    for name in os.listdir(log_dir):
        task_path = os.path.join(log_dir, name)
        if not os.path.isdir(task_path):
            continue
        if name.startswith(".") or name.startswith("eval_report"):
            continue
        if os.path.isfile(os.path.join(task_path, "result.txt")):
            finished += 1
    total = _get_total_tasks(enable_user_interaction)
    return finished, total


_LOCAL_TIME_JS = """
function convertEpochs() {
    document.querySelectorAll('.local-time').forEach(function(el) {
        var epoch = parseInt(el.getAttribute('data-epoch'));
        if (!epoch || el.getAttribute('data-converted')) return;
        el.setAttribute('data-converted', '1');
        var d = new Date(epoch * 1000);
        el.textContent = d.getFullYear() + '-' +
            String(d.getMonth()+1).padStart(2,'0') + '-' +
            String(d.getDate()).padStart(2,'0') + ' ' +
            String(d.getHours()).padStart(2,'0') + ':' +
            String(d.getMinutes()).padStart(2,'0');
    });
}
convertEpochs();
document.body.addEventListener('htmx:afterSwap', function(e) {
    convertEpochs();
    if (e.detail.target && e.detail.target.id === 'modal-inner') {
        document.getElementById('submit-modal').style.display = 'flex';
    }
});

function applyFilters() {
    var el = document.getElementById('dashboard-content');
    if (!el) return;
    var base = el.getAttribute('hx-get').split('?')[0];
    var params = new URLSearchParams();
    var s = document.getElementById('filter-status');
    var a = document.getElementById('filter-agent');
    var l = document.getElementById('filter-label');
    var m = document.getElementById('filter-model');
    if (s && s.value) params.set('status', s.value);
    if (a && a.value) params.set('agent_type', a.value);
    if (l && l.value) params.set('label', l.value);
    if (m && m.value) params.set('model_name', m.value);
    var qs = params.toString();
    el.setAttribute('hx-get', qs ? base + '?' + qs : base);
    htmx.trigger(el, 'filterChanged');
}

var _filterTimer = null;
function debouncedApplyFilters() {
    clearTimeout(_filterTimer);
    _filterTimer = setTimeout(applyFilters, 300);
}
"""


def register_routes(rt, base_path: str = "/"):
    """Register all eval server routes.

    Routes are always registered at plain paths (e.g. /, /submit, /jobs/{id}).
    base_path is only used for generating URLs in HTML output, so that a reverse
    proxy mapping /8800/ -> / produces correct links.
    """
    # Normalize base_path for URL generation only
    if not base_path.endswith("/"):
        base_path = base_path + "/"
    if not base_path.startswith("/"):
        base_path = "/" + base_path

    def url(path: str) -> str:
        """Build a URL with the base path prefix (for hrefs/actions only)."""
        if path.startswith("/"):
            path = path[1:]
        return base_path + path

    def _get_agent_types() -> list[str]:
        return list(AGENT_CONFIGS.keys())

    def _agent_type_select(selected: str = ""):
        options = [Option(name, value=name, selected=(name == selected)) for name in _get_agent_types()]
        return Select(*options, name="agent_type", id="agent-type-select")

    def _image_select(selected: str = ""):
        images = get_available_images()
        if images:
            options = [
                Option(f"{img['tag']}  ({img['created'].split('.')[0] if img['created'] else ''})",
                       value=img["full"], selected=(img["full"] == selected if selected else i == 0))
                for i, img in enumerate(images)
            ]
        else:
            options = [Option("(no images found)", value="")]
        return Select(*options, name="env_image", id="image-select")

    def _status_badge(status: str):
        return Span(status, cls=f"badge badge-{status}")

    def _score_breakdown(j):
        """Render score breakdown for a job."""
        scores_raw = j.get("scores_json", "")
        if not scores_raw:
            if j.get("success_rate") is not None:
                return f"{j['success_rate']:.1%} ({j['successful_tasks']}/{j['total_tasks']})"
            return "-"

        try:
            s = json.loads(scores_raw)
        except (json.JSONDecodeError, TypeError):
            if j.get("success_rate") is not None:
                return f"{j['success_rate']:.1%}"
            return "-"

        parts = []
        if s.get("overall_sr") is not None:
            parts.append(Span(f"SR: {s['overall_sr']:.1f}%", cls="score-tag score-overall"))
        if s.get("standard_finished", 0) > 0:
            parts.append(Span(f"Std: {s['standard_sr']:.1f}%", cls="score-tag score-std"))
        if s.get("mcp_finished", 0) > 0:
            parts.append(Span(f"MCP: {s['mcp_sr']:.1f}%", cls="score-tag score-mcp"))
        if s.get("ui_finished", 0) > 0:
            parts.append(Span(f"UI: {s['ui_sr']:.1f}%", cls="score-tag score-ui"))
        return Div(*parts, cls="score-breakdown")

    def _score_detail_cards(j):
        """Render detailed score breakdown cards for job detail page."""
        scores_raw = j.get("scores_json", "")
        if not scores_raw:
            if j.get("success_rate") is not None:
                return Div(
                    Div(Div(f"{j['success_rate']:.1%}", cls="stat-value"),
                        Div("Success Rate", cls="stat-label"), cls="stat-card"),
                    Div(Div(str(j["successful_tasks"]), cls="stat-value"),
                        Div("Successful", cls="stat-label"), cls="stat-card"),
                    Div(Div(str(j["total_tasks"]), cls="stat-value"),
                        Div("Total Tasks", cls="stat-label"), cls="stat-card"),
                    cls="stats-row",
                )
            return ""

        try:
            s = json.loads(scores_raw)
        except (json.JSONDecodeError, TypeError):
            return ""

        cards = [
            Div(Div(f"{s.get('overall_sr', 0):.1f}%", cls="stat-value"),
                Div("Overall SR", cls="stat-label"), cls="stat-card"),
        ]
        if s.get("standard_finished", 0) > 0:
            cards.append(Div(
                Div(f"{s.get('standard_sr', 0):.1f}%", cls="stat-value"),
                Div(f"Standard ({s['standard_success']}/{s['standard_finished']})", cls="stat-label"),
                cls="stat-card"))
        if s.get("mcp_finished", 0) > 0:
            cards.append(Div(
                Div(f"{s.get('mcp_sr', 0):.1f}%", cls="stat-value"),
                Div(f"MCP ({s['mcp_success']}/{s['mcp_finished']})", cls="stat-label"),
                cls="stat-card"))
        if s.get("ui_finished", 0) > 0:
            cards.append(Div(
                Div(f"{s.get('ui_sr', 0):.1f}%", cls="stat-value"),
                Div(f"User Interaction ({s['ui_success']}/{s['ui_finished']})", cls="stat-label"),
                cls="stat-card"))
        if s.get("uiq", 0) > 0:
            cards.append(Div(
                Div(f"{s.get('uiq', 0):.3f}", cls="stat-value"),
                Div("UIQ", cls="stat-label"), cls="stat-card"))
        cards.append(Div(
            Div(f"{s.get('avg_steps', 0):.1f}", cls="stat-value"),
            Div("Avg Steps", cls="stat-label"), cls="stat-card"))

        return Div(*cards, cls="stats-row")

    def _submit_modal_content(defaults: dict | None = None):
        """Render the inner content of the submit job modal.

        Args:
            defaults: Optional dict of field values to pre-fill (for copy-job).
        """
        d = defaults or {}
        title = "Copy Job \u2014 Submit as New" if defaults else "Submit Evaluation Job"
        return Div(
            Div(
                H2(title),
                Button("x", cls="modal-close", onclick="document.getElementById('submit-modal').style.display='none'"),
                style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid var(--border-color);",
            ),
            Form(
                Div(
                    Div(
                        Label("Label (optional)"),
                        Input(name="label", placeholder="e.g. your name or experiment tag",
                              value=d.get("label", "")),
                        cls="form-group",
                    ),
                    Div(
                        Label(
                            "Agent Type ",
                            Button("↻", type="button", cls="refresh-btn",
                                   hx_get=url("agent-types"),
                                   hx_target="#agent-type-select",
                                   hx_swap="outerHTML"),
                        ),
                        _agent_type_select(selected=d.get("agent_type", "")),
                        cls="form-group",
                    ),
                    Div(
                        Label(
                            "Docker Image ",
                            Button("↻", type="button", cls="refresh-btn",
                                   hx_get=url("image-versions"),
                                   hx_target="#image-select",
                                   hx_swap="outerHTML"),
                        ),
                        _image_select(selected=d.get("env_image", "")),
                        cls="form-group",
                    ),
                    Div(
                        Label("Model Name"),
                        Input(name="model_name", required=True,
                              placeholder="e.g. gui-32b-0403-V8d1",
                              value=d.get("model_name", "")),
                        cls="form-group",
                    ),
                    Div(
                        Label("LLM Base URL"),
                        Input(name="llm_base_url", required=True,
                              placeholder="http://...",
                              value=d.get("llm_base_url", "")),
                        cls="form-group",
                    ),
                    Div(
                        Label("API Key (optional, falls back to .env)"),
                        Input(name="api_key", type="password",
                              placeholder="Leave empty to use .env"),
                        cls="form-group",
                    ),
                    Div(
                        Label("Number of Environments"),
                        Input(name="env_count", type="number",
                              value=str(d.get("env_count", 5)),
                              min="1", max="40", required=True),
                        cls="form-group",
                    ),
                    Div(
                        Label("Max Rounds"),
                        Input(name="max_round", type="number",
                              value=str(d.get("max_round", 50)),
                              min="1"),
                        cls="form-group",
                    ),
                    Div(
                        Label("Step Wait Time (seconds)"),
                        Input(name="step_wait_time", type="number",
                              value=str(d.get("step_wait_time", 3)),
                              min="0.1", step="0.1"),
                        cls="form-group",
                    ),
                    Div(
                        Label("Auto Retry (rounds)"),
                        Input(name="auto_retry", type="number",
                              value=str(d.get("auto_retry", 10)),
                              min="0", max="10"),
                        cls="form-group",
                    ),
                    Div(
                        Label(
                            Input(type="checkbox", name="enable_user_interaction",
                                  checked=d.get("enable_user_interaction", True)),
                            " Enable User Interaction Tasks",
                            cls="toggle-label",
                        ),
                        cls="form-group",
                    ),
                    cls="form-grid",
                ),
                Div(
                    Button("Submit Job", type="submit", cls="btn btn-primary",
                           onclick="this.disabled=true;this.textContent='Submitting...';this.form.submit()"),
                    style="margin-top: 20px; text-align: right;",
                ),
                method="post",
                action=url("submit"),
            ),
            id="modal-inner",
            cls="modal-content",
        )

    def _submit_modal():
        """Render the submit job modal."""
        return Div(
            _submit_modal_content(),
            id="submit-modal",
            cls="modal-overlay",
            style="display:none;",
        )

    def _page_shell(*content, title="Eval Server", active_page=""):
        dashboard_cls = "btn btn-sm btn-primary btn-disabled" if active_page == "dashboard" else "btn btn-sm btn-primary"
        dashboard_btn = (
            Span("Dashboard", cls=dashboard_cls) if active_page == "dashboard"
            else A("Dashboard", href=url(""), cls="btn btn-sm btn-primary")
        )
        return (
            Title(title),
            Style(EVAL_SERVER_CSS),
            Div(
                Div(
                    H1("MobileWorld Eval Server"),
                    Div(
                        Span(dashboard_btn, style="margin-right: 8px;"),
                        Button("Submit Job", cls="btn btn-sm btn-primary",
                               hx_get=url("submit-form"),
                               hx_target="#modal-inner",
                               hx_swap="outerHTML",
                               onclick="document.getElementById('submit-modal').style.display='flex'"),
                    ),
                    cls="app-header",
                ),
                *content,
                _submit_modal(),
                Script(_LOCAL_TIME_JS),
                cls="container",
            ),
        )

    def _build_dashboard_content(filters: dict | None = None):
        """Build the dashboard content (shared between full page and HTMX partial)."""
        # Stats use all jobs (unfiltered)
        all_jobs = db.list_jobs()
        # Table uses filtered jobs
        jobs = db.list_jobs(**(filters or {})) if filters else all_jobs
        running_jobs = [j for j in all_jobs if j["status"] == "running"]
        running_envs = sum(j["env_count"] for j in running_jobs)
        completed_jobs = [j for j in all_jobs if j["status"] == "completed"]
        failed_jobs = [j for j in all_jobs if j["status"] == "failed"]
        containers = get_docker_containers()

        # Build container popover content grouped by image
        container_rows = []
        for c in sorted(containers, key=lambda x: x["name"]):
            status_short = c["status"].split("(")[0].strip()  # e.g. "Up 2 hours"
            image_short = c["image"].split("/")[-1][:30]  # last segment, truncated
            container_rows.append(
                Tr(Td(c["name"], cls="popover-name"),
                   Td(status_short, cls="popover-status"),
                   Td(image_short, cls="popover-image"))
            )
        popover_content = Table(
            Thead(Tr(Th("Name"), Th("Status"), Th("Image"))),
            Tbody(*container_rows),
            cls="popover-table",
        ) if container_rows else P("No containers running", style="padding: 12px; color: var(--text-secondary);")

        docker_card = Div(
            Div(str(len(containers)), cls="stat-value"),
            Div("Docker Containers", cls="stat-label"),
            Div(popover_content, cls="popover-body"),
            cls="stat-card stat-card-popover",
        )

        stats = Div(
            Div(Div(str(len(all_jobs)), cls="stat-value"),
                Div("Total Jobs", cls="stat-label"), cls="stat-card"),
            Div(Div(str(len(running_jobs)), cls="stat-value"),
                Div("Running", cls="stat-label"), cls="stat-card"),
            Div(Div(str(len(completed_jobs)), cls="stat-value"),
                Div("Completed", cls="stat-label"), cls="stat-card"),
            Div(Div(str(len(failed_jobs)), cls="stat-value"),
                Div("Failed", cls="stat-label"), cls="stat-card"),
            Div(Div(str(running_envs), cls="stat-value"),
                Div("Running Envs", cls="stat-label"), cls="stat-card"),
            docker_card,
            cls="stats-row",
        )

        rows = []
        for j in jobs:
            action_items = []
            action_items.append(
                Button("Copy", cls="btn btn-sm",
                       hx_get=url(f"jobs/{j['id']}/copy-form"),
                       hx_target="#modal-inner",
                       hx_swap="outerHTML"),
            )
            if j["status"] in ("queued", "running"):
                action_items.append(
                    Form(
                        Button("Cancel", cls="btn btn-danger btn-sm", type="submit"),
                        method="post",
                        action=url(f"jobs/{j['id']}/cancel"),
                        onsubmit="return confirm('Cancel this job?')",
                        style="display:inline;",
                    ))
            actions = Div(*action_items, style="display:flex;gap:4px;align-items:center;")

            # Progress / Score
            if j["status"] == "running":
                finished, total = _get_job_progress(j.get("log_dir", ""), bool(j.get("enable_user_interaction")))
                if total > 0:
                    pct = int(finished / total * 100)
                    progress = Div(
                        Div(f"{finished}/{total}",
                            style="font-size: 12px; margin-bottom: 2px;"),
                        Div(Div(style=f"width: {pct}%; height: 100%; background: var(--accent-color); border-radius: 3px; transition: width 0.3s;"),
                            cls="progress-bar"),
                    )
                else:
                    progress = Span("starting...", style="color: var(--text-secondary); font-size: 12px;")
            elif j["status"] == "queued":
                progress = Span("queued", style="color: var(--text-secondary); font-size: 12px;")
            elif j.get("scores_json") or j.get("success_rate") is not None:
                progress = _score_breakdown(j)
            else:
                progress = Span("-", style="color: var(--text-secondary);")

            # Created time — render as local time via JS
            created_epoch = j.get("created_at", "")
            if created_epoch:
                try:
                    ts = float(created_epoch)
                    # Use a span with data attribute + JS to convert
                    created_td = Span(cls="local-time", data_epoch=str(int(ts)))
                except (ValueError, TypeError):
                    # Legacy string format fallback
                    created_td = Span(str(created_epoch)[:16])
            else:
                created_td = Span("-")

            rows.append(Tr(
                Td(A(j["id"][:8], href=url(f"jobs/{j['id']}"))),
                Td(j.get("label") or "-"),
                Td(_status_badge(j["status"])),
                Td(j["agent_type"]),
                Td(j["model_name"]),
                Td(str(j["env_count"])),
                Td(progress),
                Td(created_td),
                Td(actions),
            ))

        if not rows:
            table = Div(
                P("No jobs yet. Click 'Submit Job' to create one.",
                  style="color: var(--text-secondary); text-align: center; padding: 40px;"),
                cls="job-table",
            )
        else:
            table = Table(
                Thead(Tr(
                    Th("ID"), Th("Label"), Th("Status"), Th("Agent"),
                    Th("Model"), Th("Envs"), Th("Progress / Score"), Th("Created"), Th("Actions"),
                )),
                Tbody(*rows),
                cls="job-table",
            )

        return stats, table

    # ── Dashboard ────────────────────────────────────────────
    # Routes registered at plain paths; url() used only for HTML output

    def _filter_bar():
        """Render the filter bar above the jobs table."""
        statuses = ["queued", "running", "completed", "failed", "cancelled"]
        agent_types = _get_agent_types()
        return Div(
            Div(
                Label("Status", cls="filter-label"),
                Select(
                    Option("All", value=""),
                    *[Option(s, value=s) for s in statuses],
                    id="filter-status", onchange="applyFilters()",
                ),
                cls="filter-group",
            ),
            Div(
                Label("Agent", cls="filter-label"),
                Select(
                    Option("All", value=""),
                    *[Option(a, value=a) for a in agent_types],
                    id="filter-agent", onchange="applyFilters()",
                ),
                cls="filter-group",
            ),
            Div(
                Label("Label", cls="filter-label"),
                Input(id="filter-label", placeholder="Filter by label...",
                      oninput="debouncedApplyFilters()"),
                cls="filter-group",
            ),
            Div(
                Label("Model", cls="filter-label"),
                Input(id="filter-model", placeholder="Filter by model...",
                      oninput="debouncedApplyFilters()"),
                cls="filter-group",
            ),
            cls="filter-bar",
        )

    def _dashboard_content_div(filters: dict | None = None):
        """Build the polling div with filter-aware hx-get URL."""
        stats, table = _build_dashboard_content(filters)
        # Preserve active filters in the polling URL
        params = "&".join(f"{k}={quote(str(v))}" for k, v in (filters or {}).items() if v)
        poll_url = url("dashboard-content") + ("?" + params if params else "")
        return Div(
            stats, table,
            id="dashboard-content",
            hx_get=poll_url,
            hx_trigger="every 5s, filterChanged",
            hx_swap="outerHTML",
        )

    @rt("/")
    def dashboard():
        return _page_shell(
            _filter_bar(),
            _dashboard_content_div(),
            active_page="dashboard",
        )

    @rt("/dashboard-content")
    def dashboard_content(
        status: str = "", agent_type: str = "",
        label: str = "", model_name: str = "",
    ):
        """HTMX partial for dashboard polling."""
        filters = {k: v for k, v in dict(
            status=status, agent_type=agent_type,
            label=label, model_name=model_name,
        ).items() if v}
        return _dashboard_content_div(filters or None)

    # ── Agent Types (HTMX) ────────────────────────────────────

    @rt("/agent-types")
    def agent_types_select():
        """Reload registry and return fresh agent type select."""
        importlib.reload(_registry_module)
        from mobile_world.agents.registry import AGENT_CONFIGS as fresh_configs
        options = [Option(name, value=name) for name in fresh_configs.keys()]
        return Select(*options, name="agent_type", id="agent-type-select")

    # ── Image Versions (HTMX) ────────────────────────────────

    @rt("/image-versions")
    def image_versions_select():
        """Return fresh image version select."""
        return _image_select()

    # ── Submit Form (HTMX) ─────────────────────────────────

    @rt("/submit-form")
    def submit_form():
        """Return a blank submit form (resets modal after a copy action)."""
        return _submit_modal_content()

    @rt("/jobs/{job_id}/copy-form")
    def copy_form(job_id: str):
        """Return the submit form pre-filled with an existing job's parameters."""
        job = db.get_job(job_id)
        if not job:
            return _submit_modal_content()
        defaults = {
            "label": job.get("label", ""),
            "agent_type": job["agent_type"],
            "env_image": job.get("env_image", ""),
            "model_name": job["model_name"],
            "llm_base_url": job["llm_base_url"],
            "env_count": job["env_count"],
            "max_round": job["max_round"],
            "step_wait_time": job["step_wait_time"],
            "auto_retry": job.get("auto_retry", 0),
            "enable_user_interaction": bool(job.get("enable_user_interaction")),
        }
        return _submit_modal_content(defaults)

    # ── Submit Job ───────────────────────────────────────────

    @rt("/submit", methods=["POST"])
    def submit_job(
        agent_type: str,
        model_name: str,
        llm_base_url: str,
        env_count: int,
        api_key: str = "",
        label: str = "",
        max_round: int = 50,
        step_wait_time: float = 1.0,
        auto_retry: int = 0,
        enable_user_interaction: str = "",
        env_image: str = "",
    ):
        job = db.create_job(
            agent_type=agent_type,
            model_name=model_name,
            llm_base_url=llm_base_url,
            env_count=env_count,
            api_key=api_key,
            label=label,
            max_round=max_round,
            step_wait_time=step_wait_time,
            auto_retry=int(auto_retry),
            enable_user_interaction=enable_user_interaction == "on",
            env_image=env_image,
        )
        return RedirectResponse(url(f"jobs/{job['id']}"), status_code=303)

    # ── Job Detail ───────────────────────────────────────────

    @rt("/jobs/{job_id}")
    def job_detail(job_id: str):
        job = db.get_job(job_id)
        if not job:
            return _page_shell(Div("Job not found", cls="flash-error"))

        # Metadata
        meta_items = [
            ("Status", _status_badge(job["status"])),
            ("Agent Type", job["agent_type"]),
            ("Model", job["model_name"]),
            ("LLM URL", job["llm_base_url"]),
            ("Image", job.get("env_image") or "default"),
            ("Envs", str(job["env_count"])),
            ("Max Rounds", str(job["max_round"])),
            ("Step Wait", f"{job['step_wait_time']}s"),
            ("Auto Retry", str(job.get("auto_retry", 0))),
            ("User Interaction", "Yes" if job["enable_user_interaction"] else "No"),
            ("Created", job.get("created_at", "")),
            ("Started", job.get("started_at", "") or "-"),
            ("Finished", job.get("finished_at", "") or "-"),
            ("Label", job.get("label") or "-"),
        ]

        meta_dl = Div(
            *[Div(
                Span(dt_text, cls="meta-label"),
                Span(dd_val, cls="meta-value"),
                cls="meta-item",
            ) for dt_text, dd_val in meta_items],
            cls="detail-meta",
        )

        # Results section with breakdown
        results_section = ""
        if job.get("success_rate") is not None or job.get("scores_json"):
            results_section = Div(
                H3("Results"),
                _score_detail_cards(job),
                style="margin-bottom: 24px;",
            )

        # Action buttons row
        action_buttons = [
            Button("Copy to New Job", cls="action-btn action-btn-primary",
                   hx_get=url(f"jobs/{job_id}/copy-form"),
                   hx_target="#modal-inner",
                   hx_swap="outerHTML"),
        ]
        log_dir = job.get("log_dir", "")
        if log_dir and os.path.isdir(log_dir):
            abs_log_dir = os.path.abspath(log_dir)
            viewer_url = url(f"log-viewer/?log_root={quote(abs_log_dir)}")
            action_buttons.append(
                A("Open Log Viewer", href=viewer_url, target="_blank",
                  cls="action-btn action-btn-primary"))
        if job["status"] in ("queued", "running"):
            action_buttons.append(
                Form(
                    Button("Cancel Job", cls="action-btn action-btn-danger", type="submit"),
                    method="post",
                    action=url(f"jobs/{job_id}/cancel"),
                    onsubmit="return confirm('Cancel this job? This will kill the tmux session and remove containers.')",
                    style="display: inline;",
                ))
        if job["status"] in ("completed", "failed", "cancelled"):
            action_buttons.append(
                Form(
                    Button("Re-run", cls="action-btn action-btn-primary", type="submit"),
                    method="post",
                    action=url(f"jobs/{job_id}/rerun"),
                    onsubmit="return confirm('Re-run this job? It will retry tasks that have no results yet.')",
                    style="display: inline;",
                ))
        actions_row = Div(*action_buttons, cls="actions-row") if action_buttons else ""

        # Log output section (polls for updates)
        log_section = Div(
            H3("Output Log"),
            Div(
                _read_log_tail(job.get("log_file", ""), 200),
                cls="log-output",
                id="log-output",
                hx_get=url(f"jobs/{job_id}/log-tail"),
                hx_trigger="every 5s" if job["status"] == "running" else None,
                hx_swap="innerHTML",
            ),
            style="margin-bottom: 24px;",
        )

        header = Div(
            Div(
                H2(f"Job {job_id[:8]}"),
                meta_dl,
                cls="detail-header",
            ),
            actions_row,
            results_section,
            log_section,
        )

        return _page_shell(header, title=f"Job {job_id[:8]} - Eval Server")

    @rt("/jobs/{job_id}/log-tail")
    def job_log_tail(job_id: str):
        job = db.get_job(job_id)
        if not job:
            return Pre("Job not found")
        return _read_log_tail(job.get("log_file", ""), 200)

    # ── Cancel ───────────────────────────────────────────────

    @rt("/jobs/{job_id}/cancel", methods=["POST"])
    def cancel_action(job_id: str):
        cancel_job(job_id)
        return RedirectResponse(url(f"jobs/{job_id}"), status_code=303)

    @rt("/jobs/{job_id}/rerun", methods=["POST"])
    def rerun_action(job_id: str):
        job = db.get_job(job_id)
        if job and job["status"] in ("completed", "failed", "cancelled"):
            db.update_job(
                job_id,
                status="queued",
                started_at=None,
                finished_at=None,
                total_tasks=None,
                successful_tasks=None,
                success_rate=None,
                scores_json="",
                tmux_session="",
                log_file="",
            )
        return RedirectResponse(url(f"jobs/{job_id}"), status_code=303)


def _read_log_tail(log_file: str, lines: int = 200) -> str:
    """Read the last N lines from a log file."""
    if not log_file or not os.path.isfile(log_file):
        return "No log output yet."
    try:
        with open(log_file) as f:
            all_lines = f.readlines()
        return "".join(all_lines[-lines:])
    except Exception as e:
        return f"Error reading log: {e}"
