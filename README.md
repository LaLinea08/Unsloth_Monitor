# Unsloth Monitor

A manually launched native Qt desktop companion for Unsloth. Linux first;
passive hardware reads and a bounded local connection check, with honest missing
values. No inference requests, model loading, compute frameworks, services,
autostart registration, or web dashboard.

**Status: runnable development prototype, not a validated Linux release.**
The initial development host available to this session was Windows 11, not the
Fedora and CachyOS machines in the requirements. Their real hardware, installed
Unsloth versions, and hosting overhead still need validation. Windows hardware
collectors and packaged Windows support are not implemented.

## What works

- Linux CPU name/utilization, RAM and uptime from procfs.
- Discovered AMD GPU utilization, driver-reported VRAM, accessible temperature
  and GPU/SoC power, plus accessible CPU sensors. Missing devices do not block UI.
- Source-verified Unsloth liveness checking with explicit offline, authentication,
  unsupported-response and unverified-identity states. Automatic reconnect.
- Five-second default polling, 30 seconds minimized, separate bounded workers,
  editable loopback endpoint, session-only bearer token, and single-instance lock.
- Resizable charcoal Qt widgets; sources and availability in reading tooltips.
  Close exits and stops collectors. No invisible tray/background mode.

**Model and inference metrics are intentionally unavailable in this prototype.**
The selected liveness endpoint does not expose them. Other reviewed upstream
routes can scan model files or return inference-content previews; they are not
polled. See [telemetry evidence](docs/TELEMETRY.md). GPU activity is never treated
as proof of generation or a ROCm backend.

## Run from source on Linux

Development requires Python 3.11–3.14 and a compatible Qt desktop environment.
End-user packaging is being evaluated separately; these are developer steps.

```sh
git clone https://github.com/LaLinea08/Unsloth_Monitor.git
cd Unsloth_Monitor
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip install --no-build-isolation --no-deps -e .
python -m unsloth_monitor
```

Once this branch is merged, the default checkout contains the prototype. Until
then, check out the development branch shown in the open pull request.
Run on the **same computer as Unsloth**. `127.0.0.1:8888` always refers to that
computer. Settings accepts another local HTTP port. Close the window to exit.

## Download and install

There is **no approved public release yet**. The manually dispatched
[Linux package candidate workflow](https://github.com/LaLinea08/Unsloth_Monitor/actions/workflows/linux-package.yml)
builds an x86_64 AppImage as a temporary workflow artifact. A successful candidate
build alone is not distribution or Wayland/GPU validation. See
[installation](docs/INSTALL.md) and [compatibility](docs/COMPATIBILITY.md).

License selection is deliberately deferred at the owner's request. No project
license is granted by this repository yet; public release publication is blocked
pending that decision and package validation. Third-party components retain
their own licenses. See [LICENSE-STATUS.md](LICENSE-STATUS.md).

## Verify and contribute

```sh
python -m pytest -q
python -m ruff check src tests scripts
QT_QPA_PLATFORM=offscreen python -m unsloth_monitor --smoke-test
python3 scripts/diagnose.py
```

The last command is dependency-free and read-only: it samples hardware and
makes one bounded liveness request without installing anything or sending
prompts. Review its JSON before sharing. See [performance validation](docs/PERFORMANCE.md)
for process-resource observation and the separate, authorization-gated inference
benchmark protocol.

- [Project specification](PROJECT_SPEC.md) and [agent instructions](AGENTS.md)
- [Progress and next task](docs/PROGRESS.md)
- [Architecture](docs/ARCHITECTURE.md), [hardware](docs/HARDWARE.md), [telemetry](docs/TELEMETRY.md)
- [Compatibility and troubleshooting](docs/COMPATIBILITY.md)
- [Roadmap](docs/ROADMAP.md) and [changelog](CHANGELOG.md)

This independent companion is not an official Unsloth product.
