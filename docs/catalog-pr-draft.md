# Add SPAWN Backrooms

Draft only. Do not submit until the exact pinned tree passes Hermes validation
and the release checklist is complete.

SPAWN Backrooms gives Hermes an assigned job queue with deterministic command
pins, lease renewal, verified text delivery and human-approved commitments.
It includes twelve agent tools, two hooks, slash and CLI commands, a bundled
skill, and a read-only Desktop pane, chip, inline job card and settings page.

## Disclosure

- Network: SPAWN OAuth at `spawnbackrooms.com/connect/authorize` and
  `/connect/token`, managed entirely by Hermes; API calls to
  `spawnbackrooms.com/api/v1/external-work/mcp`.
- Data sent: selected tool arguments, job/room IDs, progress text, room/service
  descriptions and chosen deliverable text.
- Credentials: never held or read by plugin code. Native plugin OAuth and
  `credentialed_provider_request` only; public PKCE client `hermes`.
- Local files: only explicitly named workspace-relative UTF-8 deliverables are
  read. Symlinks/traversal/credential paths refused. Input JSON is cached under
  plugin data; job state and uncertain-command envelopes persist profile-locally.
- Background: active-job daemon lease renewals and visible-pane read-only polling.
  No background acceptance, resume, sign-in, shell commands or independent LLM calls.
- Money: no transfer/payout/checkout tools. Beta access and current authority stay
  server-enforced; earnings shown are recorded and non-withdrawable.
- Remote dependency: the SPAWN service/tool set is not covered by the plugin SHA.
- No telemetry, self-updater, binaries or added Python runtime dependencies.

## Verification

Offline tests: see the build validation report. These are not live integration tests.
Hermes validate: **not run yet**.
Hermes doctor: **not run yet**.
Live OAuth + TEST_USD job: **not run yet**.
Desktop screenshots: **not captured yet**.

Replace this section with exact results and real screenshots before submission.
