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
The sixteen explicit advisory IDs are in
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

| Advisory | Exact dependency | Severity | Potential impact | Verified affected range |
| --- | --- | --- | --- | --- |
| [CVE-2026-112895](https://github.com/advisories/GHSA-p4wg-p73j-c528) | pillow 12.3.0 | high | Pillow: Unbounded recursion parsing a PDF page tree or trailer chain (incomplete fix for CVE-2026-42310) | `>= 5.1.0, < 13.0.0` |
| [CVE-2026-112400](https://github.com/advisories/GHSA-65qm-jvmh-6pqg) | pillow 12.3.0 | high | Pillow: GIF seek keeps rejected size after DecompressionBombError, allowing DoS | `>= 9.2.0, < 13.0.0` |
| [CVE-2026-112397](https://github.com/advisories/GHSA-58r4-6rv3-gfh8) | pillow 12.3.0 | high | Pillow: Out-of-bounds access in _imagingmorph on a zero-width image | `<= 12.3.0` |
| [CVE-2026-112896](https://github.com/advisories/GHSA-pchr-8j38-3x4p) | pillow 12.3.0 | high | Pillow: TIFF encoder ColorMap plane-size mismatch causes a heap out-of-bounds read | `<= 12.3.0` |
| [CVE-2026-112897](https://github.com/advisories/GHSA-q45j-58j2-45rg) | pillow 12.3.0 | high | Pillow: TiffDecode returns uninitialized memory as pixels for short JPEG strips | `>= 5.3.0, < 13.0.0` |
| [CVE-2026-112395](https://github.com/advisories/GHSA-462x-pgg6-55fp) | pillow 12.3.0 | medium | Pillow tiled-TIFF decoder reads past tile buffer in copy4 (Unpack.c:1290) | `>= 8.2.0, < 13.0.0` |
| [CVE-2026-112404](https://github.com/advisories/GHSA-c6hw-5grf-ff96) | pillow 12.3.0 | high | Pillow: OOB read in TiffDecode.c tile and RGBA paths leaks heap memory into pixels | `>= 8.1.0, < 13.0.0` |
| [CVE-2026-112899](https://github.com/advisories/GHSA-vx6w-vv9f-6gvg) | pillow 12.3.0 | medium | Pillow: EPS load(scale) lets Ghostscript render past the decompression bomb limit | `>= 2.3.0, <= 12.3.0` |
| [PYSEC-2026-4321](https://github.com/advisories/GHSA-hq85-5cpj-mr62) | uv 0.12.23 | critical | uv's bundled CA store trusts an emSign root whose intermediate CA keys are compromised | `< 0.13.4` |
| [CVE-2026-112402](https://github.com/advisories/GHSA-7mwm-ghpf-9vrm) | pillow 12.3.0 | high | Pillow: Double free in ImagingScaleAffine on calloc failure via Image.transform | `<= 12.3.0` |
| [CVE-2026-112900](https://github.com/advisories/GHSA-w889-685w-c8fh) | pillow 12.3.0 | critical | Pillow: Argument Injection in Ghostscript call, potentially leading into RCE | `>= 2.6.0, < 13.0.0` |
| [CVE-2026-112893](https://github.com/advisories/GHSA-j4m9-6w36-pw47) | pillow 12.3.0 | high | Pillow: Invalid free in FreeType glyph rendering when a stroker is active | `>= 10.0.0, < 13.0.0` |
| [CVE-2026-112392](https://github.com/advisories/GHSA-27h8-gf7j-v5hc) | pillow 12.3.0 | high | Pillow: NULL dereference in ImagingExpand via rank filters on zero-size images | `<= 12.3.0` |
| [CVE-2026-112891](https://github.com/advisories/GHSA-fc9g-5qg7-mf45) | pillow 12.3.0 | medium | Pillow: Quadratic GIF comment copying during save | `>= 9.2.0, < 13.0.0` |
| [CVE-2026-112405](https://github.com/advisories/GHSA-cp9v-662q-vvx9) | pillow 12.3.0 | high | Pillow: NULL pointer dereference in Image.merge via an unvalidated band 0 | `>= 12.0.0, < 13.0.0` |
| [CVE-2026-112390](https://github.com/advisories/GHSA-22hg-r758-rrw9) | pillow 12.3.0 | high | Pillow: Infinite loop in MIC n_frames when the embedded TIFF | `>= 7.2.0, < 13.0.0` |

Every entry was individually verified on **21 October 2026** against its linked GitHub Advisory Database API record and the package/version-specific PyPI vulnerability feed. The verified affected ranges above include the exact pinned dependency; the advisory records identify the fixed versions stated above. Core’s [2026.10.2 dependency metadata](https://pypi.org/pypi/homeassistant/2026.10.2/json) independently confirms that both pins are unavoidable with the selected current stable Core. The policy JSON records each source, severity, impact, affected range, verification date and justification. These are dependency exposures even though the manager does not directly invoke the affected paths.

The owner authorized further independently verified advisories affecting exactly Pillow 12.3.0 during 0.1.0 development under this same fixed expiry and scope. This is not a runtime wildcard: each accepted advisory must be explicitly documented in the policy, and the audit continues to reject all unlisted findings. Findings for other packages or versions require separate authorization. Reassess the complete list before any Production release.
