# Unsloth Monitor

Read PROJECT_SPEC.md and docs/PROGRESS.md before continuing. Linux comes first.
This workspace was initially accessed on Windows; do not claim Fedora or CachyOS
validation without actual results from those separate computers.

- Build native Qt widgets, never a web dashboard or inference client.
- Passive, bounded, normal-user reads only. No inference requests, model loads,
  compute runtimes, hardware changes, startup entries, or services.
- No invented readings. Every metric carries source, timestamp, units and state.
- Keep hardware and network collection separate and off the GUI thread.
- Never equate GPU activity with generation or a model catalog with loaded models.
- Tests may use fixtures; normal operation must never substitute fixture data.
- Closing the window exits. Keep polling and all retained data bounded.
- Never commit credentials, private logs, model weights or generated packages.
- License is undecided: do not publish a public release until the user confirms it.
- Record exact test environments and outstanding validation in docs/PROGRESS.md.
- Use an isolated environment and `python -m pytest`; no global package installs.
