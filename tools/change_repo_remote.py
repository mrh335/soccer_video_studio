"""Switch this local project to a different Git repository.

Usage examples:
  python tools/change_repo_remote.py --new-url git@github.com:you/new-repo.git
  python tools/change_repo_remote.py --new-url https://github.com/you/new-repo.git --remote upstream

If the remote does not exist, it will be created.
If the remote exists, its URL will be updated.
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def run(cmd: list[str]) -> str:
    completed = subprocess.run(cmd, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip() or "Command failed")
    return completed.stdout.strip()


def remote_exists(name: str) -> bool:
    completed = subprocess.run(["git", "remote", "get-url", name], capture_output=True, text=True)
    return completed.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Change or create a git remote URL for this repo.")
    parser.add_argument("--new-url", required=True, help="New repository URL")
    parser.add_argument("--remote", default="origin", help="Remote name (default: origin)")
    parser.add_argument("--show", action="store_true", help="Show remote list after update")
    args = parser.parse_args()

    try:
        run(["git", "rev-parse", "--is-inside-work-tree"])
    except RuntimeError:
        print("Error: current directory is not a git repository.", file=sys.stderr)
        return 2

    try:
        if remote_exists(args.remote):
            run(["git", "remote", "set-url", args.remote, args.new_url])
            print(f"Updated remote '{args.remote}' -> {args.new_url}")
        else:
            run(["git", "remote", "add", args.remote, args.new_url])
            print(f"Created remote '{args.remote}' -> {args.new_url}")

        if args.show:
            print("\nCurrent remotes:")
            print(run(["git", "remote", "-v"]))
    except RuntimeError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
