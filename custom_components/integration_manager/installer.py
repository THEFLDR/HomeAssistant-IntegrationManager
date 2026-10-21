"""Domain-scoped atomic file replacement, retained backup and crash recovery."""

import json
import os
import shutil
from pathlib import Path
from uuid import uuid4

from .artifacts import tree_fingerprints
from .models import ManagerError, domain_name


class Installer:
    def __init__(self, config_path: Path) -> None:
        self.components = config_path / "custom_components"
        self.work = config_path / ".storage" / "integration_manager_files"

    def paths(self, domain: str) -> tuple[Path, Path, Path]:
        domain_name(domain)
        # Disallow symlinked parents as well as integration targets.
        for path in (self.components, self.work, self.work.parent):
            if path.is_symlink():
                raise ManagerError("Symlinked installation/storage directories are not supported")
        self.components.mkdir(parents=True, exist_ok=True)
        self.work.mkdir(parents=True, exist_ok=True, mode=0o700)
        target, backup, journal = (
            self.components / domain,
            self.work / f"{domain}.backup",
            self.work / f"{domain}.json",
        )
        if target.is_symlink() or backup.is_symlink() or journal.is_symlink():
            raise ManagerError("Symlinked managed files are not supported")
        return target, backup, journal

    def install(self, domain: str, files: dict[str, bytes], managed: bool) -> None:
        target, backup, journal = self.paths(domain)
        if target.exists() and not managed:
            raise ManagerError(
                "Existing integration is not managed; explicit verified adoption is required"
            )
        if target.exists():
            tree_fingerprints(target)  # Reject pre-existing links before touching any files.
        stage = self.components / f".im-stage-{uuid4().hex}"
        stage.mkdir(mode=0o700)
        try:
            for name, data in files.items():
                path = stage / name
                if path.resolve().is_relative_to(stage.resolve()) is False:
                    raise ManagerError("Unsafe installation path")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            if backup.exists():
                shutil.rmtree(backup)
            journal.write_text(json.dumps({"operation": "install", "stage": stage.name}))
            if target.exists():
                os.replace(target, backup)
            try:
                os.replace(stage, target)
            except OSError:
                if backup.exists() and not target.exists():
                    os.replace(backup, target)
                raise
            journal.unlink()
        finally:
            if stage.exists():
                shutil.rmtree(stage)

    def uninstall(self, domain: str) -> None:
        target, backup, journal = self.paths(domain)
        if not target.exists():
            return
        tree_fingerprints(target)
        if backup.exists():
            shutil.rmtree(backup)
        journal.write_text(json.dumps({"operation": "uninstall"}))
        os.replace(target, backup)
        journal.unlink()

    def recover(self, domain: str) -> bool:
        target, backup, journal = self.paths(domain)
        if not journal.exists():
            return False
        operation = json.loads(journal.read_text())
        if operation.get("operation") == "install" and not target.exists() and backup.exists():
            os.replace(backup, target)
        stage_name = operation.get("stage", "")
        if stage_name.startswith(".im-stage-") and "/" not in stage_name and "\\" not in stage_name:
            stage = self.components / stage_name
            if stage.exists() and not stage.is_symlink():
                shutil.rmtree(stage)
        journal.unlink()
        return True

    def restore(self, domain: str) -> None:
        target, backup, _ = self.paths(domain)
        if not backup.exists():
            raise ManagerError("No retained backup exists")
        tree_fingerprints(backup)
        failed = self.components / f".im-failed-{uuid4().hex}"
        if target.exists():
            tree_fingerprints(target)
            os.replace(target, failed)
        os.replace(backup, target)
        # Keep the failed copy for manual diagnosis; never silently remove it.
