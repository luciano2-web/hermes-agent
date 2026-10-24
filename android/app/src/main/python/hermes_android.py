"""Android entry point: run the Hermes web dashboard inside the app process.

Chaquopy loads this module from the APK. ``start`` blocks for the lifetime of the
server, so Java calls it from a dedicated background thread and polls
``http://127.0.0.1:<port>/`` to know when the WebView can load the dashboard.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_PORT = 9119


def start(home: str, port: int = DEFAULT_PORT) -> int:
    """Point HERMES_HOME at the app-private directory, then serve the dashboard.

    Blocks until the server stops. Any failure raises, which the Java side
    reports on the launch screen.
    """
    home_path = Path(home)
    home_path.mkdir(parents=True, exist_ok=True)

    # Must happen before hermes_cli is imported: HERMES_HOME decides where all
    # state (config.yaml, .env, sessions, skills) lives, and HOME backs ~ paths.
    os.environ["HOME"] = str(home_path)
    os.environ["HERMES_HOME"] = str(home_path)

    # Build the real `hermes dashboard` argument tree rather than calling
    # start_server() directly, so all of the dashboard's own startup work
    # (web deps check, skills seed, web dist resolution, plugin discovery)
    # happens exactly as it does on a desktop.
    from hermes_cli._parser import build_top_level_parser
    from hermes_cli.main import cmd_dashboard, cmd_dashboard_register
    from hermes_cli.subcommands.dashboard import build_dashboard_parser

    parser, subparsers, _chat_parser = build_top_level_parser()
    subparsers.required = True
    build_dashboard_parser(
        subparsers,
        cmd_dashboard=cmd_dashboard,
        cmd_dashboard_register=cmd_dashboard_register,
    )

    argv = [
        "dashboard",
        "--host", "127.0.0.1",
        "--port", str(port),
        "--no-open",       # there is no browser to open: we are the WebView
        "--skip-build",    # no npm on the device; serve the bundled web dist
    ]
    args = parser.parse_args(argv)
    args.func(args)
    return 0
