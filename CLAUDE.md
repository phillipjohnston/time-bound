# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Scheduled service framework for macOS. Uses launchd to run tasks on an always-on Mac. Python 3.14, no build system — just a venv with PyYAML and pytest.

## Commands

```bash
# Setup
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Run a service manually
.venv/bin/python3 bin/runner.py git-sync
.venv/bin/python3 bin/runner.py code-review

# Tests
.venv/bin/pytest                          # all tests
.venv/bin/pytest tests/test_git_sync.py   # single module
.venv/bin/pytest -k "test_name"           # single test

# Install/uninstall launchd agents
.venv/bin/python3 bin/install.py --all
.venv/bin/python3 bin/install.py --list
.venv/bin/python3 bin/uninstall.py --all
```

## Architecture

**Execution flow**: launchd → `bin/runner.py <service-name>` → loads `config.yaml` → imports the service module → calls `module.run(config, global_config, logger)`.

**Key files**:
- `bin/runner.py` — Dispatcher. Maps service names to modules via `SERVICE_MODULES` dict. Also supports `type: bash` services via `os.execv`.
- `bin/install.py` / `bin/uninstall.py` — Generate plist files from `templates/launchagent.plist.template` using `string.Template`, then `launchctl bootstrap`/`bootout`.
- `services/base.py` — Shared utilities: `run_command()` (subprocess wrapper), `setup_service_logger()`, `today_weekday()`, `notify()`.
- `services/git_sync.py` / `services/code_review.py` — Service implementations. Each exports a `run(config, global_config, logger)` function.
- `config.yaml` — Runtime config (not committed). Copy from `config.example.yaml`. Has `global` and `services` sections.

**Adding a new service**:
1. Create `services/<name>.py` with `run(config, global_config, logger)`
2. Add entry to `SERVICE_MODULES` in `bin/runner.py`
3. Add service config block in `config.yaml`
4. Run `bin/install.py <name>`

## Conventions

- Services are independent — one failure must not block others (each repo/codebase is wrapped in try/except)
- `run_command()` from `services/base.py` is the standard way to shell out (handles timeouts, logging, missing commands)
- Weekday numbering: config.yaml schedule uses launchd convention (0=Sunday), but code-review `days` list uses Python convention (0=Monday)
- Tests use `unittest.mock` extensively; shared fixtures are in `tests/conftest.py` (`global_config`, `mock_logger`, `sample_repo_config`, `sample_codebase_config`)
