"""Main FastHTML application for log viewer."""

from urllib.parse import quote

from fasthtml.common import fast_app, serve
from loguru import logger

from mobile_world.core.log_viewer.routes import register_routes
from mobile_world.core.log_viewer.utils import get_log_root_state

# Create the FastHTML app - will be configured in main()
app, rt = fast_app()


def main(log_root: str = "", server_port: int = 8760, base_path: str = "/"):
    """Launch the log viewer application."""
    # Normalize base_path to ensure it starts and ends with /
    if not base_path.startswith("/"):
        base_path = "/" + base_path
    if not base_path.endswith("/"):
        base_path = base_path + "/"

    # Register all routes with the base path
    register_routes(rt, base_path=base_path)

    log_root_state = get_log_root_state()
    if log_root:
        log_root_state["log_root"] = log_root
        logger.info(f"Setting default log root to: {log_root}")
        logger.info(f"Base path: {base_path}")
        # Open browser with log_root parameter
        url = f"http://localhost:{server_port}{base_path}?log_root={quote(log_root)}"
        logger.info(f"Open log viewer at: {url}")

        serve(port=server_port, reload=False)
    else:
        logger.info("No log root provided, starting with empty state")
        logger.info(f"Base path: {base_path}")
        serve(port=server_port, reload=False)


if __name__ == "__main__":
    import sys

    log_root = sys.argv[1] if len(sys.argv) > 1 else ""
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8760
    base_path = sys.argv[3] if len(sys.argv) > 3 else "/"
    main(log_root=log_root, server_port=port, base_path=base_path)
