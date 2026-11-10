# Dungeon integration implementation plan

## Baseline

The recovered source is the complete 41-file tree at
`7953f81cbb693f17eb0546cc4399a147e3ed7c41`, which matched remote `main`
when recovered. All Git blob hashes and sizes were verified. Its 97 local
Python tests pass in this workspace. No `hermes` executable is installed;
the prior release's successful remote validator is evidence for that prior
release only.

## Authorized scope

Preserve the assigned-job preview while adding bounded tools for open
requests, human-approved proposals, draft child commissioning and typed
game-package delivery against the agreed SPAWN contracts. Reuse native
Hermes credentials, installation identity, exact-terms approval, retained
retry envelopes and the existing artifact manifest. The client remains
`hermes`. New scopes require an explicit native OAuth reauthorization.

There are no live paid jobs, wallet funding, production uploads, deployments,
catalog submissions or new GitHub CI runs in this local implementation.

## Sequence and verification

1. Add request discovery/detail and proposal status with bounded schemas.
   Cache immutable request revision/hash and authenticated installation.
2. Add interactive proposal approval showing exact USDC price, scope,
   deliverables, deadline, fee, seller allowance, contingency and child caps.
   Refresh immutable state after approval and retain exact proposal requests
   before sending. Verify restart and lost-response replay.
3. Add child discovery, draft commissioning and status once the canonical
   parent ledger contract is frozen. Preserve active job, installation,
   approved parent terms, revision and lease checks.
4. Add the separately typed downloadable game package using the server's
   bounded upload authority. Preserve text delivery and manifest submission.
5. Add scopes and native reauthorization guidance, update stale validation
   claims, and clearly distinguish locally verified behavior from runtime,
   Desktop, catalog and funded-demo acceptance gates.
6. Run the complete Python suite and existing Desktop checks. Review all
   changes with the coordinating agent before any push.

For every behavior change, first add an observable failing test against
the real plugin components, substituting only the external server boundary.
Record the failure, implement the smallest coherent behavior, then run the
focused tests and the complete suite. Do not count synthetic source review
as independent gameplay or fabricated assets as a Backroom child result.

## Contract decisions

- Model arguments contain the draft proposal, never request hashes,
  installation identity, server revision or retry keys.
- Money is integer micro-USDC in canonical decimal strings, converted with
  integer arithmetic only. The server remains the accounting authority.
- Approval records are not grants. They bind cached immutable terms to the
  exact model arguments and conversation; host approval controls execution.
- Unknown new server tools and missing scopes return explicit availability
  or reauthorization guidance without disabling the existing preview.

## Progress

- Baseline: all 41 source files verified; 97 Python tests pass.
- Native Hermes runtime: not available in this workspace at baseline.
- Additive implementation complete: proposals, native child drafts, typed ZIP
  upload through a dedicated bounded JSON bridge, and explicit native scopes.
- Local verification: 137 Python tests, manifest parity and existing Desktop
  syntax/smoke checks pass. Python ZIP output passes the actual server parser.
- New-release native Hermes, live OAuth/paid flow, real Desktop and catalog
  acceptance remain unverified. Baseline remote CI is historical evidence only.
