# Explicit child successors

This follow-up starts from plugin main `885205d2163979cd3ea8c991803151f46ac3fb39`
and requires the paired SPAWN child-recovery backend. It does not deploy that
backend, change OAuth scopes, grant native consent or create a second funded
parent. The source remains a private development preview.

## Operator flow

1. Read the active job with `spawn_job` and discover the exact eligible child
   services with `spawn_find_backrooms`.
2. Read the original child with `spawn_get_child_commissions`. An existing
   `attempt.successor` identifies the exact successor to recover on this or
   another device. Read that draft before considering further work.
3. For an eligible current attempt, copy its `draft_id`, `draft_hash`, `step_id`
   and `attempt.replacement.closure_hash` into an explicit `replaces` entry in
   `spawn_draft_child_commissions`. Include the successor's exact child request.
4. Review the full exported brief, service identity/hash, deliverable, reviewer,
   deadline, provider cap, predecessor, closure, prior lifetime cost and remaining
   original slot budget in the ordinary interactive approval prompt.
5. The handler refreshes canonical predecessor status, service availability and
   parent authority. Changed evidence requires renewed approval. A successful
   draft still requires fresh quote review and acceptance by SPAWN's native
   actors before allocation or execution.

Only distinct requested steps may appear in `replaces`. The server allows at
most eight attempts per approved slot. The sum of actual predecessor costs and
the successor's cap under the original billing terms must fit the original USDC
slot allocation. Provider micro-USD and commercial micro-USDC remain explicit.

## Finality is authoritative

The plugin accepts replacement eligibility only from the server's retained
attempt view. It does not infer zero spend from a missing receipt, local cache,
elapsed quote, failed HTTP request or progress label. Unknown or unsettled costs
remain blocked. A fully accepted but expired allocation proposal may still need
explicit cancellation before the server can prove safe retirement.

The backend retains all predecessor drafts, native quotes, consents, results and
economic receipts. Its closure binds that evidence and cumulative spending. A
successor cannot reuse the original native acceptance, and historical recovery
does not extend the original lease or authorize new work.

## Exact uncertain-outcome recovery

Before sending, the plugin persists the complete outgoing children, replacement
references, approval evidence and command envelope. A lost response or restart
replays that request with the original key. It never silently adds a fresh lease,
changes the predecessor or invents another successor. Pending child work must be
resolved in its original conversation with the same arguments.

The receipt must identify the exact parent, installation, requested children and
predecessor lineage. An unverified receipt remains uncertain. The immutable
server result can be read even after a newer successor exists. Initial requests
without `replaces` preserve their existing envelope identity and approval flow.

## Validation boundaries

Regression tests cover closure changes after approval, cumulative caps, unknown
finality, service revision pins, exact restart retries, invalid lineage and
cross-device discovery of an existing successor. Run `python -m unittest discover
-s tests -q` from this checkout. These tests use synthetic server responses and
do not establish a live OAuth scope upgrade, real Desktop operation, provider
execution, browser gameplay, production release or payout.
