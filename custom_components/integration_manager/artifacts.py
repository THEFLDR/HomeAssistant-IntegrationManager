"""Bounded, version-specific package validation and deterministic packaging."""

import json
import re
import stat
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

from .const import MAX_EXTRACTED_BYTES, MAX_FILES, MAX_PACKAGE_BYTES
from .models import ManagerError, domain_name, version


def inspect_package(data: bytes, metadata: dict) -> dict[str, bytes]:
    """Return validated relative integration files without extracting untrusted paths."""
    if len(data) > MAX_PACKAGE_BYTES or sha256(data).hexdigest() != metadata.get("sha256"):
        raise ManagerError("Package size or SHA-256 mismatch")
    domain = domain_name(metadata.get("domain", ""))
    expected_version = metadata.get("version", "")
    version(expected_version)
    root = f"custom_components/{domain}/"
    files = {}
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_FILES or sum(e.file_size for e in entries) > MAX_EXTRACTED_BYTES:
                raise ManagerError("Package exceeds extraction limits")
            for entry in entries:
                name = entry.filename
                parts = PurePosixPath(name).parts
                mode = entry.external_attr >> 16
                if (
                    "\\" in name
                    or "\x00" in name
                    or name.startswith("/")
                    or ".." in parts
                    or "." in parts
                    or not name.startswith(root)
                    or (mode and stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR))
                    or entry.flag_bits & 1
                    or PurePosixPath(name).as_posix() != name.rstrip("/")
                ):
                    raise ManagerError("Unsafe archive path, link or file type")
                if entry.is_dir():
                    continue
                relative = name[len(root) :]
                if not relative or relative in files or "__pycache__" in parts:
                    raise ManagerError("Duplicate or invalid package file")
                files[relative] = archive.read(entry)
    except (BadZipFile, RuntimeError, OSError) as err:
        raise ManagerError("Invalid or corrupt ZIP package") from err
    try:
        manifest = json.loads(files["manifest.json"])
        if manifest["domain"] != domain or manifest["version"] != expected_version:
            raise ManagerError("Manifest domain/version does not match release")
        if not isinstance(manifest.get("name"), str) or not manifest["name"].strip():
            raise ManagerError("Integration manifest must have a display name")
        if "__init__.py" not in files:
            raise ManagerError("Package has no integration entry point")
        if not isinstance(manifest.get("requirements", []), list):
            raise ManagerError("Invalid dependency declaration")
        for requirement in manifest.get("requirements", []):
            if not re.fullmatch(
                r"[A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_,.-]+\])?==[A-Za-z0-9_.+-]+", requirement
            ):
                raise ManagerError("Managed dependencies must use exact PyPI version pins")
    except (KeyError, ValueError, TypeError) as err:
        raise ManagerError("Missing or invalid integration manifest") from err
    return files


def fingerprints(files: dict[str, bytes]) -> dict[str, str]:
    return {name: sha256(data).hexdigest() for name, data in files.items()}


def tree_fingerprints(path: Path) -> dict[str, str]:
    if path.is_symlink():
        raise ManagerError("Integration directory must not be a symlink")
    result = {}
    for file in path.rglob("*"):
        if file.is_symlink():
            raise ManagerError("Integration tree contains a symlink")
        if not file.is_file() and not file.is_dir():
            raise ManagerError("Integration tree contains a special file")
        if file.is_file() and "__pycache__" not in file.parts and file.suffix != ".pyc":
            result[file.relative_to(path).as_posix()] = sha256(file.read_bytes()).hexdigest()
    return result


def build_package(source: Path, domain: str) -> tuple[bytes, dict]:
    domain_name(domain)
    manifest = json.loads((source / "manifest.json").read_text())
    version(manifest["version"])
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_symlink():
                raise ManagerError("Cannot package symlinks")
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            item = ZipInfo(f"custom_components/{domain}/{path.relative_to(source).as_posix()}")
            item.date_time = (2026, 1, 1, 0, 0, 0)
            item.external_attr = (stat.S_IFREG | 0o644) << 16
            item.compress_type = ZIP_DEFLATED
            archive.writestr(item, path.read_bytes())
    data = buffer.getvalue()
    metadata = {
        "schema_version": 1,
        "domain": domain,
        "version": manifest["version"],
        "sha256": sha256(data).hexdigest(),
        "size": len(data),
    }
    inspect_package(data, metadata)
    return data, metadata
