"""Small shared contracts used by HA and release workflows."""

import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime


class ManagerError(Exception):
    """An actionable error safe to show to an administrator."""


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


def fresh(value: str | None, seconds: float) -> bool:
    try:
        age = (datetime.now(UTC) - datetime.fromisoformat(value or "")).total_seconds()
        return -60 <= age <= seconds
    except ValueError, TypeError:
        return False


def version(value: str) -> tuple[int, int, int]:
    """Channels are metadata, never SemVer prerelease suffixes."""
    if not isinstance(value, str) or not re.fullmatch(
        r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", value
    ):
        raise ManagerError("Expected MAJOR.MINOR.PATCH without a channel suffix")
    return tuple(map(int, value.split(".")))


def repository(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+", value
    ):
        raise ManagerError("Expected GitHub owner/repository")
    if value.split("/")[1] in (".", ".."):
        raise ManagerError("Invalid repository")
    return value.lower()


def domain_name(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", value):
        raise ManagerError("Invalid Home Assistant integration domain")
    return value


@dataclass
class Release:
    repository: str
    release_id: int
    tag: str
    version: str
    commit: str
    asset_id: int
    sha256: str
    prerelease: bool
    immutable: bool
    html_url: str
    notes: str = ""

    def __post_init__(self) -> None:
        self.repository = repository(self.repository)

    def identity(self) -> dict:
        return {
            key: getattr(self, key)
            for key in (
                "repository",
                "release_id",
                "tag",
                "version",
                "commit",
                "asset_id",
                "sha256",
            )
        }


@dataclass
class Managed:
    repository: str
    domain: str
    name: str
    approved: bool = True
    installed: Release | None = None
    available: Release | None = None
    running_version: str | None = None
    state: str = "not_installed"
    health: str = "unknown"
    health_at: str | None = None
    health_release_id: int | None = None
    install_boot: str | None = None
    files: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    checked_at: str | None = None
    progress: int = 0
    promotion: dict | None = None
    backup_snapshot: dict | None = None
    pending: dict | None = None
    offers: list[dict] = field(default_factory=list)
    absence_confirmed: bool = False
    health_boot: str | None = None

    def __post_init__(self) -> None:
        self.repository = repository(self.repository)

    @classmethod
    def restore(cls, data: dict) -> Managed:
        data = dict(data)
        for key in ("installed", "available"):
            if data.get(key):
                data[key] = Release(**data[key])
        return cls(**data)

    def serialize(self) -> dict:
        return asdict(self)

    def status(self) -> dict:
        health = self.health if fresh(self.health_at, 7200) else "unknown"
        return {
            "updated_at": utcnow(),
            "repository": self.repository,
            "installed_version": self.installed.version if self.installed else None,
            "running_version": self.running_version,
            "state": self.state,
            "owner_confirmed": self.absence_confirmed and self.state == "not_installed",
            "health": health,
            "health_at": self.health_at,
            "health_release_id": self.health_release_id,
            "restart_pending": self.state in ("downloaded", "installed", "pending_restart"),
            "release": self.installed.identity() if self.installed else None,
        }
