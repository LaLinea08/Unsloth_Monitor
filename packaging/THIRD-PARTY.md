# Third-party runtime notices

These notices cover bundled third-party components. They do not choose or grant
a license for Unsloth Monitor itself; see LICENSE-STATUS.md.

The extracted AppImage contains this directory at
`usr/share/doc/unsloth-monitor/`. It includes CPython's installed license,
PyInstaller's installed license and bootloader exception, runtime-hook notices,
Ubuntu copyright files for the actual collected shared libraries, their common
license texts, and a binary/source inventory. An unknown native-library origin
or missing notice fails packaging. GNU readline is not needed and is excluded.

`runtime-provenance.json` identifies the checksum-verified AppImage runtime and
its source archives. `sources/` contains the complete pinned runtime source
(including its build scripts and libfuse patch), libfuse 3.15.0, and squashfuse
0.5.2. The standalone AppImage runtime is separate from the application payload.
To rebuild it, unpack the runtime archive, write its recorded commit to
`src/runtime/version`, and follow its BUILD.md and dependency script. Apply the
included libfuse patch when rebuilding that library. A modified runtime may be
combined with the extracted AppDir using appimagetool's `--runtime-file` option.
Shared libraries in the extracted application's `_internal` directory may also
be replaced with ABI-compatible builds.

The prebuilt runtime's upstream Dockerfile uses moving Alpine 3.21 packages.
Its build log is no longer available, so the precise musl, zstd, zlib and mimalloc
revisions remain unverified. Their included notices are pinned upstream
reference texts, not proof of exact source correspondence. The complete source
archives and patch for the LGPL-covered libfuse version are included. The version
uncertainty for the other runtime libraries remains a provenance limitation;
this inventory is not a completed legal review or certification.

Source references and versions for Ubuntu libraries are recorded in
`binary-provenance.json`. For Ubuntu source retrieval, use the source package
and source version recorded there (for example, `apt source NAME=VERSION` in an
appropriately configured development environment). The application itself never
runs a source retrieval command, compiler, package manager, or notice downloader.
All collection happens only while building the package.
