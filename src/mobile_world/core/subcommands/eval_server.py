"""Eval server subcommand for MobileWorld CLI."""

import argparse


def configure_parser(subparsers: argparse._SubParsersAction) -> None:
    """Configure the eval-server subcommand parser."""
    parser = subparsers.add_parser(
        "eval-server",
        help="Launch the evaluation server dashboard",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8800,
        help="Server port (default: 8800)",
    )
    parser.add_argument(
        "--max-containers",
        "--max_containers",
        dest="max_containers",
        type=int,
        default=40,
        help="Maximum number of Docker containers allowed (default: 40)",
    )
    parser.add_argument(
        "--data-dir",
        "--data_dir",
        dest="data_dir",
        default=".",
        help="Directory for database and logs (default: current directory)",
    )
    parser.add_argument(
        "--base-path",
        "--base_path",
        dest="base_path",
        default="/",
        help="Base URL path prefix (e.g. /8800/ for reverse proxy). Default: /",
    )
    parser.add_argument(
        "--shell-prefix",
        "--shell_prefix",
        dest="shell_prefix",
        default="",
        help="Shell command prefix for docker commands (e.g. 'sg docker -c' for docker group)",
    )


async def execute(args: argparse.Namespace) -> None:
    """Execute the eval-server command."""
    from mobile_world.core.eval_server.app import main

    await main(
        port=args.port,
        max_containers=args.max_containers,
        data_dir=args.data_dir,
        base_path=args.base_path,
        shell_prefix=args.shell_prefix,
    )
