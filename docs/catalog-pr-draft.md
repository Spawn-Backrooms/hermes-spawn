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

Offline tests: **97 passed**, plus Desktop SDK smoke and syntax checks.
Hermes validate and doctor: **passed** against official v0.23.1 on source commit
`163a7c84bc039ca48b52042abc74de66e63312ba` in
[run 42773361456](https://github.com/Spawn-Backrooms/hermes-spawn/actions/runs/42773361456).
The validator reported the security scan safe. These are not live SPAWN tests.
Live OAuth + TEST_USD job: **not run yet**.
Desktop screenshots: **not captured yet**.

Re-run checks on the final catalog-pinned commit and add the live results and
real screenshots before submission. See the release checklist.
