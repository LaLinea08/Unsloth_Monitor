# Linux-first roadmap

The current deliverable is a runnable native prototype and its source/tests.
The first milestone is not complete until it runs on the actual Fedora computer
and its preliminary overhead has been measured there.

1. **Fedora prototype acceptance.** Run the read-only diagnostic, record exact
   OS/kernel/display-session versions, verify CPU/RAM/uptime and the discovered
   AMD GPU, launch the native dashboard with Unsloth offline, verify shutdown and
   duplicate prevention, and measure visible/minimized overhead. Fix evidence-
   based collector or layout problems before adding optional features.
2. **CachyOS verification.** Run the same application locally beside Unsloth.
   Record installed Unsloth version, actual loopback endpoint, authentication,
   driver readings, liveness behavior, starts/restarts, and KDE/Wayland behavior.
   Keep this record separate from Fedora. Remote monitoring is not required.
3. **Additional verified telemetry.** Add residency or request metrics only
   after checking a passive, content-free source and its overhead on the
   installed version. Define scope and units first; unavailable fields remain
   unavailable until trustworthy evidence exists. Never infer generation from
   GPU load or loaded models from a catalog.
4. **Linux package and acceptance.** Build the Ubuntu 22.04 x86_64 AppImage
   candidate; validate the extracted payload and actual portable launch without
   a development environment. Test fonts, Qt plugins, networking, sensors,
   Wayland and X11 where available. Run packaged overhead and long-session
   checks on CachyOS. Inference comparisons require separate explicit approval.
5. **Publication.** Confirm the project license, complete real-machine package
   acceptance, choose the primary download, and publish an authorized release.
   The license remains undecided, so public release is blocked. Keep binaries
   in workflow artifacts/release assets rather than the source repository.
6. **Later expansion.** Broaden tested Linux distributions, consider multiple-GPU
   views and additional vendors, then implement Windows telemetry and packaging.
   Measure Windows independently before advertising support. Flatpak or native
   distribution packages need their own permission and telemetry validation.

No milestone introduces automatic startup, a background service, model loading,
inference requests for monitoring, privileged sensor access, or hardware changes.
Windows work must not delay a useful tested Linux release.
