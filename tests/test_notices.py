import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile

import pytest

spec = importlib.util.spec_from_file_location(
    "bundle_notices", Path(__file__).resolve().parents[1] / "scripts/bundle_notices.py",
)
assert spec and spec.loader
notices = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notices)


def test_cached_notice_checksum_is_verified_before_use(tmp_path):
    cached = tmp_path / "LICENSE"
    cached.write_bytes(b"altered")
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        notices.checked_download("https://unused.invalid", cached, "0" * 64)
    assert cached.read_bytes() == b"altered"
    notices.checked_download("https://unused.invalid", cached,
                             hashlib.sha256(b"altered").hexdigest())


def test_archive_notice_symlinks_are_rejected(tmp_path):
    archive = tmp_path / "source.tar"
    with tarfile.open(archive, "w") as output:
        member = tarfile.TarInfo("LICENSE")
        member.type = tarfile.SYMTYPE
        member.linkname = "../../secret"
        output.addfile(member)
    with pytest.raises(RuntimeError, match="Invalid notice"):
        notices.archive_notices(archive, ["LICENSE"], tmp_path / "output")


def test_only_requested_notice_is_written_without_archive_paths(tmp_path):
    archive = tmp_path / "source.tar"
    with tarfile.open(archive, "w") as output:
        member = tarfile.TarInfo("source/LICENSE")
        member.size = 7
        output.addfile(member, io.BytesIO(b"License"))
    notices.archive_notices(archive, ["source/LICENSE"], tmp_path / "output")
    assert (tmp_path / "output/LICENSE").read_text() == "License"
    assert not (tmp_path / "output/source").exists()


def test_missing_required_notice_fails(tmp_path):
    with pytest.raises(RuntimeError, match="Required notice"):
        notices.copy_required(tmp_path / "absent", tmp_path / "output")


def test_runtime_must_match_pinned_source_inventory(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.write_bytes(b"different runtime")
    with pytest.raises(RuntimeError, match="recorded source provenance"):
        notices.verify_runtime(runtime, "0" * 64)
    notices.verify_runtime(runtime, hashlib.sha256(b"different runtime").hexdigest())
