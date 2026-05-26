# Signing YancoHub for distribution

Building `python build.py` produces an unsigned installer that works fine but
triggers Windows SmartScreen warnings for end users (because the publisher is
unknown). This file is the playbook for fixing that.

## Why SmartScreen warns

When a user downloads an `.exe`, Windows SmartScreen checks two things:

1. **Is it Authenticode-signed by a trusted publisher?**  An unsigned binary
   gets the worst treatment — a red "Windows protected your PC" dialog.
2. **Does this publisher have reputation?**  Even a signed binary from a new
   publisher gets a softer warning for a while until enough installs accrue.

The only way to eliminate the warning entirely is an **EV (Extended Validation)**
certificate — those get instant reputation. Everything else either accrues
reputation over weeks/months (OV cert, Azure Trusted Signing) or never reaches
the trust store at all (self-signed).

## Realistic options in 2026

| Path | Cost | Warning timeline | Notes |
|---|---|---|---|
| **SignPath Foundation** | Free | None (EV-grade) | OSS-only. Repo must be public + meet their reputation criteria. |
| **Azure Trusted Signing** | ~$10/mo | Days–weeks | Cloud-based, no hardware token, requires a verified business entity (LLC/Inc.). |
| **EV cert** — Sectigo / DigiCert / SSL.com | $300–700/yr | **Instant — no warnings** | USB hardware token (CA/B Forum mandate since 2023). What commercial apps use. |
| **OV cert** — same vendors | $100–300/yr | Weeks–months | Same hardware token. Same SmartScreen warnings as unsigned until reputation builds. |
| **Self-signed** | Free | Worse than unsigned | Only useful for testing the signing pipeline on your own machine. |

For a personal/indie YancoHub: **SignPath Foundation** if the repo is open
source, otherwise **Azure Trusted Signing** is the cheapest no-token path.

## Wiring a cert into `python build.py`

`sign_executable()` in `build.py` reads two environment variables:

- `YANCOHUB_SIGN_CERT` — what to sign with
- `YANCOHUB_SIGN_PASS` — password for `.pfx` files (only)

It accepts three forms:

```pwsh
# 1. PFX file on disk (Sectigo / DigiCert traditional cert, exported from token):
$env:YANCOHUB_SIGN_CERT = "C:\path\to\yancohub-codesign.pfx"
$env:YANCOHUB_SIGN_PASS = "..."   # password

# 2. The user's Windows certificate store — picks the best code-signing cert.
#    Use this with EV USB tokens (they install a cert into the store):
$env:YANCOHUB_SIGN_CERT = "store"

# 3. A specific cert by SHA1 thumbprint (precise selection from the store):
$env:YANCOHUB_SIGN_CERT = "AB12CD34EF56..."

python build.py
```

It then runs:

```
signtool sign /tr http://timestamp.digicert.com /td sha256 /fd sha256 <args> <file>
```

with a SHA-256 file digest and an **RFC 3161 timestamp** — the signature stays
valid after the cert expires, which matters for an installer that may sit on a
download mirror for years.

The signing function runs on both the inner `YancoHub.exe` and the final
`YancoHub-<version>-setup.exe`, so both get the publisher name shown in the
SmartScreen prompt.

## Verifying the signature

```pwsh
# Path to signtool from the Windows 10 SDK:
$signtool = "C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64\signtool.exe"

& $signtool verify /v /pa dist\YancoHub-1.0.0-setup.exe
& $signtool verify /v /pa dist\YancoHub\YancoHub.exe
```

Both should report `Successfully verified` with the publisher you expect, plus
a valid timestamp.

## Cloud signers (Azure Trusted Signing, SignPath)

These don't expose a regular `.pfx` to `signtool` — they have their own CLI
that wraps the signing call. Once you have one set up, you'd replace the
`signtool sign ...` invocation in `sign_executable()` with their equivalent
(typically `azuresigntool sign ...` or `signpath sign ...`) and pass your
credentials the same way through env vars. The rest of the pipeline (build →
sign inner exe → build installer → sign installer) stays identical.

## Until you have a cert

Ship the unsigned installer. Tell first users to right-click → Properties →
**Unblock** if Windows flagged the download, or to press "More info" → "Run
anyway" on the SmartScreen dialog. It's not pretty, but the installer itself
works correctly and YancoHub runs the same regardless of whether the exe is
signed.
