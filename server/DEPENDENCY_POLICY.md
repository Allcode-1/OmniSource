# Dependency Policy

## Scope

This policy applies to Python dependencies in `server/pyproject.toml` and
`server/uv.lock`. `server/requirements.txt` is kept only as a compatibility
fallback for tools that still expect it.

## Rules

1. All runtime dependencies must be pinned to exact versions.
2. New dependencies require:
   - a clear runtime need,
   - an actively maintained upstream project,
   - a compatible license.
3. Security checks are mandatory in CI:
   - `pip-audit` for known vulnerabilities,
   - `bandit` for static security analysis.
4. Dependency updates must include test runs:
   - `uv run ruff check .`
   - `uv run pytest -q`
5. For security exceptions:
   - open a tracking issue with risk assessment,
   - define an expiration date,
   - remove the exception as soon as a fix is available.

## Cadence

1. Review dependency updates at least monthly.
2. Apply urgent security fixes as soon as they are available.

## Current Exceptions

1. `CVE-2024-23342` (`ecdsa`):
   - no fixed version is currently available in upstream advisory data,
   - tracked as temporary exception in CI via `--ignore-vuln CVE-2024-23342`,
   - must be removed immediately when a patched release appears.
