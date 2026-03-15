#!/usr/bin/env python3
"""Bootout launchd agents and remove plists.

Usage:
    python3 bin/uninstall.py --all            # Remove all services
    python3 bin/uninstall.py git-sync         # Remove a specific service
"""

import argparse
import os
import subprocess
import sys

import yaml


def load_config():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, "config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)


def uninstall_service(service_name, global_config):
    """Bootout the agent and remove its plist."""
    label = f"{global_config['label_prefix']}.{service_name}"
    plist_path = os.path.expanduser(f"~/Library/LaunchAgents/{label}.plist")

    if not os.path.exists(plist_path):
        print(f"Plist not found (already removed?): {plist_path}")
        return True

    result = subprocess.run(
        ["launchctl", "bootout", f"gui/{os.getuid()}", plist_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Error 3 means "no such process" — already unloaded, which is fine
        if "3:" not in result.stderr:
            print(f"WARNING bootout {label}: {result.stderr.strip()}", file=sys.stderr)

    os.remove(plist_path)
    print(f"Removed: {plist_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Uninstall time-bound launchd agents")
    parser.add_argument("services", nargs="*", help="Service names to uninstall")
    parser.add_argument("--all", action="store_true", help="Uninstall all services")
    args = parser.parse_args()

    config = load_config()
    global_config = config["global"]

    if not args.all and not args.services:
        parser.print_help()
        sys.exit(1)

    if args.all:
        targets = list(config["services"].keys())
    else:
        targets = args.services

    for name in targets:
        uninstall_service(name, global_config)

    print(f"\nUninstalled {len(targets)} service(s)")


if __name__ == "__main__":
    main()
