"""Exercise release failures/resumption with an in-memory GitHub; never publish."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


spec = importlib.util.spec_from_file_location(
    "publish_release", Path(__file__).resolve().parents[1] / "scripts" / "publish_release.py")
script = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = script
spec.loader.exec_module(script)


@pytest.fixture
def context():
    return {"GITHUB_REPOSITORY": script.REPOSITORY, "GITHUB_EVENT_NAME": "push",
            "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "123456"}


@pytest.fixture
def output(tmp_path):
    asset = tmp_path / script.ASSET_NAME
    asset.write_bytes(b"A synthetic package used only by release tests")
    (tmp_path / "SHA256SUMS").write_text(f"{script.sha256(asset)}  {asset.name}\n", encoding="utf-8")
    (tmp_path / "terminal-smoke.txt").write_bytes(b"UNSLOTH fixture output")
    for mode in ("default", "quiet"):
        (tmp_path / f"overhead-{mode}.json").write_text(json.dumps({
            "packaged": True, "clean_exit": True, "existing_process": False,
            "synthetic_pty": True, "quiet_mode": mode == "quiet", "observed_seconds": 59.2,
            "warmup_seconds": 10, "mean_tree_rss_mib": 22, "peak_tree_rss_mib": 23,
            "average_cpu_percent_one_logical_cpu": 0.2, "peak_process_count": 1,
        }), encoding="utf-8")
    return tmp_path


@pytest.fixture
def release(output, context):
    return script.prepare_release(output, context)


class FakeGitHub:
    def __init__(self):
        self.tag = None
        self.release = None
        self.writes = []
        self.fail_upload = False

    def api(self, endpoint, method="GET", payload=None, missing_ok=False):
        if method == "GET":
            if "/git/ref/tags/" in endpoint:
                result = self.tag
            elif "/releases?" in endpoint:
                result = [self.release] if self.release else []
            elif "/releases/tags/" in endpoint and self.release and self.release["draft"]:
                result = None  # Documented published-only tag endpoint.
            else:
                result = self.release
            assert missing_ok or result is not None
            return deepcopy(result)
        self.writes.append((method, endpoint, deepcopy(payload)))
        if endpoint.endswith("/git/refs"):
            assert self.tag is None
            self.tag = {"object": {"type": "commit", "sha": payload["sha"]}}
            return deepcopy(self.tag)
        if method == "POST" and endpoint.endswith("/releases"):
            assert self.release is None
            self.release = {**payload, "id": 1, "assets": []}
        elif method == "PATCH":
            assert self.release["draft"] is True
            assert len(self.release["assets"]) == 1
            self.release.update(payload)
        else:
            pytest.fail(f"Unexpected API operation: {method} {endpoint}")
        return deepcopy(self.release)

    def upload(self, release):
        self.writes.append(("upload", release.asset.name))
        assert self.release["draft"] is True
        assert not self.release["assets"]
        if self.fail_upload:
            raise RuntimeError("fixture upload failure")
        self.release["assets"] = [{"name": release.asset.name, "state": "uploaded",
                                   "size": release.asset.stat().st_size,
                                   "digest": f"sha256:{release.digest}"}]


def test_default_prepares_verified_draft_with_one_asset(release):
    github = FakeGitHub()
    remote = script.publish_release(release, github)
    assert remote["draft"] is True and remote["prerelease"] is True
    assert len(remote["assets"]) == 1
    assert github.tag["object"]["sha"] == release.sha
    assert [call[0] for call in github.writes] == ["POST", "POST", "upload"]


def test_publish_is_last_after_draft_upload_and_verification(release):
    github = FakeGitHub()
    remote = script.publish_release(release, github, publish=True)
    assert remote["draft"] is False and remote["prerelease"] is True
    assert [call[0] for call in github.writes] == ["POST", "POST", "upload", "PATCH"]
    assert github.writes[1][2]["draft"] is True
    assert github.writes[1][2]["target_commitish"] == release.sha


def test_completed_rerun_verifies_without_any_writes(release):
    github = FakeGitHub()
    script.publish_release(release, github, publish=True)
    github.writes.clear()
    script.publish_release(release, github, publish=True)
    assert github.writes == []


def test_draft_rerun_is_found_by_listing_without_any_writes(release):
    github = FakeGitHub()
    script.publish_release(release, github)
    github.writes.clear()
    assert script.publish_release(release, github)["draft"] is True
    assert github.writes == []


def test_existing_draft_is_found_on_later_page(release):
    calls = []

    class PaginatedGitHub:
        def api(self, endpoint, **kwargs):
            calls.append(endpoint)
            if "/tags/" in endpoint:
                return None
            if endpoint.endswith("page=1"):
                return [{"tag_name": f"unrelated-{index}"} for index in range(100)]
            return [{"tag_name": release.tag, "draft": True}]

    assert script.find_release(release, PaginatedGitHub()) == {
        "tag_name": release.tag, "draft": True}
    assert len(calls) == 3 and calls[-1].endswith("page=2")


def test_partial_upload_failure_remains_draft_then_can_resume(release):
    github = FakeGitHub()
    github.fail_upload = True
    with pytest.raises(RuntimeError, match="upload failure"):
        script.publish_release(release, github, publish=True)
    assert github.release["draft"] is True
    github.fail_upload = False
    github.writes.clear()
    assert script.publish_release(release, github, publish=True)["draft"] is False
    assert [call[0] for call in github.writes] == ["upload", "PATCH"]


@pytest.mark.parametrize("change", ["checksum", "tag"])
def test_changes_during_upload_cannot_be_published(release, change, monkeypatch):
    github = FakeGitHub()
    original_upload = github.upload

    def changed_upload(candidate):
        original_upload(candidate)
        if change == "checksum":
            github.release["assets"][0]["digest"] = "sha256:" + "0" * 64
        else:
            github.tag["object"]["sha"] = "b" * 40

    monkeypatch.setattr(github, "upload", changed_upload)
    with pytest.raises(ValueError):
        script.publish_release(release, github, publish=True)
    assert github.release["draft"] is True
    assert "PATCH" not in [call[0] for call in github.writes]


@pytest.mark.parametrize("change", ["checksum", "missing_digest", "extra_asset", "missing_asset",
                                   "notes", "target", "tag", "stable"])
def test_mismatched_published_release_is_never_changed(release, change):
    github = FakeGitHub()
    script.publish_release(release, github, publish=True)
    if change == "checksum":
        github.release["assets"][0]["digest"] = "sha256:" + "0" * 64
    elif change == "missing_digest":
        github.release["assets"][0].pop("digest")
    elif change == "extra_asset":
        github.release["assets"].append({"name": "unrelated.zip"})
    elif change == "missing_asset":
        github.release["assets"] = []
    elif change == "notes":
        github.release["body"] = "Someone else's release"
    elif change == "target":
        github.release["target_commitish"] = "b" * 40
    elif change == "tag":
        github.tag["object"]["sha"] = "b" * 40
    else:
        github.release["prerelease"] = False
    github.writes.clear()
    with pytest.raises(ValueError):
        script.publish_release(release, github, publish=True)
    assert github.writes == []


@pytest.mark.parametrize(("key", "value"), [
    ("GITHUB_EVENT_NAME", "pull_request"), ("GITHUB_EVENT_NAME", "pull_request_target"),
    ("GITHUB_REPOSITORY", "attacker/fork"), ("GITHUB_REF", "refs/heads/untrusted"),
    ("GITHUB_REF", "refs/tags/v1"), ("GITHUB_SHA", "main"),
    ("GITHUB_RUN_ID", "1; echo unsafe"),
])
def test_untrusted_or_injected_ci_context_rejected_before_release(output, context, key, value):
    context[key] = value
    with pytest.raises(ValueError):
        script.prepare_release(output, context)


def test_checksum_and_multiple_packages_rejected(output, context):
    (output / script.ASSET_NAME).write_bytes(b"changed after build")
    with pytest.raises(ValueError, match="checksum"):
        script.prepare_release(output, context)
    (output / "other.AppImage").write_bytes(b"another platform")
    with pytest.raises(ValueError, match="exactly one"):
        script.prepare_release(output, context)


@pytest.mark.parametrize(("key", "value"), [
    ("packaged", False), ("clean_exit", False), ("quiet_mode", False),
    ("mean_tree_rss_mib", 101), ("peak_tree_rss_mib", 151),
    ("average_cpu_percent_one_logical_cpu", 0.51), ("observed_seconds", 5),
    ("average_cpu_percent_one_logical_cpu", float("nan")),
])
def test_invalid_or_over_budget_evidence_rejected(output, context, key, value):
    path = output / "overhead-quiet.json"
    evidence = json.loads(path.read_text(encoding="utf-8"))
    evidence[key] = value
    path.write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises(ValueError):
        script.prepare_release(output, context)


def test_notes_contain_one_file_launch_checksum_provenance_and_limits(release):
    assert f"chmod +x {script.ASSET_NAME}" in release.notes
    assert release.digest in release.notes and release.sha in release.notes
    assert f"/actions/runs/{release.run_id}" in release.notes
    assert "license remains undecided" in release.notes
    assert "Fedora/CachyOS" in release.notes and "remain unverified" in release.notes
    assert "Default: 22.00 MiB" in release.notes and "Quiet: 22.00 MiB" in release.notes
    assert "0.200% of one logical CPU" in release.notes


def test_api_uses_structured_stdin_and_only_accepts_404_as_absence(monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 1, '{"status":"404"}', "")

    monkeypatch.setattr(script.subprocess, "run", run)
    github = script.GitHub()
    assert github.api("repos/example/test", "POST", {"body": "literal `command`\n"}, True) is None
    command, options = calls[0]
    assert options["input"] == json.dumps({"body": "literal `command`\n"})
    assert options.get("shell", False) is False and command[-2:] == ["--input", "-"]
    with pytest.raises(RuntimeError):
        github.api("repos/example/test")


def test_api_permission_failure_is_not_treated_as_absence(monkeypatch):
    monkeypatch.setattr(script.subprocess, "run", lambda command, **kwargs:
                        subprocess.CompletedProcess(command, 1, '{"status":"403"}', ""))
    with pytest.raises(RuntimeError):
        script.GitHub().api("repos/example/test", missing_ok=True)


def test_asset_upload_never_clobbers_existing_assets(release, monkeypatch):
    calls = []
    monkeypatch.setattr(script.subprocess, "run", lambda args, **kwargs: calls.append(args))
    script.GitHub().upload(release)
    assert len(calls) == 1 and "--clobber" not in calls[0]
    assert calls[0][3:5] == [release.tag, str(release.asset)]
