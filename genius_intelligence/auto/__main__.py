"""
genius_intelligence.auto - CLI Entry Point
==========================================

사용법:
    python -m genius_intelligence.auto wrap claude
    python -m genius_intelligence.auto watch
    python -m genius_intelligence.auto init
"""

import sys


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Genius Intelligence Auto Module",
        prog="python -m genius_intelligence.auto",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # wrap command
    wrap_parser = subparsers.add_parser("wrap", help="Wrap a CLI with Genius Intelligence")
    wrap_parser.add_argument("cli", help="CLI tool name (claude, omp, etc.)")
    wrap_parser.add_argument("args", nargs="*", help="CLI arguments")
    wrap_parser.add_argument("--project", "-p", default=None, help="Project root")

    # watch command
    watch_parser = subparsers.add_parser("watch", help="Start background watcher")
    watch_parser.add_argument("--project", "-p", default=None, help="Project root")
    watch_parser.add_argument("--poll-interval", type=float, default=0.5, help="Poll interval (seconds)")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize Genius Intelligence")
    init_parser.add_argument("--project", "-p", default=None, help="Project root")
    init_parser.add_argument("--force", "-f", action="store_true", help="Force reinitialize")

    args = parser.parse_args()

    if args.command == "wrap":
        from .wrapper import wrap_cli
        sys.exit(wrap_cli([args.cli] + list(args.args), project_root=args.project))

    elif args.command == "watch":
        from .watcher import AutoWatcher
        from ..core.manager import GeniusIntelligence

        project = args.project or GeniusIntelligence.find_project_root() or "."
        watcher = AutoWatcher.for_current_project(project)
        watcher.poll_interval = args.poll_interval
        watcher.start()

        print(f"[genius] Watching {project}...")
        print("Press Ctrl+C to stop")

        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[genius] Stopping...")
            watcher.stop()

    elif args.command == "init":
        from ..core.manager import GeniusIntelligence
        from pathlib import Path

        project = args.project or GeniusIntelligence.find_project_root() or "."
        genius = GeniusIntelligence.for_current_project(project, auto_init=True)

        genius_dir = Path(project) / genius.config.genius_dir_name
        print(f"Initialized: {genius_dir}")
        print(f"  - DB: {genius_dir / 'memory.sqlite.db'}")
        print(f"  - Knowledge: {genius_dir / 'knowledge_graph'}")
        print("\nTo enable shell integration, run:")
        print(f'  eval "$(genius shell-init)"')

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
