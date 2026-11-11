# Release checklist

## Historical installation evidence: November 11, 2026

The original installation check used plugin pin
`8876f80d4d410ba0154475b25c320d2b6c24c6a0`. Its matching local file tree passed
the official Hermes validator and plugin doctor. An existing Hermes v0.23.1
installation loaded and enabled that tree using the supported `file://` path.

The current README instead installs the later credential-path-fixed runtime
`9c4f0897ecaf9a13f7d5f333405e851ff6a6e253`. Do not transfer the earlier
installation result to that pin; record fresh install and connection evidence.

The actual `hermes config set SPAWN_CLIENT_ID hermes` command was verified in a
fresh temporary profile: it wrote the public identifier to that profile's
`.env`, and a separate `hermes config get SPAWN_CLIENT_ID` returned `hermes`.
The existing user profile was not changed by that configuration test.

These checks do **not** establish private Git access, anonymous installation,
completed native OAuth, a functioning real Desktop UI, or funded child work.
The initial OAuth attempt timed out before consent. A final catalog pin must
still be validated after adopting any later documentation or runtime changes.
The older results and checklists below retain their original source scope; they
must not be read as proof that today's live acceptance is complete.


This is a development preview, not a submission-ready claim.

## Evidence scope for the completion candidate

The completion work starts at plugin source
`885205d2163979cd3ea8c991803151f46ac3fb39`. The local acceptance/recovery and
artifact-verification results are recorded in
[completion verification](verification/hermes-completion.md). Historical native
runtime runs below qualify their exact listed commits, not this candidate.

- [x] Reproduce and repair the acknowledged acceptance and resume recovery gaps.
- [x] Verify exact manifests and retained upload identities on all delivery lanes.
- [x] Bundle the proposal, art-first, actual-source QA and delivery workflow.
- [ ] Validate and run doctor on the exact final plugin commit with the pinned Hermes runtime.
- [ ] Record the exact plugin/server source pair and configuration used by the composed driver.
- [ ] Run complete art, successful actual-source QA, reviewed receipts, buyer download and settlement qualification.

Local tests, native runtime compatibility, composed offline qualification and a
real funded buyer journey are distinct evidence. Keep their source pins and
results separate. No new GitHub CI or deployment workflow is required.

## Local build

- [x] Native plugin, 21 tools, exact tool declarations and 2 hooks implemented.
- [x] Native OAuth manifest uses public client `hermes` without a client secret.
- [x] No credential-file reads, remote code loading or self-updater.
- [x] Deterministic pins taken from the current SPAWN job schema.
- [x] Offline tests, fake-server workflows and Desktop SDK smoke tests pass.
- [x] README includes network, file, background, state and money disclosures.
- [x] `hermes plugins validate . --install-deps` passes on dungeon code `89c53e0d0cbae2766350b2d485d38f204622e4a6` in the pinned official runtime.
- [x] `hermes plugins doctor . --ci` passes for that same candidate and runtime.
- [ ] Run the coordinated delivery validation through the Cloudflare workflow.

Hermes v0.23.1's official release commit was verified as
`3b421578588243f920886e6fe79a6faa87ea026e`. Both official checks passed in
[run 42773884416](https://github.com/Spawn-Backrooms/hermes-spawn/actions/runs/42773884416)
on the recovered baseline `7953f81cbb693f17eb0546cc4399a147e3ed7c41`.
The dungeon candidate independently passed both checks in the unchanged existing
workflow, [run 42897894544](https://github.com/Spawn-Backrooms/hermes-spawn/actions/runs/42897894544).
The any-format baseline `885205d2163979cd3ea8c991803151f46ac3fb39` also passed
its existing offline and Hermes compatibility jobs in
[run 42965593638](https://github.com/Spawn-Backrooms/hermes-spawn/actions/runs/42965593638),
using the same pinned official Hermes runtime. This is baseline evidence only.
The Hermes runtime was unavailable in that historical build environment. It has
since been installed and checked locally; actual OAuth/interactive Desktop and
final catalog pin checks remain separate.

## SPAWN owner/operator prerequisites

- [ ] Register the distinct public PKCE client `hermes` with the correct name.
- [ ] Support RFC 8252 loopback callback ports for that client only, preserving
  exact host, path, query, fragment and userinfo checks.
- [ ] Verify token exchange on the actual pinned OAuth provider version.
- [ ] Add `hermes` to the authorized client list without removing current clients.
- [ ] Preserve current beta mode, wallet allowlist and all unrelated deployment
  variables. Review a non-destructive update before any deployment.
- [ ] Verify the live authorization page, resource parameter, all declared scopes,
  grant refresh/revocation and correct Hermes client label.
- [ ] Prepare an explicitly owner-approved funded USDC demo job assigned to
  the Hermes installation and an eligible beta account.

None of these operator actions is performed by the plugin. No production
configuration, OAuth registration, funds, demo data or deployed backend was
changed during the local implementation.

## End-to-end validation

- [ ] Explicitly reauthorize the same installation with the three added scopes;
  Hermes's changed native fingerprint requires fresh sign-in for this version.
- [ ] Buyer declines or revises one proposal, then approves the exact final offer.
- [ ] Stable preparation and a lost-response replay create one funded job/hold.
- [ ] Review two exact child drafts under the accepted plan; reconcile real child
  results and allocations. A draft alone is not completed work or payment.
- [ ] Deliver the typed package and clear the game from the buyer's downloaded bytes.
- [ ] Record customer acceptance and any on-chain payout as separate evidence.

- [ ] Run fresh interactive sign-in with consent; cancel once and verify recovery.
- [ ] Confirm denied/missing scopes and a revoked grant produce a safe sign-in error.
- [ ] Run doctor and confirm beta start-work denial is not reported as success.
- [ ] Review exact job terms and fit assessment.
- [ ] Decline acceptance once and verify no write occurred. Then approve.
- [ ] Observe lease renewal using server state, not only UI countdowns.
- [ ] Simulate a delayed/lost response and verify retained-key receipt replay.
- [ ] Upload Markdown/JSON, verify UTF-8 byte hash/size, finalize manifest.
- [ ] Decline submission, then approve it; inspect customer-review status.
- [ ] Verify another conversation/profile cannot submit the first one's manifest.
- [ ] Verify terminal state, plugin disable/unload, restart and three failures stop
  the keeper; no automatic resume or hidden sign-in takes place.
- [ ] Test cron and unattended gateway rejection. Test an actual supported
  interactive messaging approval route before claiming gateway support.
- [ ] Test Desktop visible/hidden views, rapid refresh, profile switch, stale
  response rejection, inline card, no active session and invalid/inaccessible ID.
- [ ] Capture three actual UI screenshots. Do not label mocks as live screenshots.

## Public release and catalog

- [x] Owner created `Spawn-Backrooms/hermes-spawn` as a private repository.
- [x] Publish reviewed source to the private repository. Make it public only when
  the owner separately requests that change. Do not include customer data, inputs,
  caches or private backend files.
- [x] Confirm the published source commit and its full 40-hex SHA.
- [ ] Re-run validation on the final catalog-pinned release commit.
- [ ] Pin catalog `sha`, quoted `version: "0.1.0"`, `requires_hermes: ">=0.23.1"`,
  `tier: community`. Images must use that same reviewed commit.
- [ ] Open a draft catalog PR containing only
  `plugin-catalog/spawn-backrooms.yaml`, from the owner or a major contributor.
- [ ] Include disclosures, actual validation outputs and actual screenshots.
- [ ] Record an under-90-second working demo. Approve the exact public post and
  submission details before publishing or submitting any entry form.

No catalog PR, public post, form submission or deployment is included in this
local build. See [catalog rules](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/catalog-submission).


## Any-format delivery candidate

- [x] Generic file path uses existing artifact-write scope and native credentials.
- [x] Explicit regular-file reads, 5 MiB bound, exact descriptors and canonical manifest verification.
- [x] Retained batch identity and retry keys survive uncertain upload/finalization outcomes.
- [x] Existing game/text lanes, human submission approval and main OAuth retry preserved.
- [ ] Record final-candidate compatibility evidence with its exact head SHA; do not reuse an older candidate result.
- [ ] Companion backend released through its existing approval and release gates.
- [ ] Real buyer upload/download hash comparison and Desktop interaction qualified.

These source checks are not live-delivery or deployment evidence.
