#!/usr/bin/env python3
"""Dispatcher: launchd calls this with a service name.

Usage: python3 bin/runner.py <service-name>
"""

import importlib
import os
import sys

# Add project root to sys.path before any local imports
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import yaml

from services.base import setup_service_logger


def load_config():
    """Load config.yaml from the project root."""
    config_path = os.path.join(_PROJECT_ROOT, "config.yaml")

    with open(config_path) as f:
        return yaml.safe_load(f)


# Map service names to Python module paths
SERVICE_MODULES = {
    "git-sync": "services.git_sync",
    "code-review": "services.code_review",
    "log-cleanup": "services.log_cleanup",
    "disk-health": "services.disk_health",
}


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <service-name>", file=sys.stderr)
        sys.exit(1)

    service_name = sys.argv[1]
    config = load_config()
    global_config = config["global"]

    # Ensure we're running from the project root
    os.chdir(global_config["project_root"])

    service_def = config["services"].get(service_name)
    if not service_def:
        print(f"Unknown service: {service_name}", file=sys.stderr)
        print(f"Available: {', '.join(config['services'].keys())}", file=sys.stderr)
        sys.exit(1)

    if not service_def.get("enabled", True):
        print(f"Service {service_name} is disabled.", file=sys.stderr)
        sys.exit(0)

    logger = setup_service_logger(service_name, global_config)
    logger.info("Starting service: %s", service_name)

    service_type = service_def.get("type", "python")
    service_config = service_def.get("config", {})

    try:
        if service_type == "python":
            module_path = SERVICE_MODULES.get(service_name)
            if not module_path:
                # Fall back to deriving from script path
                script = service_def["script"]
                module_path = script.replace("/", ".").removesuffix(".py")

            module = importlib.import_module(module_path)
            module.run(service_config, global_config, logger)

        elif service_type == "bash":
            script = os.path.join(global_config["project_root"], service_def["script"])
            logger.info("Handing off to bash script: %s", script)
            os.execv("/bin/bash", ["/bin/bash", script])

        else:
            logger.error("Unknown service type: %s", service_type)
            sys.exit(1)

    except Exception:
        logger.exception("Service %s failed with an unhandled exception", service_name)
        sys.exit(1)

    logger.info("Service %s completed", service_name)


if __name__ == "__main__":
    main()
