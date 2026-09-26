# Project progress

Updated: 2026-09-26. License: **undecided**, as explicitly requested by the user.
No public release is authorized while the license remains undecided.

## Current direction

The user explicitly requested the application **inside the computer's normal
terminal**, inheriting its appearance. This supersedes the original Qt-widget
requirement. The earlier Qt implementation and UI tests were removed. Current
runtime code has no Qt dependency and does not define a font, fixed color
palette, or background theme. PROJECT_SPEC.md preserves the original brief;
the latest user decision governs the interface.

## Implemented

- Terminal-native curses dashboard, pure bounded renderer, responsive terminal
  resize, scrolling on smaller terminals, honest missing readings, and a source/
  unit/time/state view. Unknown bars use question marks, not fabricated zero.
- Keyboard controls: q quit, r refresh, s connection settings, i interval,
  p quiet mode, d sources, arrows/Page Up/Page Down scroll. Token input is hidden,
  bounded, and session-only; URL/interval preferences can be saved.
- Linux CPU identity/utilization, RAM, uptime, CPU sensors, and discovered AMD GPU
  identity/activity/VRAM/temperature/SoC power. Cached discovery, bounded reads,
  baseline CPU pending state, explicit missing/denied/unsupported readings, and
  skipped optional sensor inputs for suspended GPUs.
- Source-verified local liveness adapter with strict signature, two-second
  overall deadline, 32 KiB response limit, reuse, authentication classification,
  and no raw credential/response logging. Model/inference fields remain absent.
- Independent hardware/network workers, one replaceable result per source,
  bounded backoff, five-second default intervals, explicit 30-second quiet mode,
  stale-state handling, and rejection of obsolete configuration results.
- Manual launch, Linux duplicate-process locking, terminal restoration, and
  cleanup on q/Ctrl-C/SIGTERM/SIGHUP. No startup registration, services, compute
  runtime, model loading, inference traffic, or hardware-setting writes.
- Read-only diagnostic and Linux process-tree observer; source and package
  pseudo-terminal CI configuration, AppImage build configuration, optional
  terminal desktop launcher, and supporting documentation.

## Actual evidence

Development host: **Windows 11 build 26200, AMD64, CPython 3.14.6**, using the
repository's isolated environment. Neither specified Linux computer was
accessible. Windows hardware telemetry and interactive application launch are
explicitly unsupported; portable tests do not establish a Windows port.

- Current complete local terminal-era run: **121 passed, one Linux-only lock
  test skipped on Windows**. Ruff passed for the complete tree.
- Ubuntu 22.04 x86_64 CI: **122 passed** on **Python 3.11.16** and **3.14.7**
  at `abc2b39` ([checks](https://github.com/LaLinea08/Unsloth_Monitor/actions/runs/36264025134)).
  Actual source curses launch in a pseudo-terminal passed on both versions.
- Current terminal renderer/keyboard subset: **23 passed in 0.07 seconds**.
  Covers 80×24 layout, narrow/wide Unicode bounds, source details, control-character
  filtering, stale/missing values, quiet/refresh/interval keys, hidden token
  input, cancellation, safe save errors, unchanged-frame redraw suppression,
  cleanup, and moving back after scrolling past the end.
- Linux hardware fixture subset: **29 passed**. Exercises normal file-reading
  paths against synthetic procfs/sysfs, including denied/missing files, counters,
  discovery, units, and suspended-device input avoidance.
- At commit `edbd92d`, the AppImage built, the extracted bundled payload launched
  through actual curses in a Linux pseudo-terminal, and the payload was checked
  to contain no Qt. See
  [package workflow 36263567059](https://github.com/LaLinea08/Unsloth_Monitor/actions/runs/36263567059).
  Normal AppImage mount/launch, visible terminal emulators, and target-machine
  acceptance remain unverified.
- Earlier PySide6/Qt 6.11.2 offscreen Windows tests belonged to the superseded
  GUI and are not current terminal acceptance evidence.
- Official Unsloth source at
  `b6ee1739d4714193dcba0f3585cb79f839c435ab` establishes the inspected liveness
  contract. Installed Fedora/CachyOS versions and actual endpoint/auth remain
  unverified. [TELEMETRY.md](TELEMETRY.md) records exact source evidence.

## Performance and packaging

Final terminal package observation on Ubuntu 22.04 CI averaged 21.96 MiB tree
RSS and 0.219% of one logical CPU over 59.25 s after 10 s warm-up; one process,
clean exit. After reducing quiet-mode idle UI wakeups, quiet averaged 21.89 MiB
and 0.051% CPU over 59.24 s. No actual target-GPU idle power, hours-long
memory or packaged CachyOS result exists. The ≤100 MiB RSS and <0.5% CPU targets
are not target-machine acceptance claims. No inference benchmark was run.
[PERFORMANCE.md](PERFORMANCE.md) distinguishes synthetic PTY observation from
actual emulator overhead and superseded Qt results.

The Ubuntu 22.04 x86_64 / Python 3.11 AppImage candidate built successfully and
its extracted bundled runtime passed a Linux pseudo-terminal smoke test without
Qt. The final terminal candidate at `abc2b39` is 17,132,024 bytes with SHA-256
`920942126725475a4393f7632a7c7b523ff329dff9bdc3d3ba054470b8ac7dec`.
[Final build passed](https://github.com/LaLinea08/Unsloth_Monitor/actions/runs/36264025155);
[download candidate artifact](https://github.com/LaLinea08/Unsloth_Monitor/actions/runs/36264025155/artifacts/10913450556)
(14-day retention, GitHub sign-in may be required). SHA256SUMS was corrected to
verify from the artifact directory. Source is in
[draft PR #1](https://github.com/LaLinea08/Unsloth_Monitor/pull/1).
This is a CI candidate, not actual target-desktop acceptance. Release remains
blocked on license confirmation and real-machine acceptance.

## Known limits

- One selected AMD GPU; other GPU vendors and Windows telemetry unsupported.
  Restart after hardware/driver/sensor changes because discovery is cached.
- Liveness does not establish loaded model, quantization, context, backend,
  generation, token counts/rate, or request duration.
- Terminal minimization cannot be detected reliably; quiet polling is explicit.
- Driver state guards do not prove zero GPU wake/power effect. A faulty Linux
  sysfs read can block indefinitely and delay worker shutdown; untested on
  target hardware.
- A Linux PTY test cannot establish actual terminal font/theme/window behavior,
  target GPU compatibility, or host desktop integration. Older glibc systems,
  other architectures, and untested distributions are not certified.

## Next concrete action

On the **Fedora development computer**, from a complete checkout:

```bash
python3 scripts/diagnose.py
```

Python 3.11+ and the standard library suffice. The script reads selected hardware,
makes one bounded liveness GET, writes no files, installs nothing, changes no
settings, and sends no inference content. An offline Unsloth result is acceptable
on Fedora. Review the output before sharing and record the Fedora/kernel/session
versions. Keep later CachyOS results separate, then launch this same dashboard
in the computer's normal terminal.
