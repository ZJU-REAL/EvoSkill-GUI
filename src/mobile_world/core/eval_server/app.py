"""Main FastHTML application for eval server."""

import warnings

import uvicorn
from fasthtml.common import fast_app
from loguru import logger

from mobile_world.core.eval_server import db
from mobile_world.core.eval_server.routes import register_routes
from mobile_world.core.eval_server.worker import start_worker

warnings.filterwarnings("ignore", message="'audioop' is deprecated", category=DeprecationWarning)

app, rt = fast_app()


async def main(
    port: int = 8800,
    max_containers: int = 40,
    data_dir: str = ".",
    base_path: str = "/",
    shell_prefix: str = "",
):
    """Launch the eval server."""
    # Initialize database
    db.init_db(db_dir=data_dir)
    logger.info("Database initialized at {}/eval_jobs.db", data_dir)

    # Normalize base_path
    if not base_path.startswith("/"):
        base_path = "/" + base_path
    if not base_path.endswith("/"):
        base_path = base_path + "/"

    # Register eval server routes
    register_routes(rt, base_path=base_path)

    # Register log viewer routes under /log-viewer/ prefix
    from mobile_world.core.log_viewer.routes import register_routes as register_log_viewer_routes
    log_viewer_base = base_path.rstrip("/") + "/log-viewer/"
    register_log_viewer_routes(rt, base_path=log_viewer_base, route_prefix="/log-viewer")

    # Start background worker
    start_worker(max_containers=max_containers, shell_prefix=shell_prefix)
    logger.info("Background worker started (max_containers={})", max_containers)

    logger.info("Eval server starting at http://0.0.0.0:{}{}", port, base_path)
    print(f"Link: http://localhost:{port}{base_path}")

    config = uvicorn.Config(app, host="0.0.0.0", port=port, ws="none")
    server = uvicorn.Server(config)
    await server.serve()
