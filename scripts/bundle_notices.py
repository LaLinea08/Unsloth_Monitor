"""Build-time notice/source inventory for the Ubuntu-built Linux AppImage."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MAX_DOWNLOAD = 20 * 1024 * 1024


def checked_download(url: str, destination: Path, expected: str) -> None:
    """Fetch source/text only, with a pinned digest and bounded response."""
    if destination.exists():
        data = destination.read_bytes()
    else:
        request = urllib.request.Request(url, headers={"User-Agent": "Unsloth-Monitor-build"})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD or hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError(f"Source/notice size or checksum mismatch: {destination.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)


def copy_required(source: Path, destination: Path) -> None:
    if not source.is_file() or not source.stat().st_size:
        raise RuntimeError(f"Required notice is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def verify_runtime(runtime: Path, expected: str) -> None:
    if not runtime.is_file() or hashlib.sha256(runtime.read_bytes()).hexdigest() != expected:
        raise RuntimeError("AppImage runtime does not match its recorded source provenance")


def archive_notices(archive: Path, members: list[str], output: Path) -> None:
    """Read only explicitly named ordinary files; never extract archive paths."""
    with tarfile.open(archive) as source:
        for name in members:
            member = source.getmember(name)
            if not member.isfile() or not 0 < member.size < MAX_DOWNLOAD:
                raise RuntimeError(f"Invalid notice member: {name}")
            content = source.extractfile(member)
            if content is None:
                raise RuntimeError(f"Missing notice content: {name}")
            output.mkdir(parents=True, exist_ok=True)
            (output / Path(name).name).write_bytes(content.read())


def distribution_notices(name: str, output: Path) -> dict[str, str]:
    distribution = importlib.metadata.distribution(name)
    copied = 0
    for entry in distribution.files or ():
        lowered = entry.name.lower()
        if lowered.startswith(("license", "copying", "notice")):
            copy_required(Path(distribution.locate_file(entry)), output / entry.name)
            copied += 1
    if not copied:
        raise RuntimeError(f"Installed {name} has no license files")
    return {"name": name, "version": distribution.version}


def ubuntu_owner(source: Path) -> dict[str, str]:
    # dpkg records both /lib and /usr/lib forms on merged-/usr distributions.
    candidates = [str(source), str(source.resolve())]
    for candidate in list(candidates):
        if candidate.startswith("/usr/lib/"):
            candidates.append(candidate.removeprefix("/usr"))
        elif candidate.startswith("/lib/"):
            candidates.append("/usr" + candidate)
    owner = None
    for candidate in dict.fromkeys(candidates):
        result = subprocess.run(
            ["dpkg-query", "--search", candidate], capture_output=True, text=True, check=False,
        )
        if result.returncode == 0:
            first = result.stdout.splitlines()[0]
            owner = first.split(": ", 1)[0]
            break
    if not owner:
        raise RuntimeError(f"No package provenance for bundled library: {source.name}")
    fields = subprocess.check_output(
        ["dpkg-query", "--show", "--showformat=${binary:Package}\t${Version}\t"
         "${source:Package}\t${source:Version}", owner], text=True,
    ).split("\t")
    if len(fields) != 4 or any(not item for item in fields):
        raise RuntimeError(f"Incomplete package provenance: {owner}")
    return dict(zip(("package", "version", "source_package", "source_version"), fields))


def collect(appdir: Path) -> None:
    runtime = json.loads((ROOT / "packaging/third-party-runtime.json").read_text())
    runtime_path = os.environ.get("APPIMAGE_RUNTIME")
    if not runtime_path:
        raise RuntimeError("APPIMAGE_RUNTIME is required for source provenance verification")
    verify_runtime(Path(runtime_path), runtime["runtime_binary_sha256"])
    output = appdir / "usr/share/doc/unsloth-monitor"
    output.mkdir(parents=True, exist_ok=True)
    copy_required(ROOT / "packaging/THIRD-PARTY.md", output / "THIRD-PARTY.md")
    copy_required(ROOT / "LICENSE-STATUS.md", output / "LICENSE-STATUS.md")
    python_license = Path(sysconfig.get_path("stdlib")) / "LICENSE.txt"
    copy_required(python_license, output / "licenses/CPython-LICENSE.txt")
    packages = [distribution_notices(name, output / "licenses" / name)
                for name in ("PyInstaller", "pyinstaller-hooks-contrib")]
    # Copyright files may refer to these standard license texts by absolute path.
    common = Path("/usr/share/common-licenses")
    if not common.is_dir():
        raise RuntimeError("Ubuntu common license texts are missing")
    for path in common.iterdir():
        if path.is_file():
            copy_required(path, output / "licenses/common-licenses" / path.name)

    origins = json.loads((ROOT / "build/bundled-binaries.json").read_text())
    inventory = []
    base = Path(sys.base_prefix).resolve()
    for destination, original, kind in origins:
        if kind not in {"BINARY", "EXTENSION", "SYMLINK"}:
            raise RuntimeError(f"Unrecognized native payload type: {kind}")
        if kind == "SYMLINK":
            inventory.append({"file": destination, "symlink_target": original})
            continue
        source = Path(original)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        entry = {"file": destination, "sha256": digest}
        if source.resolve().is_relative_to(base) and (
            source.name.startswith("libpython") or "lib-dynload" in source.parts
        ):
            entry["origin"] = f"CPython {sys.version.split()[0]}"
            entry["source_url"] = f"https://www.python.org/downloads/release/python-{''.join(map(str, sys.version_info[:3]))}/"
        else:
            package = ubuntu_owner(source)
            name = package["package"].split(":", 1)[0]
            copy_required(Path("/usr/share/doc") / name / "copyright",
                          output / "licenses/ubuntu" / f"{name}.copyright")
            entry["origin"] = package
            entry["source_url"] = (
                f"https://launchpad.net/ubuntu/+source/{package['source_package']}/"
                f"{package['source_version']}"
            )
        inventory.append(entry)
    (output / "binary-provenance.json").write_text(json.dumps({
        "python_version": sys.version, "packaging_components": packages,
        "native_payload": inventory,
    }, indent=2) + "\n", encoding="utf-8")

    for item in runtime["files"]:
        cache = ROOT / "build/notice-cache" / item["name"]
        checked_download(item["url"], cache, item["sha256"])
        if "notices" in item:
            copy_required(cache, output / "sources" / item["name"])
            archive_notices(cache, item["notices"], output / "licenses/runtime" / item["name"])
        else:
            copy_required(cache, output / "licenses/runtime" / item["name"])
    (output / "runtime-provenance.json").write_text(
        json.dumps(runtime, indent=2) + "\n", encoding="utf-8",
    )
    print(f"Bundled third-party notices for {len(inventory)} native payload entries")
    print("Runtime Alpine package provenance remains incomplete; see THIRD-PARTY.md")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--appdir", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("Notice inventory targets the Ubuntu Linux build environment")
    collect(args.appdir)


if __name__ == "__main__":
    main()
