# time-bound

Scheduled service framework for macOS. Uses launchd to run tasks on an always-on Mac.

## Services

- **git-sync** — Pull/push a list of repos on a schedule, with optional auto-commit
- **code-review** — Run Claude CLI against codebases on specific weeknights, saving reports to files or creating GitHub issues/PRs

## Setup

```bash
# Create and activate the venv
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Copy and edit the config
cp config.example.yaml config.yaml
# Edit config.yaml with your repos and codebases
```

## Configuration

`config.yaml` has two sections:

**global** — paths, label prefix, and environment settings for launchd:

```yaml
global:
  log_dir: logs
  label_prefix: com.embeddedartistry.time-bound
  project_root: /Users/you/src/time-bound
  python_path: /Users/you/src/time-bound/.venv/bin/python3
  path: /opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
```

**services** — each service has `enabled`, `type`, `schedule`, and a `config` block. See `config.example.yaml` for full documentation.

### Schedule format

The `schedule` list maps directly to launchd's `StartCalendarInterval`. Keys are `Hour`, `Minute`, `Weekday` (0=Sunday), `Day`, `Month`:

```yaml
schedule:
  - Hour: 9
    Minute: 0
  - Hour: 17
    Minute: 0
    Weekday: 1  # Monday only
```

### Git sync config

```yaml
config:
  repos:
    - path: /Users/you/src/my-repo
      remote: origin
      branch: main
      pull: true
      push: true
      auto_commit: false
```

### Code review config

```yaml
config:
  claude_path: /Users/you/.local/bin/claude
  reports_dir: reports
  codebases:
    - path: /Users/you/src/my-project
      name: my-project
      review_focus: "Review for code quality and potential bugs."
      days: [0, 2]           # Monday, Wednesday (0=Monday)
      output_method: file    # file, gh-issue, or gh-pr
```

`gh-issue` and `gh-pr` output methods require the [GitHub CLI](https://cli.github.com/) (`brew install gh && gh auth login`). They fall back to file output if `gh` is unavailable.

## Usage

### Manual run

```bash
.venv/bin/python3 bin/runner.py git-sync
.venv/bin/python3 bin/runner.py code-review
```

### Install launchd agents

```bash
# Install all enabled services
.venv/bin/python3 bin/install.py --all

# Install a specific service
.venv/bin/python3 bin/install.py git-sync

# List available services
.venv/bin/python3 bin/install.py --list
```

### Verify agents are loaded

```bash
launchctl list | grep time-bound
```

### Force a run

```bash
launchctl start com.embeddedartistry.time-bound.git-sync
```

### Uninstall

```bash
# Remove all agents
.venv/bin/python3 bin/uninstall.py --all

# Remove a specific agent
.venv/bin/python3 bin/uninstall.py git-sync
```

## Logs

Per-service daily logs are written to `logs/<service-name>/YYYY-MM-DD.log`. launchd stdout/stderr go to `logs/<service-name>/launchd-stdout.log` and `launchd-stderr.log` as a safety net.

## Reports

Code review output (when using `file` output method) is saved to `reports/<codebase-name>/YYYY-MM-DD-review.md`.

## Adding new services

1. Create a module in `services/` with a `run(config, global_config, logger)` function
2. Add the service to `config.yaml` with `type: python` (or `type: bash` for shell scripts)
3. Add a mapping in `bin/runner.py`'s `SERVICE_MODULES` dict (or set `script` in config)
4. Run `bin/install.py <service-name>` to install the launchd agent
