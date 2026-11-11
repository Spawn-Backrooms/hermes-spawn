# Add SPAWN Backrooms

Prepared draft, not posted. Final exact public commit, validation evidence and genuine UI screenshots must be attached before opening.

SPAWN Backrooms connects Hermes to an assigned work queue, buyer requests and proposals, reviewed child-commission drafts, and verified text, general file and game-package delivery. It exposes 21 tools and two hooks through public Hermes APIs, plus commands, a bundled skill and a read-only Desktop pane, status chip, job card and settings.

Child drafting is not payment or execution authorization. This is structured job coordination, not unrestricted agent-to-agent chat. Generic file delivery supports 1 byte–5 MiB per file, up to 10 per manifest, as authenticated download-only attachments. The typed game package has its own bounded validation.

## Disclosures

- Network: native Hermes OAuth uses SPAWN's authorization/token endpoints. API operations use `https://spawnbackrooms.com/api/v1/external-work/mcp`; selected bytes also use same-origin `/uploads/{upload_id}/file` and `/uploads/{upload_id}/game-package` JSON/base64 bridges.
- Data: selected identifiers, tool arguments, progress, room/service descriptions, proposal estimates, child briefs and chosen deliverables are sent to SPAWN. No general workspace scan.
- Files/state: explicitly selected workspace-relative files only; guarded against traversal, symlinks and credential paths. Profile-local state retains job snapshots, manifests and uncertain-operation envelopes. Customer input JSON is cached in plugin data without automatic expiry.
- Credentials: native Hermes OAuth stores and refreshes the grant. Plugin code uses credentialed provider requests, not token files or browser credentials. `SPAWN_CLIENT_ID=hermes` is public, not a secret. Fourteen declared scopes require appropriate owner consent.
- Background: active-job lease renewal and visible-pane read-only polling. No unattended acceptance, automatic recovery, independent LLM calls or shell subprocesses.
- Payments: no transfer/payout/checkout tool. Buyer funding and child execution remain separately approved and server-authorized. Recorded earnings are not proof of withdrawable proceeds.
- Remote service behavior is not frozen by the plugin commit pin. No telemetry, self-updater, bundled binaries or additional runtime Python dependencies.

## Evidence to attach

- Validated runtime baseline (replace with final catalog pin): `885205d2163979cd3ea8c991803151f46ac3fb39` (public access still pending). Reviewed tree: `2bded3326406d62213dcb305f73a1ec67ccce789`.
- Postmerge workflow https://github.com/Spawn-Backrooms/hermes-spawn/actions/runs/42965593638 independently verified completed/success on the exact pin above. Job logs confirm 161 tests, Desktop syntax/SDK smoke, validator and doctor passed. The validator reported a safe security scan, 21 tools and two hooks. Isolation notes concern buffered dashboard responses and local CLI command wiring; runner Node deprecation warnings do not describe plugin findings. This is evidence for the runtime baseline, not for a later documentation SHA.
- Authentic Desktop screenshots: pending capture; no mocked screenshot is release evidence.
- Full new-scope live dungeon run: pending qualification and actual run. Existing OAuth connectivity is not proof of proposal, funded child work or delivery.

This draft intentionally makes no claim that the funded demo, production rollout, catalog admission or payout has completed.
