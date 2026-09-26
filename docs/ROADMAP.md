# Linux-first roadmap

The user has explicitly selected an application inside the computer's normal
terminal. This supersedes the original Qt-window requirement. The current
deliverable is a curses dashboard, shared passive runtime, source, and tests;
the first milestone still requires actual Fedora execution and measurements.

1. **Fedora terminal prototype acceptance.** Run the read-only diagnostic and
   record exact OS/kernel/terminal/display-session versions. Verify hardware
   readings, launch in the normal terminal with Unsloth offline, exercise
   keyboard controls, resize/scroll, quiet mode, source details, duplicate
   prevention, and clean terminal restoration. Measure monitor and incremental
   terminal-emulator overhead.
2. **CachyOS verification.** Run the same application directly beside Unsloth.
   Record installed Unsloth version, actual loopback endpoint/authentication,
   GPU readings, liveness starts/restarts, and normal CachyOS terminal behavior.
   Keep results separate from Fedora. No remote exposure is required.
3. **Additional verified telemetry.** Add model residency or request metrics only
   after validating a passive, content-free source and its overhead against the
   installed version. Define scope and units first. GPU load is not generation;
   a model catalog is not residency.
4. **Linux package acceptance.** The Ubuntu 22.04 x86_64 AppImage candidate now
   builds and its bundled runtime launches in a CI pseudo-terminal. Next test
   ordinary AppImage launch in a real terminal without development Python.
   Check curses/terminfo, host terminal integration, networking, sensors,
   keyboard input, and restoration on exit. Validate both target desktops,
   packaged overhead, and hours-long operation. Inference comparisons need
   separate explicit approval.
5. **Publication.** Automatic draft development releases contain one AppImage
   and checksum/test evidence in notes. Public publication needs an explicit
   resolution of the earlier license hold; the project license remains
   undecided. Complete real-machine acceptance before a stable release. Keep
   binaries in workflow artifacts/release assets, outside the source repository.
6. **Later expansion.** Broaden tested distributions and terminals, consider
   additional GPU vendors and multiple-GPU selection, then implement and test
   Windows telemetry/terminal packaging. Measure Windows independently before
   advertising support. Other package formats need their own validation.

No milestone adds automatic startup, services, privileged sensor access,
hardware changes, model loads, or inference requests for monitoring. Windows
work must not delay a useful validated Linux version.
