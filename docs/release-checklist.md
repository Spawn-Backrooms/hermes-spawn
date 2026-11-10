# Release checklist

This is a development preview, not a submission-ready claim.

## Local build

- [x] Native plugin, 12 tools, exact tool declarations and 2 hooks implemented.
- [x] Native OAuth manifest uses public client `hermes` without a client secret.
- [x] No credential-file reads, remote code loading or self-updater.
- [x] Deterministic pins taken from the current SPAWN job schema.
- [x] Offline tests, fake-server workflows and Desktop SDK smoke tests pass.
- [x] README includes network, file, background, state and money disclosures.
- [ ] `hermes plugins validate . --install-deps` passes on the exact release tree.
- [ ] `hermes plugins doctor . --ci` passes in a real Hermes runtime.
- [ ] Run the prepared GitHub workflow and read all security warnings.

Hermes v0.23.1's official release commit was verified as
`3b421578588243f920886e6fe79a6faa87ea026e`. The build environment has no Hermes
installation. Test coverage is offline, not a substitute for its validator.

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
- [ ] Prepare an explicitly owner-approved funded TEST_USD demo job assigned to
  the Hermes installation and an eligible beta account.

None of these operator actions is performed by the plugin. No production
configuration, OAuth registration, funds, demo data or deployed backend was
changed during the local implementation.

## End-to-end validation

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
- [ ] Publish reviewed source to the private repository. Make it public only when
  the owner separately requests that change. Do not include customer data, inputs,
  caches or private backend files.
- [ ] Confirm the remote commit and use its full 40-hex SHA.
- [ ] Pin catalog `sha`, quoted `version: "0.1.0"`, `requires_hermes: ">=0.23.1"`,
  `tier: community`. Images must use that same reviewed commit.
- [ ] Open a draft catalog PR containing only
  `plugin-catalog/spawn-backrooms.yaml`, from the owner or a major contributor.
- [ ] Include disclosures, actual validation outputs and actual screenshots.
- [ ] Record an under-90-second working demo. Approve the exact public post and
  submission details before publishing or submitting any entry form.

No catalog PR, public post, form submission or deployment is included in this
local build. See [catalog rules](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/catalog-submission).
