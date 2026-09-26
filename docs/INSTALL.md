# Installation and packaging

The primary application runs inside your existing terminal and uses its default
font/colors/background/transparency. It does not launch or configure a custom
terminal emulator. No Qt, embedded browser or inference runtime is bundled.

## Candidate AppImage

No stable release is approved. The Linux workflow provides a temporary x86_64
candidate artifact containing the AppImage, SHA256SUMS, a terminal launch capture
and preliminary process observations. See PROGRESS.md for actual completed runs.

From your normal terminal, after verifying the downloaded checksum:

```sh
sha256sum -c SHA256SUMS
chmod +x Unsloth-Monitor-x86_64.AppImage
./Unsloth-Monitor-x86_64.AppImage
```

No installed Python/pip or development environment is needed. The candidate
build baseline is Ubuntu 22.04 x86_64/glibc 2.35 with CPython 3.11. Compatible glibc,
ncurses/terminfo support, a UTF-8 terminal and ordinary access to procfs/sysfs
remain host requirements. The build baseline is not universal compatibility;
Ubuntu 20.04/Debian 11 and non-x86_64 packages are not supported by this build.
See [AppImage's baseline guidance](https://docs.appimage.org/reference/best-practices.html).

AppImage mounting can require FUSE. The monitor installs nothing automatically.
If mounting is unavailable, extract and run from the same terminal:

```sh
./Unsloth-Monitor-x86_64.AppImage --appimage-extract
./squashfs-root/AppRun
```

Running without an attached terminal prints launch instructions and exits. To
launch directly from the desktop menu, optionally install the supplied desktop
entry as described below. Your terminal emulator provides Wayland/X11 support;
the monitor neither selects nor changes its compositor/backend.

## Controls and preferences

The dashboard lists its keyboard controls. Quit with `q` or Ctrl+C, refresh with
`r`, edit connection with `s`, change interval with `i`, view sources with `d`, and
toggle 30-second quiet mode with `p`. Tokens are entered without echo and remain
in process memory only. Normal preferences are saved on explicit edits under
`${XDG_CONFIG_HOME:-~/.config}/unsloth-monitor/settings.json`.

The terminal does not expose a portable minimized-window signal. Use quiet mode
when leaving it in the background; foreground/default polling is 5 seconds.
Closing the terminal ends the process. No service, tray process or startup
registration is installed. A kernel-held lock prevents duplicate instances using
the same configuration directory. The empty lock file may remain after exit;
only an active kernel lock blocks another instance.

## Optional menu launcher and removal

Copy `packaging/unsloth-monitor.desktop` to `~/.local/share/applications/` only if
desired. Set Exec to the quoted absolute AppImage path and Icon to an accessible
copy of the supplied SVG. `Terminal=true` asks your desktop to use its configured
terminal. Behavior must be checked on the target desktop; no launcher is created
automatically and no file belongs in `~/.config/autostart`.

To uninstall, quit and delete the AppImage or extracted directory, your optional
menu launcher, and optionally the monitor's config directory. No models, Unsloth
files, drivers or other applications' configuration belong to this monitor.

## Rebuilding

The Linux package workflow runs on every push to `main` or
`codex/linux-prototype`, and manual runs on those branches. After lint, tests,
packaged terminal launch and resource observations pass, a separate job prepares
a draft development prerelease with one `Unsloth-Monitor-x86_64.AppImage` asset.
Its notes contain the checksum, source commit, build link and test observations.
GitHub also provides optional source archives; they are not needed to run the app.

Public publication is gated by the repository Actions variable
`RELEASE_PUBLICATION_APPROVED`. It must remain unset until the owner explicitly
resolves the license hold. Setting it to `true` after approval enables automatic
prerelease publication. Each tag includes its source commit and workflow run ID;
reruns verify an existing release rather than replacing earlier downloads.
Successful drafts can be finalized by rerunning the publication job after the
gate is approved. A full rebuild can produce a different hash and must use a
new workflow run instead of overwriting an earlier asset.

Use the isolated developer environment from README.md. PyInstaller creates an
onedir payload; appimagetool 1.9.1 wraps it. Both the packager and runtime are
checksum-verified. The runtime upstream URL uses a rolling tag with a fixed
digest: changed upstream assets cause a build failure until deliberately reviewed.
The builder creates a fresh AppDir each time and commits no binaries. It bundles
runtime notices and source provenance at `usr/share/doc/unsloth-monitor/` inside
the AppImage, including the AppImage runtime/libfuse/squashfuse source archives.
See [third-party inventory](../packaging/THIRD-PARTY.md) for contents and limits.

CI tests source and extracted packaged launches in a pseudoterminal, outside the
checkout and without development PYTHONPATH/VIRTUAL_ENV. This exercises curses
and clean shutdown; it does not certify Konsole, any physical display, mounted
FUSE, GPU sensors, or the user's installed Unsloth.
