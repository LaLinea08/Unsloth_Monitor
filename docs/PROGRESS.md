# Project progress

Updated: 2026-09-26. License decision: **undecided**, as requested by the user.
No public release is authorized while the license remains undecided.

## Implemented

- Native PySide6/Qt widget dashboard, dark industrial layout, resizable scroll
  fallback, source/state/time tooltips, truthful missing fields, and local
  connection/refresh settings. Tokens are session-only.
- Linux CPU identity/utilization, RAM, uptime, CPU hwmon sensors, discovered AMD
  GPU identity/activity/VRAM/temperature/SoC power. Static discovery is cached,
  reads are bounded, missing/denied/unsupported states are explicit, and the
  first CPU sample is pending. Suspended GPUs skip optional sensor inputs.
- Passive local Unsloth liveness adapter with strict source-verified signature,
  two-second overall deadline, 32 KiB body limit, connection reuse, authentication
  classification, and no raw response/credential logging. Model and inference
  fields remain unavailable; no heavier endpoints are silently probed.
- Independent hardware/network workers with single replaceable result slots,
  bounded backoff, five-second default polling and 30-second minimized polling.
  Restoring preserves snapshot age; old data becomes stale.
- Manual launch, duplicate-instance lock, and asynchronous close/worker cleanup.
  No startup registration, tray persistence, services, compute runtime, model
  loads, inference traffic, hardware-setting writes, or fixture substitution.
- Read-only `scripts/diagnose.py`, process-tree overhead observation script,
  CI checks, PyInstaller/AppImage candidate configuration, icon, and documentation.

## Verified evidence and exact environment

Actual development host: **Windows 11 build 26200, AMD64; CPython 3.14.6;
PySide6/Qt 6.11.2**, using the repository's isolated `.venv`. Neither named Linux
computer was accessible during this session. The Windows platform collector
deliberately returns unsupported hardware metrics; this is not a Windows port.

- Linux collector fixtures: **29 passed**. These exercise real file-reading
  paths against synthetic procfs/sysfs trees, including permissions, counter
  resets, discovery, units, missing readings, and no optional input reads when
  the GPU is suspended. They establish no real GPU compatibility.
- Final complete local suite: **83 passed in 7.87 seconds**.
- Latest lifecycle/UI/polling subset: **10 passed in 5.89 seconds**. This includes
  actual Qt close handling while a network worker waits, independent hardware
  progress, worker cleanup, minimized stale restore, formatting, and two real
  processes proving duplicate rejection and lock release/reopen.
- The populated default 820×900 window fits with no scrollbars using the Windows
  offscreen plugin and `QT_QPA_FONTDIR=C:\Windows\Fonts`. The 460×460 layout test
  verifies horizontal fit; smaller windows can scroll vertically.
- Ruff passed across source, tests and scripts; git diff whitespace checks passed.
  Actual offscreen application launch, screenshot and clean exit passed.
  Linux CI results must be recorded when run.
- The upstream Unsloth liveness implementation was inspected at commit
  `b6ee1739d4714193dcba0f3585cb79f839c435ab`; [TELEMETRY.md](TELEMETRY.md) records
  sources and rejected endpoints. Installed Fedora/CachyOS Unsloth versions,
  actual endpoint/auth requirements, and end-to-end compatibility are unverified.

## Measurements and packaging

Preliminary Windows offscreen source observation: mean process-tree RSS 64.46 MiB,
peak 64.48 MiB over 59.23 measured seconds after 10 seconds warm-up; CPU counter
delta rounded to 0.000% of one logical CPU (below resolution, not zero overhead).
Two observed processes, clean exit. See [PERFORMANCE.md](PERFORMANCE.md).
The 100 MiB RSS and <0.5% of one logical CPU figures are targets only. No long-
session, GPU idle-power, visible Linux, or packaged CachyOS result exists. No
inference benchmark was authorized or run.

Ubuntu 22.04 x86_64 / Python 3.11 AppImage candidate build and extracted-payload
smoke workflows are prepared. They have not yet established a successful Linux
package, actual Wayland/X11 launch, or portable compatibility. Workflow artifacts
are for review; release publication remains blocked on license confirmation and
real-machine acceptance. See [COMPATIBILITY.md](COMPATIBILITY.md).

## Known limits

- Only one discovered AMD GPU is selected; other GPU vendors and Windows
  telemetry are unsupported. Restart after hardware or driver/sensor changes.
- Liveness does not establish loaded model, quantization, context, backend,
  generation state, output token counts/rate, or request duration.
- Runtime-state guards do not prove zero GPU wake/power effect. A broken Linux
  driver can block a sysfs read indefinitely; the GUI stays responsive, but
  shutdown may wait for that worker. This has not been tested on target hardware.
- No actual Fedora, CachyOS, Wayland, X11, or packaged runtime validation has
  occurred. Other distributions and older glibc systems are not certified.

## Next concrete action

On the **Fedora development computer**, from a complete checkout, run:

```bash
python3 scripts/diagnose.py
```

This requires Python 3.11+ and no installed project dependencies. It reads local
hardware and makes one bounded liveness GET, writes no files, installs nothing,
changes no settings, and sends no inference content. An offline Unsloth result
on Fedora is expected if Unsloth is not running there. Review the selected output
before sharing, and record the exact Fedora version/kernel/session. Keep any
later CachyOS output separate. Continue with the same native dashboard after
the readings are verified; no separate editions are needed.
