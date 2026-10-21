# Security and mTLS boundary

The trust boundary is the owner, approved executable integration repositories,
trusted HA internal callers, protected workflows and the GitHub App private key.
Sandbox status is an authenticated instance assertion, not independent attestation
that arbitrary integration-specific checks are honest. Actions revalidates the
observable identity, integrity, freshness and version constraints.

HA receives Contents read, Variables write and Actions write, but no release mutation
right. Each release workflow uses its own repository-scoped `GITHUB_TOKEN` for
Contents write, and a downscoped registry read token. Do not make HA's identity
Contents-write merely to work around permission failures. CI runs untrusted PR code
without productive App secrets and only Contents read. Privileged workflows use
reviewed default-branch code. No security setting or branch rule is applied by code.

PEM keys stay in private HA storage, are not returned by panel/status endpoints and
are never committed. Tokens refresh shortly before expiry, remain in memory and are
not logged. Signed asset redirects are HTTPS and host-restricted; installation tokens
are never forwarded to the asset host. Archive sizes, domain/path containment,
symlinks, hashes and version identity are checked before installation. Backups and
HA's own storage still need filesystem/backup access protection. No encryption-at-rest
or resistance to a hostile HA administrator is claimed.

Cloudflare mTLS protects incoming clients to Sandbox. GitHub App authentication
protects outgoing HA-to-GitHub API calls. The two paths are independent. No Cloudflare
WAF exception, inbound GitHub webhook, separate GitHub mTLS client or new port is needed.
The future Cloudflare certificate-management integration remains out of scope.

## Owner-approved temporary upstream dependency exceptions

On **21 October 2026**, the owner explicitly accepted temporary exceptions for exact
stable HA 2026.10.2 pins: **Pillow 12.3.0** and **uv 0.12.23**. Fixed versions are
Pillow 13.0.0 and uv 0.13.4, incompatible with Core's current exact declarations.
The twelve explicit advisory IDs are in
[`security/dependency-exceptions.json`](../../security/dependency-exceptions.json).
Exceptions **expire on 4 November 2026** and authorize Sandbox 0.x development only.

Pillow advisories include malformed image/PDF parsing, resource exhaustion, memory
disclosure/crashes, invalid frees, and Ghostscript argument injection with potential
remote code execution. The manager does not parse downloaded images; it serves the
unchanged approved logo. Other HA components can still invoke vulnerable Pillow
paths. The uv advisory concerns a compromised CA in its vendored trust roots. Avoid
that uv bundle: use pip for documented setup, or uv's supported system/native TLS
trust configuration with a trusted system CA store. Never disable TLS validation.
These mitigations do not make the pinned packages vulnerability-free.

The audit scans every exact transitive lock pin without a second install/resolution,
reports accepted findings visibly, and rejects new IDs, different versions, skipped
dependencies and expiry. It also rejects all such exceptions when the integration
version reaches 1.0.0; they cannot be inherited into Production automatically.
No advisory is globally ignored. Recheck stable HA and its
matching fixture release, update compatible pins, regenerate the hashed lock and
remove exceptions promptly. A full pre-1.0.0 security review and live recovery tests
remain mandatory; a green 0.x CI under explicit exceptions is not that security gate.

Sources: [Pillow advisories](https://pypi.org/pypi/pillow/12.3.0/json),
[uv advisory](https://pypi.org/pypi/uv/0.12.23/json),
[PyPI Core metadata](https://pypi.org/pypi/homeassistant/2026.10.2/json).

## Complete accepted list and potential impact

All Pillow exceptions are restricted to **12.3.0**, fixed in **13.0.0**. The uv
exception is restricted to **0.12.23**, fixed in **0.13.4**. All expire on **4 November 2026**.

| Advisory | Potential impact |
| --- | --- |
| [CVE-2026-112895](https://github.com/advisories/GHSA-p4wg-p73j-c528) | PDF page/trailer recursion and CPU/memory exhaustion during append |
| [CVE-2026-112400](https://github.com/advisories/GHSA-65qm-jvmh-6pqg) | GIF rejected-size state can cause excessive memory allocation/denial of service |
| [CVE-2026-112397](https://github.com/advisories/GHSA-58r4-6rv3-gfh8) | Zero-width image morphology can crash through invalid memory access |
| [CVE-2026-112896](https://github.com/advisories/GHSA-pchr-8j38-3x4p) | TIFF re-encoding with retained malformed metadata can read out of bounds |
| [CVE-2026-112897](https://github.com/advisories/GHSA-q45j-58j2-45rg) | Short TIFF JPEG strips can expose uninitialized process memory as pixels |
| [CVE-2026-112395](https://github.com/advisories/GHSA-462x-pgg6-55fp) | TIFF tile decoding can expose out-of-bounds process memory |
| [CVE-2026-112404](https://github.com/advisories/GHSA-c6hw-5grf-ff96) | TIFF tile/RGBA paths can leak heap memory into image pixels |
| [CVE-2026-112899](https://github.com/advisories/GHSA-vx6w-vv9f-6gvg) | Scaled EPS rendering can exceed decompression-bomb resource limits |
| [CVE-2026-112402](https://github.com/advisories/GHSA-7mwm-ghpf-9vrm) | Affine transform allocation failure can double-free memory and crash |
| [CVE-2026-112900](https://github.com/advisories/GHSA-w889-685w-c8fh) | EPS filename injection into Ghostscript arguments; potential code execution with attacker-controlled argument file |
| [CVE-2026-112893](https://github.com/advisories/GHSA-j4m9-6w36-pw47) | Stroked FreeType glyph rendering can invalid/double-free memory with malformed fonts |
| [PYSEC-2026-4321 / GHSA-hq85-5cpj-mr62](https://github.com/advisories/GHSA-hq85-5cpj-mr62) | uv's vendored compromised CA trust can permit forged TLS certificates |

The three supplementary CVEs were individually verified on **21 October 2026**
against GitHub's Advisory Database API and PyPI's version-specific vulnerability
feed for `pillow/12.3.0`: `GHSA-7mwm-ghpf-9vrm` lists **<=12.3.0**,
`GHSA-w889-685w-c8fh` lists **>=2.6.0,<13.0.0**, and
`GHSA-j4m9-6w36-pw47` lists **>=10.0.0,<13.0.0**. Each range includes 12.3.0;
each advisory identifies 13.0.0 as the first patched version. These are verified
dependency exposures even though the manager does not directly invoke those paths.
