"""GitHub App authentication and bounded outgoing HTTPS; never log response secrets."""

import asyncio
import json
import time
from datetime import datetime
from urllib.parse import urlparse

import aiohttp

from .auth import assertion
from .const import MAX_PACKAGE_BYTES, METADATA_NAME, PACKAGE_NAME
from .models import ManagerError, Release, repository, version

API = "https://api.github.com"
API_VERSION = "2026-03-10"


class GitHubError(ManagerError):
    """Safe HTTP error with endpoint and status, without response bodies or tokens."""

    def __init__(self, method: str, path: str, status: int) -> None:
        self.status = status
        super().__init__(
            f"GitHub {method} {path}: HTTP {status}; check App permissions/rate limits"
        )


class GitHubClient:
    def __init__(
        self, session: aiohttp.ClientSession, app_id: str, installation_id: str, private_key: str
    ) -> None:
        self.session = session
        self.app_id = app_id
        self.installation_id = installation_id
        self._key = private_key
        self._token: str | None = None
        self._expires = 0.0
        self._auth_lock = asyncio.Lock()
        self.permissions: dict = {}
        self._cache: dict[str, tuple[str, object]] = {}

    async def token(self) -> str:
        async with self._auth_lock:
            if self._token and time.time() < self._expires - 120:
                return self._token
            bearer = await asyncio.to_thread(assertion, self.app_id, self._key)
            result = await self._request(
                "POST",
                f"/app/installations/{self.installation_id}/access_tokens",
                bearer=bearer,
                body={
                    "permissions": {
                        "contents": "read",
                        "actions_variables": "write",
                        "actions": "write",
                    }
                },
            )
            self._token = result["token"]
            self._expires = datetime.fromisoformat(
                result["expires_at"].replace("Z", "+00:00")
            ).timestamp()
            self.permissions = result.get("permissions", {})
            return self._token

    async def _request(
        self,
        method: str,
        path: str,
        *,
        bearer: str,
        body=None,
        binary=False,
        maximum=MAX_PACKAGE_BYTES,
        cache=False,
    ):
        if not path.startswith("/") or path.startswith("//"):
            raise ManagerError("Invalid GitHub API path")
        headers = {
            "Authorization": f"Bearer {bearer}",
            "X-GitHub-Api-Version": API_VERSION,
            "Accept": "application/octet-stream" if binary else "application/vnd.github+json",
        }
        if cache and path in self._cache:
            headers["If-None-Match"] = self._cache[path][0]
        for attempt in range(3):
            try:
                async with self.session.request(
                    method,
                    API + path,
                    headers=headers,
                    json=body,
                    timeout=aiohttp.ClientTimeout(total=90),
                    allow_redirects=False,
                ) as response:
                    if response.status == 304 and cache and path in self._cache:
                        return self._cache[path][1]
                    if response.status in (301, 302, 307) and binary:
                        url = response.headers.get("Location", "")
                        parsed = urlparse(url)
                        if (
                            parsed.scheme != "https"
                            or parsed.hostname != "release-assets.githubusercontent.com"
                            or parsed.username
                            or parsed.password
                        ):
                            raise ManagerError("Rejected unexpected asset download destination")
                        return await self._download_redirect(url, maximum)
                    if response.status >= 400:
                        if (
                            method == "GET"
                            and response.status in (429, 502, 503, 504)
                            and attempt < 2
                        ):
                            await asyncio.sleep(2**attempt)
                            continue
                        raise GitHubError(method, path, response.status)
                    if response.status == 204:
                        return None
                    data = await self._bounded(response, maximum)
                    if binary:
                        return data
                    try:
                        result = json.loads(data)
                    except (ValueError, TypeError) as err:
                        raise ManagerError("GitHub returned invalid JSON") from err
                    if cache and (etag := response.headers.get("ETag")):
                        self._cache[path] = (etag, result)
                    return result
            except (aiohttp.ClientError, TimeoutError) as err:
                if method == "GET" and attempt < 2:
                    await asyncio.sleep(2**attempt)
                    continue
                raise ManagerError(f"GitHub network failure during {method} {path}") from err
        raise ManagerError("GitHub retries exhausted")

    @staticmethod
    async def _bounded(response, maximum: int) -> bytes:
        data = bytearray()
        async for chunk in response.content.iter_chunked(65536):
            data.extend(chunk)
            if len(data) > maximum:
                raise ManagerError("GitHub response exceeds size limit")
        return bytes(data)

    async def _download_redirect(self, url: str, maximum: int) -> bytes:
        # Signed asset URL is restricted above. Never forward the installation token.
        async with self.session.get(
            url, allow_redirects=False, timeout=aiohttp.ClientTimeout(total=90)
        ) as response:
            if response.status != 200:
                raise ManagerError(f"GitHub asset download: HTTP {response.status}")
            return await self._bounded(response, maximum)

    async def request(self, method: str, path: str, **kwargs):
        try:
            return await self._request(method, path, bearer=await self.token(), **kwargs)
        except GitHubError as err:
            if err.status != 401:
                raise
            self._expires = 0
            return await self._request(method, path, bearer=await self.token(), **kwargs)

    async def validate(self, registry: str) -> None:
        repository(registry)
        await self.request("GET", f"/repos/{registry}")

    async def releases(self, repo: str) -> list[dict]:
        repository(repo)
        releases = []
        for page in range(1, 11):
            result = await self.request(
                "GET", f"/repos/{repo}/releases?per_page=100&page={page}", cache=True
            )
            releases.extend(item for item in result if not item["draft"])
            if len(result) < 100:
                return releases
        raise ManagerError("Release pagination limit reached; archive obsolete release history")

    async def commit(self, repo: str, tag: str) -> str:
        result = await self.request("GET", f"/repos/{repo}/commits/{tag}")
        return result["sha"]

    async def release(self, repo: str, raw: dict) -> tuple[Release, dict]:
        repository(repo)
        ver = raw["tag_name"].removeprefix("v")
        version(ver)
        if raw.get("draft") or not raw.get("immutable") or raw["tag_name"] != f"v{ver}":
            raise ManagerError("Only published immutable vMAJOR.MINOR.PATCH releases are supported")
        assets = {a["name"]: a for a in raw["assets"]}
        if PACKAGE_NAME not in assets or METADATA_NAME not in assets:
            raise ManagerError("Release lacks integration.zip or integration.json")
        asset = assets[PACKAGE_NAME]
        metadata_asset = assets[METADATA_NAME]
        try:
            metadata = json.loads(await self.asset(repo, metadata_asset["id"], maximum=65536))
        except (ValueError, UnicodeError) as err:
            raise ManagerError("Release metadata is not valid JSON") from err
        if not isinstance(metadata, dict):
            raise ManagerError("Release metadata must be a JSON object")
        digest = asset.get("digest", "")
        if (
            not isinstance(digest, str)
            or not digest.startswith("sha256:")
            or digest != f"sha256:{metadata.get('sha256')}"
            or metadata.get("schema_version") != 1
            or metadata.get("version") != ver
            or metadata.get("size") != asset.get("size")
        ):
            raise ManagerError("Release identity, GitHub digest or package metadata mismatch")
        release = Release(
            repo,
            raw["id"],
            raw["tag_name"],
            ver,
            await self.commit(repo, raw["tag_name"]),
            asset["id"],
            metadata["sha256"],
            raw["prerelease"],
            raw["immutable"],
            raw["html_url"],
            raw.get("body") or "",
        )
        return release, metadata

    async def asset(self, repo: str, asset_id: int, *, maximum=MAX_PACKAGE_BYTES) -> bytes:
        return await self.request(
            "GET",
            f"/repos/{repository(repo)}/releases/assets/{int(asset_id)}",
            binary=True,
            maximum=maximum,
        )

    async def read_status(self, registry: str, environment: str) -> dict:
        name = f"IM_STATUS_{environment.upper()}"
        try:
            result = await self.request(
                "GET", f"/repos/{repository(registry)}/actions/variables/{name}"
            )
        except GitHubError as err:
            if err.status == 404:
                return {}
            raise
        try:
            document = json.loads(result["value"])
            if not isinstance(document, dict):
                raise ValueError("Registry document must be an object")
            return document
        except (ValueError, KeyError) as err:
            raise ManagerError(f"Invalid JSON in {name}") from err

    async def write_status(self, registry: str, environment: str, document: dict) -> None:
        from .const import MAX_VARIABLE_BYTES

        name = f"IM_STATUS_{environment.upper()}"
        value = json.dumps(document, separators=(",", ":"), sort_keys=True)
        if len(value.encode()) > MAX_VARIABLE_BYTES:
            raise ManagerError(f"{name} exceeds GitHub's 48 KB limit")
        path = f"/repos/{repository(registry)}/actions/variables"
        try:
            await self.request("PATCH", f"{path}/{name}", body={"name": name, "value": value})
        except GitHubError as err:
            if err.status != 404:
                raise
            await self.request("POST", path, body={"name": name, "value": value})

    async def dispatch(self, repo: str, workflow: str, inputs: dict) -> None:
        # The emergency override is deliberately absent from the HA API.
        if workflow != "promote.yml":
            raise ManagerError("HA may dispatch normal promotion only")
        info = await self.request("GET", f"/repos/{repository(repo)}")
        await self.request(
            "POST",
            f"/repos/{repo}/actions/workflows/{workflow}/dispatches",
            body={"ref": info["default_branch"], "inputs": inputs},
        )
