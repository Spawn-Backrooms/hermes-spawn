# Validation report

Local source check, November 10, 2026.

## Passed

- `python -m unittest discover -s tests -q`: **97 tests**, all passed.
- `node tests/desktop-smoke.mjs`: registration, basic no-session rendering,
  invalid/unknown inline directives and disposal passed.
- `node --input-type=module --check < desktop/plugin.js`: ESM syntax passed.
- `python -m compileall -q .`: Python syntax passed. Generated caches are excluded
  from publication and delivery.

Python tests cover JSON/SSE transport, native auth/error mapping, no redirect
following, bounded payloads, exact immutable pins and stable keys, uncertain
mutation receipt replay, active-job ownership, UTF-16 upload limits, hash checks,
manifest scope, path traversal/symlink/credential-file refusal, lease stop behavior,
human-approval preflight binding, cron refusal, read-only dashboard/cache/profile
behavior, diagnostic access checks and registration without network side effects.

## Not run

- `hermes plugins doctor . --ci`
- Live native OAuth login/refresh/revocation
- Real funded TEST_USD accept/progress/deliver/submit
- Real Desktop visual/layout and interactive approval QA
- Passing GitHub Actions CI on the latest fixes

Hermes is not installed in the local build environment. The tests use a stateful
fake SPAWN service and mock host APIs, not a live account or a full Hermes runtime.
No backend deployment, production setting change, credential registration, paid
API work, catalog PR or public demo was performed. The repository must remain
private until its owner asks to change that.

## First remote CI run

[Run 42772923991](https://github.com/Spawn-Backrooms/hermes-spawn/actions/runs/42772923991)
on `e57dea33f04d7909d833af166476d847ab583668` failed because standalone dashboard
tests had no FastAPI installed, and Hermes's minimal capability recorder has no
runtime `ctx.state` property at registration. The official v0.23.1 validator
passed the manifest, OAuth, dependency, security scan, core-override and Desktop
surface checks, but failed the registration probe. Doctor was not reached.

Local fixes make state resolution lazy and add an explicit standalone test
dependency. A regression checks registration against a context without runtime
state. Those fixes require a new remote CI run before validation can be claimed.
