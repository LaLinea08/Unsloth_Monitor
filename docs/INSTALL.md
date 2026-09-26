# Installation and packaging

The application uses your installed terminal's font, palette, background and
transparency. Launching from an existing terminal keeps that terminal; opening
the AppImage from the desktop opens an installed terminal automatically. No Qt,
terminal emulator, embedded browser or inference runtime is bundled.

## Development AppImage

Download the single `Unsloth-Monitor-x86_64.AppImage` asset from
[GitHub Releases](https://github.com/LaLinea08/Unsloth_Monitor/releases).
These are development prereleases; no stable release is approved. The release
notes contain its SHA-256 checksum, test results and preliminary process
observations. Optional GitHub source archives are not needed to run the app.
See PROGRESS.md for actual completed runs.

From your normal terminal, compare this command's output with the SHA-256 in
the release notes:

```sh
sha256sum Unsloth-Monitor-x86_64.AppImage
```

Allow the downloaded file to run: in your file manager's properties, enable
the executable permission (often called **Allow executing file as program**),
or use:

```sh
chmod +x Unsloth-Monitor-x86_64.AppImage
```

You can then double-click the AppImage. If the file manager asks whether to
open or execute it, choose **Run/Execute**. Some file managers or desktop
security policies require their own explicit approval for downloaded
executables; the monitor does not change those policies. You can also launch
from your normal terminal:

```sh
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

When opened without an attached terminal, the app first uses
`xdg-terminal-exec` if installed, which follows the desktop's configured terminal.
Otherwise it honors a supported terminal executable named by `TERMINAL` or
KDE's existing `TerminalApplication` preference, then tries the desktop's usual
terminal: Konsole on KDE, GNOME Terminal on GNOME, or Xfce Terminal on XFCE.
Installed generic alternatives are the final fallback. Preferences containing
shell commands are not executed, and `TERM` is never treated as a program name.
No terminal is installed or configured by the monitor.

The desktop handoff requires an active graphical session and an installed
terminal. If discovery fails, run the AppImage from your terminal to see the
launch error. A guard prevents repeated terminal launches if an emulator fails
to provide a TTY. The AppImage reopens its original downloaded file for the
terminal child, so it does not depend on a launcher process retaining a
temporary mount. Native file-manager, Konsole and Wayland/X11 behavior still
requires target-desktop validation; CI's terminal stand-in does not establish it.
For a desktop-menu entry, see the optional instructions below.

## Controls and preferences

The dashboard lists its keyboard controls. Quit with `q` or Ctrl+C, refresh with
`r`, edit connection with `s`, change interval with `i`, view sources with `d`, and
toggle 30-second quiet mode with `p`. Tokens are entered without echo and remain
in process memory only. Normal preferences are saved on explicit edits under
`${XDG_CONFIG_HOME:-~/.config}/unsloth-monitor/settings.json`.

The terminal does not expose a portable minimized-window signal. Use quiet mode
when leaving it in the background; foreground/default polling is 5 seconds.
Closing the terminal or the monitor's tab ends the dashboard and its collectors;
`q` closes the dashboard and returns to the existing shell, or lets a terminal
opened for the AppImage close normally. No service, tray process or startup
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
packaged terminal launch, desktop-handoff smoke and resource observations pass,
a separate job prepares
and publishes a development prerelease with one `Unsloth-Monitor-x86_64.AppImage` asset.
Its notes contain the checksum, source commit, build link and test observations.
GitHub also provides optional source archives; they are not needed to run the app.

Public publication is gated by the repository Actions variable
`RELEASE_PUBLICATION_APPROVED`. The owner explicitly authorized automatic
development prereleases on 2026-09-26 while keeping the project license
undecided; the variable is now `true` for this authorized publication.
Each tag includes its source commit and workflow run ID;
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
checkout and without development PYTHONPATH/VIRTUAL_ENV. The additional launcher
smoke starts without a TTY, uses a test-only `xdg-terminal-exec` stand-in to open
a PTY, and runs the actual dashboard. It checks argument preservation, output,
clean child exit and release of the instance lock. To run these launch checks
inside the isolated Linux developer environment:

```sh
python scripts/pty_smoke.py
python scripts/launcher_smoke.py
python scripts/launcher_smoke.py --executable "$PWD/dist/Unsloth-Monitor-x86_64.AppImage" --appimage
```

The last command runs the real outer AppImage with `APPIMAGE_EXTRACT_AND_RUN=1`,
including the second outer-file launch inside the fixture terminal. It validates
the bundled runtime and handoff without requiring FUSE or a graphical display.
This is not a real file-manager click or terminal-emulator acceptance test and
does not certify Konsole, physical displays, mounted FUSE, GPU sensors, or the
user's installed Unsloth. See PROGRESS.md for completed runs and pending checks.
