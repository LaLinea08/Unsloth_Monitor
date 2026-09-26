# Installation and packaging

No stable release is available. Source development steps are in README.md.
Keep the source environment isolated. Do not use sudo pip or install drivers,
sensor detection utilities or services for this monitor.

## Candidate AppImage

The packaging workflow builds on Ubuntu 22.04 x86_64 (glibc 2.35), with CPython
3.11 and PySide6 Essentials 6.11.2. This is a candidate baseline, not a promise
that every distribution with that glibc runs the package. Qt documents a
[glibc 2.34 floor for Qt 6.10+](https://doc.qt.io/qt-6/linux.html); the full bundle's
actual floor can be higher. AppImage recommends
[building on an old enough baseline and testing target systems](https://docs.appimage.org/reference/best-practices.html).
Ubuntu 20.04 and Debian 11 are outside this selected baseline. x86_64 only.

PyInstaller onedir bundles the Python runtime and Qt widgets/plugins; it avoids
single-executable runtime unpacking. AppImage wraps that directory. Qt QML/Quick,
ML frameworks and inference runtimes are excluded. appimagetool 1.9.1 and its
runtime are verified against pinned SHA-256 values. Builds stay workflow artifacts,
not source commits. The app never launches as an installation side effect.

After downloading a validated candidate artifact and checking SHA256SUMS:

```sh
chmod +x Unsloth-Monitor-x86_64.AppImage
./Unsloth-Monitor-x86_64.AppImage
```

This needs no user-installed Python. A working graphical session, host graphics
drivers, compatible glibc/libstdc++, system fonts and Qt platform libraries remain
host requirements. X11 commonly needs xcb/xkbcommon and xcb-cursor libraries;
Wayland needs a functioning Wayland session and its client libraries. The exact
host dependency list must be checked on target systems. The AppImage runtime
may require FUSE support; do not install it automatically. If unavailable:

```sh
./Unsloth-Monitor-x86_64.AppImage --appimage-extract
./squashfs-root/AppRun
```

Launch the extracted package from a stable directory. `QT_QPA_PLATFORM=xcb`
selects X11/XWayland; `QT_QPA_PLATFORM=wayland` selects native Wayland where
the packaged plugin and host session support it. Neither path is advertised
as validated until a recorded graphical launch on the target system.

The workflow checks extracted payload launch with the offscreen Qt platform,
outside the checkout and without development PYTHONPATH/VIRTUAL_ENV.
That validates basic runtime imports and widget launch, not a native display,
FUSE mounting, fonts on every host, sensors, or actual Unsloth.

## Optional menu launcher

Copy `packaging/unsloth-monitor.desktop` to your own
`~/.local/share/applications/` only if desired. Change Exec to the quoted absolute
AppImage path and Icon to an accessible copy of the supplied SVG. No installer
does this automatically, and no file belongs in `~/.config/autostart`.

## Uninstall

Close the monitor; delete its AppImage or extracted directory. Remove any menu
launcher you created yourself. If desired, remove only the monitor's preference
directory (normally `~/.config/UnslothMonitor/Unsloth Monitor` on Linux). No
services, startup entries, drivers or AI configuration are installed.

For source builds, remove the checkout's `.venv` when no longer needed. The
monitor does not own or remove Unsloth, models or other applications' files.
