"""Create a verified, single-AppImage development release without replacing assets.

Runs only for this repository's trusted push/manual CI contexts. Drafts are the
default; --publish is an explicit final publication step after verification.
Only GitHub CLI and the Python standard library are required.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess


REPOSITORY = "LaLinea08/Unsloth_Monitor"
ASSET_NAME = "Unsloth-Monitor-x86_64.AppImage"


@dataclass(frozen=True)
class Release:
    sha: str
    run_id: str
    asset: Path
    digest: str
    observations: str

    @property
    def tag(self):
        return f"dev-{self.sha[:12]}-{self.run_id}"

    @property
    def title(self):
        return f"Linux development build {self.sha[:12]} ({self.run_id})"

    @property
    def notes(self):
        return f"""Download **{ASSET_NAME}** below. It is the only application file needed.
GitHub also displays automatically generated source archives; they are optional.

From your normal Linux terminal in the download directory:

```bash
chmod +x {ASSET_NAME}
./{ASSET_NAME}
```

Optional integrity check (no separate checksum download):

```bash
printf '%s  %s\\n' '{self.digest}' '{ASSET_NAME}' | sha256sum -c -
```

This is a **development prerelease**, built on Ubuntu 22.04 x86_64. Automated
tests, the extracted bundled application's terminal smoke test, and short
default/quiet resource observations passed. Normal mounted AppImage launch,
Fedora/CachyOS hardware and terminal behavior, and installed Unsloth integration
remain unverified. Loaded-model details and token metrics remain unavailable;
in-flight operation reporting depends on the installed Unsloth version. No
inference benchmark was performed.

Packaged process observations (synthetic PTY; terminal-emulator rendering excluded):

{self.observations}

The **project license remains undecided**; this release does not choose a license.
Bundled third-party notices are included inside the AppImage.

Source: [{self.sha}](https://github.com/{REPOSITORY}/commit/{self.sha})
Build and test evidence: [run {self.run_id}](https://github.com/{REPOSITORY}/actions/runs/{self.run_id})
SHA-256: `{self.digest}`
"""


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare_release(directory, environment):
    """Reject untrusted triggers and incomplete/corrupt build output before writes."""
    if (environment.get("GITHUB_REPOSITORY") != REPOSITORY
            or environment.get("GITHUB_EVENT_NAME") not in {"push", "workflow_dispatch"}
            or environment.get("GITHUB_REF") not in {
                "refs/heads/main", "refs/heads/codex/linux-prototype"}):
        raise ValueError("Releases require a trusted repository branch push or manual run")
    sha = environment.get("GITHUB_SHA", "")
    run_id = environment.get("GITHUB_RUN_ID", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or not re.fullmatch(r"[1-9][0-9]{0,19}", run_id):
        raise ValueError("Invalid source commit or workflow run ID")
    asset = directory / ASSET_NAME
    if sorted(path.name for path in directory.glob("*.AppImage")) != [ASSET_NAME]:
        raise ValueError("Expected exactly one named Linux AppImage")
    if not asset.is_file() or asset.is_symlink() or not asset.stat().st_size:
        raise ValueError("Missing or empty regular AppImage")
    digest = sha256(asset)
    if (directory / "SHA256SUMS").read_text(encoding="utf-8").strip() != f"{digest}  {ASSET_NAME}":
        raise ValueError("AppImage does not match the build checksum")
    if b"UNSLOTH" not in (directory / "terminal-smoke.txt").read_bytes().upper():
        raise ValueError("Missing packaged terminal smoke evidence")
    observations = []
    for mode in ("default", "quiet"):
        evidence = json.loads((directory / f"overhead-{mode}.json").read_text(encoding="utf-8"))
        if (evidence.get("packaged") is not True or evidence.get("clean_exit") is not True
                or evidence.get("synthetic_pty") is not True
                or evidence.get("existing_process") is not False
                or evidence.get("quiet_mode") is not (mode == "quiet")):
            raise ValueError(f"Invalid packaged {mode} resource observation")
        for name, minimum, maximum in (
            ("observed_seconds", 55, 120),
            ("warmup_seconds", 10, 30),
            ("mean_tree_rss_mib", 0.01, 100),
            ("peak_tree_rss_mib", 0.01, 150),
            ("average_cpu_percent_one_logical_cpu", 0, 0.5),
            ("peak_process_count", 1, 10),
        ):
            value = evidence.get(name)
            if (type(value) not in (int, float) or not math.isfinite(value)
                    or not minimum <= value <= maximum):
                raise ValueError(f"Packaged {mode} resource observation failed: {name}")
        observations.append(
            f"- {mode.capitalize()}: {evidence['mean_tree_rss_mib']:.2f} MiB mean tree RSS; "
            f"{evidence['average_cpu_percent_one_logical_cpu']:.3f}% of one logical CPU; "
            f"{evidence['observed_seconds']:.2f} s after "
            f"{evidence['warmup_seconds']:.0f} s warm-up; clean exit.")
    return Release(sha, run_id, asset.resolve(), digest, "\n".join(observations))


class GitHub:
    def api(self, endpoint, method="GET", payload=None, missing_ok=False):
        command = ["gh", "api", "--hostname", "github.com", "--method", method,
                   "-H", "Accept: application/vnd.github+json",
                   "-H", "X-GitHub-Api-Version: 2022-11-28", endpoint]
        if payload is not None:
            command += ["--input", "-"]
        result = subprocess.run(command, input=json.dumps(payload) if payload is not None else None,
                                capture_output=True, text=True, check=False, timeout=120)
        try:
            response = json.loads(result.stdout)
        except ValueError:
            response = None
        if result.returncode:
            if missing_ok and isinstance(response, dict) and str(response.get("status")) == "404":
                return None
            raise RuntimeError(f"GitHub API {method} {endpoint} failed; no assets were overwritten")
        if not isinstance(response, (dict, list)):
            raise RuntimeError("Unexpected GitHub API response")
        return response

    def upload(self, release):
        # Never --clobber: an existing asset must be verified or explicitly investigated.
        subprocess.run(["gh", "release", "upload", release.tag, str(release.asset),
                        "--repo", f"github.com/{REPOSITORY}"], check=True, timeout=300)


def check_metadata(remote, release):
    if (remote.get("tag_name") != release.tag
            or remote.get("target_commitish") != release.sha
            or remote.get("name") != release.title
            or remote.get("body", "").replace("\r\n", "\n") != release.notes
            or remote.get("prerelease") is not True
            or type(remote.get("draft")) is not bool
            or type(remote.get("id")) is not int):
        raise ValueError("Existing release metadata differs; refusing to modify it")


def check_asset(remote, release):
    assets = remote.get("assets", [])
    if len(assets) != 1:
        raise ValueError("Release must contain exactly one application asset")
    asset = assets[0]
    if (asset.get("name") != ASSET_NAME or asset.get("state") != "uploaded"
            or asset.get("size") != release.asset.stat().st_size
            or asset.get("digest") != f"sha256:{release.digest}"):
        raise ValueError("Remote AppImage checksum/size/state differs; refusing to overwrite it")


def check_tag(tag, release):
    if (tag is None or tag.get("object", {}).get("type") != "commit"
            or tag.get("object", {}).get("sha") != release.sha):
        raise ValueError("Tag does not point directly at the tested source commit")


def find_release(release, github):
    root = f"repos/{REPOSITORY}/releases"
    remote = github.api(f"{root}/tags/{release.tag}", missing_ok=True)
    if remote is not None:
        return remote
    # The tag endpoint documents published releases only. Authenticated listing
    # includes drafts, including one left behind by a failed upload or rerun.
    # Bound traversal rather than risk unbounded API work on an unexpected repo.
    for page in range(1, 101):
        candidates = github.api(f"{root}?per_page=100&page={page}")
        if not isinstance(candidates, list):
            raise RuntimeError("Unexpected release list response")
        for candidate in candidates:
            if candidate.get("tag_name") == release.tag:
                return candidate
        if len(candidates) < 100:
            return None
    raise RuntimeError("Release history exceeds safe lookup limit; no release was changed")


def publish_release(release, github, publish=False):
    """Resume matching drafts/reruns safely; never rewrite tags or published releases."""
    root = f"repos/{REPOSITORY}"
    tag_endpoint = f"{root}/git/ref/tags/{release.tag}"
    tag = github.api(tag_endpoint, missing_ok=True)
    if tag is not None:
        check_tag(tag, release)
    remote = find_release(release, github)
    if remote is not None:
        check_metadata(remote, release)
        if tag is None:
            raise ValueError("Existing release has no matching source tag")
    else:
        if tag is None:
            github.api(f"{root}/git/refs", "POST", {
                "ref": f"refs/tags/{release.tag}", "sha": release.sha})
        remote = github.api(f"{root}/releases", "POST", {
            "tag_name": release.tag, "target_commitish": release.sha,
            "name": release.title, "body": release.notes,
            "draft": True, "prerelease": True, "make_latest": "false",
        })
        check_metadata(remote, release)
    endpoint = f"{root}/releases/{remote['id']}"
    if not remote.get("assets"):
        if remote["draft"] is not True:
            raise ValueError("Published release has no asset; refusing to change it")
        github.upload(release)
        remote = github.api(endpoint)
        check_metadata(remote, release)
    check_asset(remote, release)
    check_tag(github.api(tag_endpoint), release)
    if remote["draft"] and publish:
        remote = github.api(f"{root}/releases/{remote['id']}", "PATCH", {
            "draft": False, "prerelease": True, "make_latest": "false"})
        check_metadata(remote, release)
        check_asset(remote, release)
        if remote["draft"]:
            raise RuntimeError("GitHub did not confirm release publication")
    return remote


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("dist"))
    parser.add_argument("--publish", action="store_true", help="Publish after all verification")
    args = parser.parse_args()
    release = prepare_release(args.directory, os.environ)
    remote = publish_release(release, GitHub(), publish=args.publish)
    state = "Draft prepared" if remote["draft"] else "Prerelease published"
    url = remote.get("html_url") or f"https://github.com/{REPOSITORY}/releases/tag/{release.tag}"
    print(f"{state}: {url}")
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as stream:
            stream.write(f"{state}: [{release.tag}]({url})\n\nOne application asset: `{ASSET_NAME}`\n")


if __name__ == "__main__":
    main()
