# Compatibility and validation

The current application is a Linux terminal dashboard. The user's later request
to use the computer's normal terminal supersedes the earlier graphical Qt design.
It inherits that terminal's appearance; it does not recreate a particular
CachyOS theme. No actual target Linux computer has yet been validated.

| Environment | What actually ran | Status |
| --- | --- | --- |
| Windows 11 build 26200, AMD64; CPython 3.14.6 | Hardware fixtures, local HTTP fixtures, pure terminal rendering, simulated keyboard and runtime tests; 29 portable launcher boundary tests passed | Development validation only; interactive application and hardware telemetry are unsupported on Windows |
| Fedora; Ryzen 7 9800X3D; Radeon RX 9070 XT | Nothing on this separate computer yet | User-provided target hardware; exact OS/kernel/session and readings unverified |
| CachyOS; KDE Plasma/Wayland; Ryzen 5 5600X; Radeon RX 9060 XT 16 GB; 16 GB RAM | Nothing on this separate computer yet | Primary Unsloth and packaged-performance target; versions, API/auth, and readings unverified |
| Ubuntu 22.04 x86_64 CI; Python 3.11.16 and 3.14.7 | 122 tests passed on each Python; actual curses source launch in a pseudo-terminal passed | Linux CI verified; target GPU and visible emulator behavior remain unverified |
| Ubuntu 22.04 x86_64 AppImage baseline; Python 3.11 | AppImage built; extracted bundled payload launched through actual curses in a pseudo-terminal; no Qt in payload | Candidate package CI verified; normal AppImage mount/launch and target desktop acceptance remain pending |
| Linux no-TTY desktop handoff; source and AppImage extract-and-run | Test-only terminal stand-in and real dashboard PTY smoke implemented | Pending CI execution for this revision; native file-manager clicks, Konsole/GNOME/Xfce and Wayland/X11 behavior remain unverified |
| Other Linux distributions or terminal emulators | No execution yet | Candidates for later validation; no universal compatibility claim |
| Windows packaged app; other architectures | No terminal port/package validation | Unsupported in this phase |

Historical Qt 6.11.2 offscreen tests ran on the Windows host before the terminal
request. They are evidence for a superseded implementation and must not be used
as proof of current curses, terminal-emulator, or packaged compatibility.

The terminal candidate at commit `edbd92d` passed
[package workflow 36263567059](https://github.com/LaLinea08/Unsloth_Monitor/actions/runs/36263567059).
An extracted-payload launch proves the bundled terminal runtime runs in CI;
it does not prove the AppImage mount path or actual target desktop integration.

## Terminal and package requirements

Launch inside an interactive terminal, or open the executable AppImage from a
graphical desktop to start an installed terminal automatically. The source
version needs Python 3.11+ with curses; the AppImage bundles the runtime. The
terminal's `TERM` setting and matching host terminfo entry must be available.
There is no pinned font or palette. Desktop handoff prefers `xdg-terminal-exec`,
supported existing terminal preferences and desktop-specific installed fallbacks;
it neither installs nor changes a terminal. Executable permission and the file
manager's policy for running downloaded programs still apply. An optional menu
entry uses `Terminal=true`. Actual desktop integration is still unverified.
Wayland/X11 rendering belongs to the host terminal emulator and must still be
checked on each target desktop. A Linux pseudo-terminal test has no visible
emulator and cannot establish font, theme, window behavior or real terminal-close
handling. The new launcher smoke exercises no-TTY handoff and actual AppImage
extract-and-run through a fixture emulator; it does not test the FUSE mount path.

The portable build baseline is Ubuntu 22.04 x86_64. Systems with an older glibc
than the build environment, non-glibc systems, and other architectures are
outside the initial baseline. Newer distributions still need packaged testing
for runtime libraries, curses/terminfo, networking, and sensors. AppImage does
not bundle the host kernel or GPU drivers. See [INSTALL.md](INSTALL.md).

## Device and integration limits

The AMD adapter discovers DRM cards and selects the largest driver-reported
VRAM capacity. Intel/NVIDIA GPU telemetry and multiple-GPU selection are not
implemented. CPU/RAM/uptime continue when GPU or sensor support is absent.
Names can fall back to a verified PCI ID. Inaccessible sensors remain denied;
no privilege escalation is attempted. Restart after hardware hotplug or
driver/sensor changes because discovery is cached.

Runtime-state checks skip optional GPU sensors on suspended, transitional,
unknown, erroneous, or unreadable states. This does not prove zero idle-power
effect. Tctl may be a control temperature, APU VRAM is not separate dedicated
RAM, and APU SoC power can include CPU power. Press `d` for source details.

The passive Unsloth liveness contract was checked in upstream source, not in an
installed target version. Only local HTTP loopback endpoints are accepted.
Unsupported installations remain unsupported instead of triggering heavier
endpoint probes. Model residency, quantization, context, backend, generation,
and token statistics remain unavailable through this adapter. See
[TELEMETRY.md](TELEMETRY.md).

Next, run `python3 scripts/diagnose.py` from a complete checkout on Fedora.
It needs Python 3.11+ and the standard library, installs nothing, changes no
configuration, and sends no prompts. Unsloth offline on Fedora is acceptable.
Later run it directly on CachyOS beside Unsloth; record the two machines
separately. Localhost on Fedora never refers to the CachyOS computer.

A user-provided screenshot shows the earlier monitor online with AMD GPU and
Ryzen 5 5600X readings on the target setup. It is evidence of a visible running
session, not controlled telemetry accuracy, performance, or new launcher/activity
acceptance. Exact OS/terminal/Unsloth versions were not supplied in that image.
