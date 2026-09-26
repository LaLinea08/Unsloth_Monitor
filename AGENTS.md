# Unsloth Monitor

Read PROJECT_SPEC.md and docs/PROGRESS.md before continuing. Linux comes first.
This workspace was initially accessed on Windows; do not claim Fedora or CachyOS
validation without actual results from those separate computers.

- The user changed the UI requirement to run inside their normal terminal and
  inherit its appearance. Use the terminal-native curses dashboard, no fixed
  RGB theme and no Qt dependency in the primary package. Use the terminal's ANSI
  palette for readable accents and its default background. Manual desktop launch
  may open the existing host terminal. See PROJECT_SPEC amendments.
  Never build a web dashboard or inference client.
- Passive, bounded, normal-user reads only. No inference requests, model loads,
  compute runtimes, hardware changes, startup entries, or services.
- No invented readings. Every metric carries source, timestamp, units and state.
- Keep hardware and network collection separate and off the GUI thread.
- Never equate GPU activity with generation or a model catalog with loaded models.
- Tests may use fixtures; normal operation must never substitute fixture data.
- Quit/Ctrl+C closes the dashboard and workers. No background service. Terminal
  minimization is not observable portably; explicit quiet mode polls every 30s.
  Keep polling and all retained data bounded.
- Never commit credentials, private logs, model weights or generated packages.
- The user requested automatic releases with one AppImage per successful build.
  On 2026-09-26 the user explicitly authorized merging the release workflow and
  automatically publishing this and future development prereleases while the
  license stays undecided. This resolves the earlier hold for development
  prereleases. Do not select a project license or claim stable acceptance.
  Include bundled third-party notices.
- Record exact test environments and outstanding validation in docs/PROGRESS.md.
- Use an isolated environment and `python -m pytest`; no global package installs.
