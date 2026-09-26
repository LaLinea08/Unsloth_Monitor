# Compatibility and validation

Linux is the target; no Linux distribution or GPU has yet been validated on an
actual target machine. Expected compatibility must not be read as a tested claim.
The Fedora and CachyOS computers are separate systems, and localhost always
refers to the computer running the monitor.

| Environment | What actually ran | Status |
| --- | --- | --- |
| Windows 11, build 26200, AMD64; CPython 3.14.6; PySide6/Qt 6.11.2 | Fixture tests, synthetic local HTTP tests, offscreen Qt lifecycle/layout, actual duplicate-process locking and shutdown | Development validation only; hardware sensors deliberately unsupported |
| Fedora; Ryzen 7 9800X3D; Radeon RX 9070 XT | Nothing on this separate computer yet | Target hardware supplied by user; OS/kernel/session versions and readings unverified |
| CachyOS; KDE Plasma/Wayland; Ryzen 5 5600X; Radeon RX 9060 XT 16 GB; 16 GB RAM | Nothing on this separate computer yet | Primary Unsloth and packaged-performance target; installed versions, API/auth and readings unverified |
| Ubuntu 22.04 x86_64 CI; Python 3.11 and 3.14 | Workflow configuration prepared | CI results pending; a headless pass would validate tests only |
| Ubuntu 22.04 x86_64 AppImage baseline; Python 3.11 | Build and extracted-payload smoke workflow prepared | No successful package build or real desktop launch established |
| Other Fedora/Arch/CachyOS/Ubuntu/Debian versions and derivatives | No execution yet | Expected candidates only where runtime/driver requirements are met |
| Windows packaged application; other architectures | No build or telemetry implementation | Unsupported in this phase |

## Runtime and device limits

The proposed portable package uses an Ubuntu 22.04 build baseline and bundles
Python/Qt. It is not universally compatible: systems with an older glibc than
the build environment, non-glibc systems, and other architectures are outside
the initial baseline. Newer distributions still need packaged validation for
Qt platform plugins, host display libraries, networking, fonts, and sensors.
An AppImage does not bundle the host kernel or GPU drivers. See
[installation instructions](INSTALL.md) for host/runtime details.

Wayland and X11 sessions must be tested separately. Offscreen Qt tests establish
neither. On the initial Windows offscreen test host, setting
`QT_QPA_FONTDIR=C:\Windows\Fonts` was needed to render real fonts in screenshots;
this is a test-platform setting, not a Linux installation instruction.

The current GPU adapter discovers AMD DRM cards, chooses the largest
driver-reported VRAM capacity, and reads accessible sysfs/hwmon files. Intel and
NVIDIA GPU telemetry and multiple-GPU selection are not implemented. CPU/RAM/
uptime collection continues when GPU support or sensors are absent. GPU names
can fall back to a verified PCI ID. Sensors denied to a normal user remain
permission-denied; the app does not request privileged access. Restart after
hardware hotplug or driver/sensor changes because discovery is cached.

Optional GPU inputs are skipped when runtime power state is suspended,
transitional, unknown, unreadable, or erroneous. This does not prove zero idle
power impact: actual driver behavior still needs measurement. Tctl can be a
control-temperature value, APU VRAM is not independent dedicated RAM, and APU
SoC power may include CPU power. Source tooltips preserve these distinctions.

## Unsloth limits

The passive liveness contract was inspected in upstream source, not in either
installed test machine. Only numeric loopback HTTP endpoints and `localhost`
are supported. An installation without the source-verified liveness route is
reported as unsupported; the monitor does not probe heavier endpoints instead.
Model residency, quantization, context, backend, generation state, and token
statistics remain unavailable through this adapter. See [TELEMETRY.md](TELEMETRY.md).

The immediate validation step is to run `python3 scripts/diagnose.py` from a
complete checkout on Fedora. It uses Python 3.11+ and the standard library only,
reads selected local metrics, and makes one bounded liveness GET. It installs
nothing, sends no prompts, and changes no configuration. An offline Unsloth
result on Fedora is acceptable. Record Fedora results separately; later run the
same diagnostic directly on CachyOS beside its Unsloth installation.
