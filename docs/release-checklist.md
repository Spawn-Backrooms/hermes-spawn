# Release checklist

This is a development preview, not a submission-ready claim.

## Local build

- [x] Native plugin, 20 tools, exact tool declarations and 2 hooks implemented.
- [x] Native OAuth manifest uses public client `hermes` without a client secret.
- [x] No credential-file reads, remote code loading or self-updater.
- [x] Deterministic pins taken from the current SPAWN job schema.
- [x] Offline tests, fake-server workflows and Desktop SDK smoke tests pass.
- [x] README includes network, file, background, state and money disclosures.
- [ ] `hermes plugins validate . --install-deps` passes on the new release tree.
- [ ] `hermes plugins doctor . --ci` passes for the new release in a real runtime.
- [ ] Run the coordinated delivery validation through the Cloudflare workflow.

Hermes v0.23.1's official release commit was verified as
`3b421578588243f920886e6fe79a6faa87ea026e`. Both official checks passed in
[run 42773884416](https://github.com/Spawn-Backrooms/hermes-spawn/actions/runs/42773884416)
on the recovered baseline `7953f81cbb693f17eb0546cc4399a147e3ed7c41`.
That historical result does not qualify the new code. Current local tests pass;
the Hermes runtime is unavailable here. No new GitHub workflow was started.

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
