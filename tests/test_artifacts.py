import json
import stat
from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile, ZipInfo

import pytest

from custom_components.integration_manager.artifacts import inspect_package
from custom_components.integration_manager.installer import Installer
from custom_components.integration_manager.models import ManagerError


def test_package_integrity_and_contract(bundle):
    release, metadata, data = bundle()
    files = inspect_package(data, metadata)
    assert json.loads(files["manifest.json"])["version"] == release.version
    with pytest.raises(ManagerError, match="SHA-256"):
        inspect_package(data + b"tampered", metadata)
    with pytest.raises(ManagerError, match="domain/version"):
        inspect_package(data, {**metadata, "version": "0.1.1"})


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
