# Unsloth Monitor

A lightweight Linux dashboard that runs **inside your normal terminal** and
inherits its font, colors and transparency. Works with the terminal you already
use—such as Konsole on CachyOS—without imitating its theme in a separate window.

It passively reads Linux hardware and a verified Unsloth liveness interface.
No prompts, model loading, compute runtimes, proxies, services, autostart entries
or hardware changes. Quit exits the application and stops its collectors.

**Development prototype, not a validated stable release.** The first graphical
prototype was replaced at the user's explicit request with a curses interface.
Qt is no longer a runtime dependency or included in the primary package.
See [current progress](docs/PROGRESS.md) for actual test/build results.

## Run on Linux

Download **Unsloth-Monitor-x86_64.AppImage** from
[GitHub Releases](https://github.com/LaLinea08/Unsloth_Monitor/releases).
That single file bundles Python; users do not need pip or an environment.
Compare `sha256sum Unsloth-Monitor-x86_64.AppImage` with the checksum in the
release notes, then run **inside your terminal**:

```sh
chmod +x Unsloth-Monitor-x86_64.AppImage
./Unsloth-Monitor-x86_64.AppImage
```

Every successful Linux package build on `main` or `codex/linux-prototype` now
automatically publishes a versioned development prerelease with **one AppImage download**.
The checksum and test observations are in its notes; runtime notices are inside
the AppImage. The owner explicitly authorized public development prereleases
while keeping the project license undecided. Fedora/CachyOS and stable
acceptance remain pending.
[Installation and uninstall](docs/INSTALL.md) include the extraction
fallback and optional menu launcher that opens your desktop's normal terminal.

For source development (Python 3.11–3.14; no application dependencies):

```sh
git clone https://github.com/LaLinea08/Unsloth_Monitor.git
cd Unsloth_Monitor
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m unsloth_monitor
```

Run on the same computer as Unsloth: `127.0.0.1:8888` refers to the computer
running the monitor.
Endpoint and refresh settings are editable in the terminal; tokens are session-only.

## What it shows

- Linux CPU utilization/name, RAM and uptime; accessible CPU sensor.
- Discovered AMD GPU identity, utilization, driver-reported VRAM, temperature
  and GPU/SoC power. Missing or denied readings stay unavailable.
- Unsloth liveness, offline/authentication/unsupported-response states and
  automatic reconnect using bounded background workers.
- Sources and availability details. Five-second default polling; explicit quiet
  mode uses 30 seconds. The app cannot reliably detect a minimized terminal.

Model, quantization, context, backend and inference counters currently remain
unavailable. The lightweight liveness endpoint does not expose them; other
reviewed upstream routes can scan model files or return inference-content
previews. See [verified telemetry evidence](docs/TELEMETRY.md). GPU activity never
implies generation or a ROCm backend.

Windows hardware/terminal packaging is deferred until Linux is validated. A
successful Ubuntu CI run does not certify Fedora/CachyOS GPUs or hosting overhead.

## Validate

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check src tests scripts
python scripts/pty_smoke.py
python3 scripts/diagnose.py
```

The diagnostic needs only system Python 3.11+ and this checkout. It reads local
hardware and makes one bounded liveness GET; it installs nothing, sends no prompts
and writes no files. Review its JSON before sharing.

- [Specification and current UI amendment](PROJECT_SPEC.md), [agent guidance](AGENTS.md)
- [Architecture](docs/ARCHITECTURE.md), [hardware](docs/HARDWARE.md), [telemetry](docs/TELEMETRY.md)
- [Compatibility](docs/COMPATIBILITY.md), [performance](docs/PERFORMANCE.md), [roadmap](docs/ROADMAP.md)
- [Changelog](CHANGELOG.md), [license pending](LICENSE-STATUS.md)

Independent companion; not an official Unsloth product.
