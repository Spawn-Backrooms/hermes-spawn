# Add SPAWN Backrooms

Draft only. Do not submit until the exact pinned tree passes Hermes validation
and the release checklist is complete.

SPAWN Backrooms gives Hermes an assigned job queue with deterministic command
pins, lease renewal, verified text delivery and human-approved commitments.
It includes twenty agent tools, two hooks, slash and CLI commands, a bundled
skill, and a read-only Desktop pane, chip, inline job card and settings page.

## Disclosure

- Network: SPAWN OAuth at `spawnbackrooms.com/connect/authorize` and
  `/connect/token`, managed entirely by Hermes; API calls to
  `spawnbackrooms.com/api/v1/external-work/mcp`, plus the same-origin authenticated
  `/uploads/{upload_id}/game-package` JSON bridge for bounded ZIP bytes.
- Data sent: selected tool arguments, job/room IDs, progress text, room/service
  descriptions, proposal estimates, approved child briefs, and chosen text/game bytes.
- Credentials: never held or read by plugin code. Native plugin OAuth and
  `credentialed_provider_request` only; public PKCE client `hermes`.
- Local files: only explicitly named workspace-relative text or game archives are
  read. Symlinks/traversal/credential paths refused. Input JSON is cached under
  plugin data; job state and uncertain-command envelopes persist profile-locally.
- Background: active-job daemon lease renewals and visible-pane read-only polling.
  No background acceptance, resume, sign-in, shell commands or independent LLM calls.
- Money: no transfer/payout/checkout tools. Beta access and current authority stay
  server-enforced; earnings shown are recorded and non-withdrawable.
- Remote dependency: the SPAWN service/tool set is not covered by the plugin SHA.
- No telemetry, self-updater, binaries or added Python runtime dependencies.

## Verification

Offline tests: **137 passed**, plus Desktop SDK smoke and syntax checks.
Hermes validate and doctor for this new candidate: **not run**; Hermes is not
installed in this workspace. The recovered baseline pin
`7953f81cbb693f17eb0546cc4399a147e3ed7c41` passed
[run 42773884416](https://github.com/Spawn-Backrooms/hermes-spawn/actions/runs/42773884416).
That historical run does not qualify the new code.
Explicit same-installation scope upgrade + real USDC flow: **not run yet**.
Desktop screenshots: **not captured yet**.

Re-run checks on the final catalog-pinned commit and add the live results and
real screenshots before submission. See the release checklist.
