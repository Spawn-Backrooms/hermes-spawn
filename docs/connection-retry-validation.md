# OAuth connection retry validation

Validated on 2026-11-10 against official Hermes Agent v0.23.1, commit
`3b421578588243f920886e6fe79a6faa87ea026e`.
The plugin baseline was `7953f81cbb693f17eb0546cc4399a147e3ed7c41`.

## Change

Retry only Hermes's exact `oauth_refresh_failed` error ending in
`the token request failed (ConnectTimeout).`, with three total attempts and
short bounded delays. In this Hermes version, that error is raised during
credential resolution, before the token request or the plugin request is sent.
Each retry re-enters Hermes after its auth-store lock has been released and
lets Hermes resolve the current grant again.

Read/write timeouts, rejected grants, permission failures, unrecognized errors,
and post-authentication transport failures are not retried. Exhausted connection
attempts retain the existing sign-in and suggest retrying status rather than
creating a new authorization. The OAuth declaration and requested scopes are
unchanged; the plugin does not handle tokens.

## Checks

- Four new regression tests cover recovery, exhaustion, ambiguous/rejected
  outcomes, and post-authentication failures. Two cases reproduced the bug
  against the baseline before the fix.
- `python -m unittest discover -s tests -v`: 101 tests passed.
- `node --input-type=module --check < desktop/plugin.js`: passed.
- `node tests/desktop-smoke.mjs`: passed.
- Native `hermes plugins validate`: passed, including the security scan and
  Desktop SDK checks.
- Independent code review found no concrete correctness or safety issues.

## Live verification

The fix was installed in an existing isolated test profile. Native
`hermes spawn doctor` exited 0 at 23:32 UTC, reporting `ok=true`,
`public_client_configured=true`, `beta_start_work_allowed=true`, and no errors.
Hermes refreshed the existing grant successfully at 23:31 UTC. No new
authorization, scope change, network-setting change, production deployment,
or job execution was performed.

The live check confirms the existing connection and diagnostic path. It does
not validate the real Desktop UI or a complete live job lifecycle. The retry
boundary tests use mocks; their safety assumptions were separately checked
against the pinned Hermes source.
