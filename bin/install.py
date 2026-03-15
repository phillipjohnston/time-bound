#!/usr/bin/env python3
"""Generate launchd plists and bootstrap agents.

Usage:
    python3 bin/install.py --all              # Install all enabled services
    python3 bin/install.py git-sync           # Install a specific service
    python3 bin/install.py --list             # List available services
"""

import argparse
import os
import string
import subprocess
import sys

import yaml


def load_config():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, "config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)


def schedule_to_xml(schedule):
    """Convert a list of schedule dicts to plist XML for StartCalendarInterval."""
    if len(schedule) == 1:
        lines = ["    <dict>"]
        for key, value in schedule[0].items():
            lines.append(f"        <key>{key}</key>")
            lines.append(f"        <integer>{value}</integer>")
        lines.append("    </dict>")
        return "\n".join(lines)

    lines = ["    <array>"]
    for entry in schedule:
        lines.append("        <dict>")
        for key, value in entry.items():
            lines.append(f"            <key>{key}</key>")
            lines.append(f"            <integer>{value}</integer>")
        lines.append("        </dict>")
    lines.append("    </array>")
    return "\n".join(lines)


def generate_plist(service_name, service_def, global_config):
    """Render a plist from the template."""
    project_root = global_config["project_root"]
    template_path = os.path.join(project_root, "templates", "launchagent.plist.template")

    with open(template_path) as f:
        template = string.Template(f.read())

    label = f"{global_config['label_prefix']}.{service_name}"
    schedule_xml = schedule_to_xml(service_def["schedule"])

    # Ensure log directories exist
    log_dir = os.path.join(project_root, global_config["log_dir"], service_name)
    os.makedirs(log_dir, exist_ok=True)

    plist_content = template.substitute(
        label=label,
        python_path=global_config["python_path"],
        project_root=project_root,
        service_name=service_name,
        path=global_config["path"],
        home=os.path.expanduser("~"),
        log_dir=global_config["log_dir"],
        schedule_xml=schedule_xml,
    )

    return label, plist_content


def install_service(service_name, service_def, global_config):
    """Generate plist and bootstrap the agent."""
    label, plist_content = generate_plist(service_name, service_def, global_config)

    plist_dir = os.path.expanduser("~/Library/LaunchAgents")
    os.makedirs(plist_dir, exist_ok=True)
    plist_path = os.path.join(plist_dir, f"{label}.plist")

    # Bootout first if already loaded (ignore errors if not loaded)
    subprocess.run(
        ["launchctl", "bootout", f"gui/{os.getuid()}", plist_path],
        capture_output=True,
    )

    with open(plist_path, "w") as f:
        f.write(plist_content)
    print(f"Written: {plist_path}")

    result = subprocess.run(
        ["launchctl", "bootstrap", f"gui/{os.getuid()}", plist_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR bootstrapping {label}: {result.stderr.strip()}", file=sys.stderr)
        return False

    print(f"Bootstrapped: {label}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Install time-bound launchd agents")
    parser.add_argument("services", nargs="*", help="Service names to install")
    parser.add_argument("--all", action="store_true", help="Install all enabled services")
    parser.add_argument("--list", action="store_true", help="List available services")
    args = parser.parse_args()

    config = load_config()
    global_config = config["global"]

    if args.list:
        for name, svc in config["services"].items():
            status = "enabled" if svc.get("enabled", True) else "disabled"
            print(f"  {name} ({status})")
        return

    if not args.all and not args.services:
        parser.print_help()
        sys.exit(1)

    if args.all:
        targets = [
            (name, svc)
            for name, svc in config["services"].items()
            if svc.get("enabled", True)
        ]
    else:
        targets = []
        for name in args.services:
            if name not in config["services"]:
                print(f"Unknown service: {name}", file=sys.stderr)
                sys.exit(1)
            targets.append((name, config["services"][name]))

    succeeded = 0
    for name, svc in targets:
        if install_service(name, svc, global_config):
            succeeded += 1

    print(f"\nInstalled {succeeded}/{len(targets)} services")


if __name__ == "__main__":
    main()
