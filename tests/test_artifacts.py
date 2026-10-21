import json
import os
import stat
from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile, ZipInfo

import pytest

from custom_components.integration_manager.artifacts import inspect_package, tree_fingerprints
from custom_components.integration_manager.installer import Installer
from custom_components.integration_manager.models import ManagerError


def test_failed_replacement_retains_target_and_existing_backup(tmp_path, monkeypatch):
    installer = Installer(tmp_path)
    installer.install("demo", {"__init__.py": b"A"}, False)
    installer.install("demo", {"__init__.py": b"B"}, True)
    replace = os.replace

    def fail_stage(source, destination):
        if source.name.startswith(".im-stage-"):
            raise OSError("simulated replacement failure")
        return replace(source, destination)

    monkeypatch.setattr(os, "replace", fail_stage)
    with pytest.raises(OSError, match="replacement failure"):
        installer.install("demo", {"__init__.py": b"C"}, True)
    assert (installer.components / "demo/__init__.py").read_bytes() == b"B"
    assert (installer.work / "demo.backup/__init__.py").read_bytes() == b"A"


def test_failed_restore_rolls_back_the_first_rename(tmp_path, monkeypatch):
    installer = Installer(tmp_path)
    installer.install("demo", {"__init__.py": b"A"}, False)
    installer.install("demo", {"__init__.py": b"B"}, True)
    target, backup, journal = installer.paths("demo")
    replace = os.replace

    def fail_backup(source, destination):
        if source == backup:
            raise OSError("simulated restore failure")
        return replace(source, destination)

    monkeypatch.setattr(os, "replace", fail_backup)
    with pytest.raises(OSError, match="restore failure"):
        installer.restore("demo")
    assert (target / "__init__.py").read_bytes() == b"B"
    assert (backup / "__init__.py").read_bytes() == b"A"
    assert not journal.exists()


@pytest.mark.parametrize("committed", [False, True])
def test_restore_journal_recovers_before_and_after_commit(tmp_path, committed):
    installer = Installer(tmp_path)
    installer.install("demo", {"__init__.py": b"A"}, False)
    installer.install("demo", {"__init__.py": b"B"}, True)
    target, backup, journal = installer.paths("demo")
    failed = installer.components / ".im-failed-crash"
    journal.write_text(json.dumps({"operation": "restore", "failed": failed.name}))
    target.rename(failed)
    if committed:
        backup.rename(target)
    installer.recover("demo")
    assert (target / "__init__.py").read_bytes() == (b"A" if committed else b"B")
    assert backup.exists() is not committed
    assert not journal.exists()


@pytest.mark.parametrize("committed", [False, True])
def test_crash_recovery_preserves_the_backup_matching_the_target(tmp_path, committed):
    installer = Installer(tmp_path)
    installer.install("demo", {"__init__.py": b"A"}, False)
    installer.install("demo", {"__init__.py": b"B"}, True)
    target, backup, journal = installer.paths("demo")
    previous = installer.work / "demo.previous-crash"
    stage = installer.components / ".im-stage-crash"
    stage.mkdir()
    (stage / "__init__.py").write_bytes(b"C")
    journal.write_text(
        json.dumps({"operation": "install", "stage": stage.name, "previous_backup": previous.name})
    )
    backup.rename(previous)
    target.rename(backup)
    if committed:
        stage.rename(target)
    installer.recover("demo")
    assert (target / "__init__.py").read_bytes() == (b"C" if committed else b"B")
    assert (backup / "__init__.py").read_bytes() == (b"B" if committed else b"A")
    assert not previous.exists() and not journal.exists() and not stage.exists()


def test_package_integrity_and_contract(bundle):
    release, metadata, data = bundle()
    files = inspect_package(data, metadata)
    assert json.loads(files["manifest.json"])["version"] == release.version
    with pytest.raises(ManagerError, match="SHA-256"):
        inspect_package(data + b"tampered", metadata)
    with pytest.raises(ManagerError, match="domain/version"):
        inspect_package(data, {**metadata, "version": "0.1.1"})


def test_manual_special_files_cannot_be_adopted_or_replaced(tmp_path):
    installer = Installer(tmp_path)
    target, _, _ = installer.paths("demo")
    target.mkdir()
    os.mkfifo(target / "foreign-pipe")
    with pytest.raises(ManagerError, match="special file"):
        tree_fingerprints(target)
    with pytest.raises(ManagerError, match="special file"):
        installer.install("demo", {"__init__.py": b"replacement"}, True)
    assert (target / "foreign-pipe").exists()


@pytest.mark.parametrize(
    "name,mode",
    [
        ("../escape", stat.S_IFREG),
        ("/absolute", stat.S_IFREG),
        ("custom_components/demo/../../escape", stat.S_IFREG),
        ("custom_components/demo/link", stat.S_IFLNK),
        ("custom_components/other/__init__.py", stat.S_IFREG),
        ("custom_components/demo/back\\slash", stat.S_IFREG),
    ],
)
def test_unsafe_packages_rejected(name, mode):
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        entry = ZipInfo(name)
        entry.external_attr = (mode | 0o644) << 16
        archive.writestr(entry, b"unsafe")
    data = buffer.getvalue()
    with pytest.raises(ManagerError, match="Unsafe"):
        inspect_package(
            data, {"domain": "demo", "version": "0.1.0", "sha256": sha256(data).hexdigest()}
        )


def test_install_preserves_other_domains_and_backup(tmp_path):
    installer = Installer(tmp_path)
    unrelated = tmp_path / "custom_components/other"
    unrelated.mkdir(parents=True)
    (unrelated / "user-data").write_text("keep")
    installer.install("demo", {"__init__.py": b"old"}, False)
    with pytest.raises(ManagerError, match="not managed"):
        installer.install("demo", {"__init__.py": b"unapproved"}, False)
    installer.install("demo", {"__init__.py": b"new"}, True)
    assert (installer.work / "demo.backup/__init__.py").read_bytes() == b"old"
    installer.restore("demo")
    assert (installer.components / "demo/__init__.py").read_bytes() == b"old"
    installer.uninstall("demo")
    assert not (installer.components / "demo").exists()
    assert (unrelated / "user-data").read_text() == "keep"


def test_crash_after_old_directory_moved_is_recoverable(tmp_path):
    installer = Installer(tmp_path)
    installer.install("demo", {"__init__.py": b"old"}, False)
    target, backup, journal = installer.paths("demo")
    target.rename(backup)
    stage = installer.components / ".im-stage-test"
    stage.mkdir()
    journal.write_text(json.dumps({"operation": "install", "stage": stage.name}))
    assert installer.recover("demo")
    assert (target / "__init__.py").read_bytes() == b"old"
    assert not stage.exists()
    assert not journal.exists()


def test_symlinked_target_rejected(tmp_path):
    installer = Installer(tmp_path)
    installer.components.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    (installer.components / "demo").symlink_to(external, target_is_directory=True)
    with pytest.raises(ManagerError, match="Symlink"):
        installer.install("demo", {"x": b"x"}, True)
