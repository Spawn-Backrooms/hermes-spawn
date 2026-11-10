# Validation report

Local and remote source checks, November 10, 2026.

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

## Official Hermes runtime verification

[GitHub Actions run 42773361456](https://github.com/Spawn-Backrooms/hermes-spawn/actions/runs/42773361456)
passed on source commit `163a7c84bc039ca48b52042abc74de66e63312ba`. Both jobs
succeeded: offline Python 3.14/Node checks and the real Hermes runtime checks.
Hermes was pinned to official v0.23.1 commit
`3b421578588243f920886e6fe79a6faa87ea026e` and installed from its frozen lockfile.

- `hermes plugins validate <plugin> --install-deps`: **Validation passed.**
  Manifest, OAuth clients, entrypoints, isolated registration, declared tools and
  hooks, collisions, security scan, no core overrides and Desktop surface passed.
- `hermes plugins doctor <plugin> --ci`: **OK: runtime discovery, manifest parsing,
  import, and registration passed.**

The validator reported no plugin security warnings. Its informational isolation
notes say dashboard responses are buffered through the plugin host and CLI
subcommands are wired through the local CLI parser, not the isolated host.
GitHub emitted runner-action Node deprecation warnings; these did not fail either
job and are unrelated to the plugin security scan.

These checks do not authenticate to SPAWN or exercise live account operations.

## Not run

- Live native OAuth login/refresh/revocation
- Real funded TEST_USD accept/progress/deliver/submit
- Real Desktop visual/layout and interactive approval QA

Hermes is not installed in the local build environment; the official runtime
checks ran in GitHub Actions. Unit tests use a stateful fake SPAWN service and
mock host APIs, not a live SPAWN account.
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

The published fix makes state resolution lazy and adds an explicit standalone
test dependency. A regression checks registration against a context without
runtime state. Both previously failing checks passed in run 42773361456 above.
