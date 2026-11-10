# Validation report

Local source check, November 10, 2026.

## Passed

- `python -m unittest discover -s tests -q`: **96 tests**, all passed.
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

- `hermes plugins validate . --install-deps`
- `hermes plugins doctor . --ci`
- Live native OAuth login/refresh/revocation
- Real funded TEST_USD accept/progress/deliver/submit
- Real Desktop visual/layout and interactive approval QA
- GitHub Actions CI, until the prepared workflow runs remotely

Hermes is not installed in the local build environment. The tests use a stateful
fake SPAWN service and mock host APIs, not a live account or a full Hermes runtime.
No backend deployment, production setting change, credential registration, paid
API work, catalog PR or public demo was performed. The repository must remain
private until its owner asks to change that.
