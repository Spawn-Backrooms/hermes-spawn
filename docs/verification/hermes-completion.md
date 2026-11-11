# Hermes companion completion verification

## H01 acceptance and resume recovery

The goal is to recover acknowledged work after a lost follow-up snapshot without creating another acceptance or paid attempt.

The pending command now retains its original arguments, immutable terms, expected lease generation and acknowledgment until the originating conversation records the current active job. A new State and Jobs instance can reconcile that record through `spawn_job` or the next active operation. Recovery checks the owner, installation, grant, immutable hashes, receipt revision, execution state and expected generation. A failed check preserves the pending record.

Make Operations Idempotent led to retaining the original command across the acknowledgment window. Model the Domain led to extending the existing pending record instead of adding a second recovery table. Boundary Discipline kept current server facts authoritative. Sequence Work into Verifiable Units keeps this change separate from artifact verification. Prove It Works required reproducing both lost-read windows before the fix.

The new tests failed on the original implementation with `not_active_here` after acknowledged acceptance and `lease_changed` after acknowledged resume. The current implementation passes those tests with fresh client state instances backed by the retained store. Changed conversation, installation, grant, quote, lease and terminal execution cannot restore active work.

Run the offline checks from the repository root.

```sh
python -m unittest discover -s tests
node tests/desktop-smoke.mjs
```

H01 result on 2026-11-11 was 164 Python tests passed and the Desktop smoke check passed. This does not establish a mounted server run, live deployment, real provider work or payment.

## H02 exact artifact verification

Text, game packages and opaque files now share the exact upload and manifest verifier in `artifacts.py`. Verification covers the job, installation, grant, lease, provenance, complete descriptors, artifact identities and canonical hash. Current authority is read again before finalization and before local delivery is recorded.

Text delivery retains its original batch pins and keys across uncertainty. All three delivery paths retain each acknowledged upload identity, so a retry cannot substitute a new upload even if the server returns matching bytes. Text recovery blocks changed bytes or metadata and other parent mutations until the original batch resolves.

The two new forged-manifest regressions failed before implementation. Text raised no error and game delivery returned `ok: true` for a foreign empty manifest with a zero hash. The shared behavior matrix now rejects every tested altered manifest field through each public delivery entry point. It then restarts Jobs and State, retries the original batch, and checks identical finalization arguments and one retained upload. Separate cases check changed current grant after finalization, complete text upload authority, changed upload identity during recovery and lost text upload or finalization responses.

Boundary Discipline led to one shared verifier at the server response boundary. Make Operations Idempotent led to durable text intent and acknowledged upload identities. No new server API or delivery approval path was added.

H02 result on 2026-11-11 was 171 Python tests passed and the Desktop smoke check passed. The mounted SPAWN response check belongs to the composed cross-repository acceptance driver. These local tests use explicit offline server doubles and do not claim mounted or live acceptance.

## H08 complete bundled workflow

The shipped `work-a-job` skill now includes open brief discovery, complete proposal revision, selection and funding waits, assigned acceptance, art-first commissioning, actual-source QA from a different service, designated review waits, local playtesting, receipts, exact delivery and recovery. It explains the bounded UTF-8 export and counts every paid correction against the approved execution limit. It does not invent a plugin renewal or correction tool.

The skill-creator validator passed on the repository source. A schema check found all 17 referenced tools in `schemas.py`. The release checklist now distinguishes the verified historical baseline and its pinned Hermes run from completion-candidate qualification.

The source change follows the user's authorization to edit the bundled repository skill. It is not an installation or modification of a personal skill. Independent forward testing remains part of root review.

## H03 authoritative readiness consumption

The server contract is additive `spawn_identity.workflow_readiness` with schema
`spawn.external-work-readiness.v1`. The plugin validates installation and grant,
observation time, the four named feature states, their scope lists, and server
limits. Missing or malformed projections fail closed for full workflow readiness.

`spawn_status` exposes the validated projection. Doctor reports
`assigned_work_ready` and `full_workflow_ready` separately and retains identity,
public-client and beta-start-work diagnostics. A valid identity cannot make an
older or partially enabled server pass full collaboration readiness. These checks
use only the existing identity, access, rooms and assigned-job reads.

The seven command/status tests include old servers, disabled rollout, missing
commission scope, unavailable eligible services, malformed response fields,
foreign authority, public-client mismatch and read-only call accounting. The
full result on 2026-11-11 was 175 Python tests passed, Desktop smoke passed and
the updated skill passed the authoring validator. No live server readiness or
native sign-in outcome is implied by these offline checks.

## H01 acknowledgment boundary follow-up

A malformed acknowledgment revision is now an uncertain response that retains
the original command for exact replay. Before the guard, null/string revisions
raised `TypeError`, while boolean/stale revisions could restore active work.
The regression now rejects all four forms, retries the original arguments and
observes one server receipt. The final local suite has 176 passing Python tests;
Desktop smoke also passes.

## H02 independent-review expiry correction

Independent review found that text and game delivery retained an unusable pending
batch after a lost response followed by definitive lease or upload expiry. That
batch blocked both explicit progress/resume and abandon. Generic files already
released this local recovery state correctly.

All three delivery paths now share the same failure handler. A definitive
`LEASE_EXPIRED`, `ARTIFACT_LEASE_STALE`, `LEASE_GENERATION_STALE` or
`UPLOAD_EXPIRED` releases only that pending artifact batch and explains the next
step. It does not resume the job, abandon it, delete server bytes, submit a result
or alter a parent command. Uncertain errors, including an expiry-shaped error
marked uncertain, retain the original batch. Other definitive errors also retain
a batch that was already being recovered.

The new regressions failed before the correction: 16 text/game expiry subcases
had no release indicator, and the two text/game abandon subcases raised
`pending_outcome`. The corresponding generic-file subcases passed. The checks
now restart after both lost upload and lost finalization responses, cover all
four definitive codes, and confirm that explicit progress reaches exactly one
resume. Previously verified manifests from the old lease generation cannot be
submitted. Explicit abandon reaches the server, while unproven expiry and
unrelated retry errors still block new mutations and recover with identical
finalization arguments.

Run `python -m unittest tests.test_artifact_delivery tests.test_file_delivery
tests.test_packages -v` for the focused 34-test check. On 2026-11-11 that check,
the full 179-test Python suite, the Desktop smoke check and `git diff --check`
passed. These are offline boundary regressions using stateful server doubles;
the error classification and expiry conditions were checked against the actual
SPAWN artifact store source. Mounted-server and live qualification remain
separate.

## H06 correction allowance compatibility

The server's child-plan contract adds optional `max_correction_attempts`, an
integer from zero through three. The plugin's strict proposal schema previously
rejected that field. It now accepts the same bounded allowance and shows its
exact value in the host-owned approval prompt. The allowance stays within the
child's existing cap; each correction still requires native owner review. An
omitted allowance remains absent from the submitted proposal, preserving legacy
terms rather than inserting a new default into their hash.

The focused proposal regressions first reproduced the rejection of all four
valid explicit values. They now verify disclosure, exact submitted values,
rejection of invalid values, changed-allowance approval gating and identical
retry after a lost response and restart. The existing child parser accepts the
additive lifecycle projection without changing code. Its new output regression
preserves the requested original draft identity while exposing the current
successor ID, authority, history and budget facts. Reading those facts sends only
the parent and child status reads. No agent-facing renewal or correction tool was
added.

On 2026-11-11 the focused proposal/child suite passed 38 tests, the full Python
suite passed 183 tests, Desktop smoke passed and `git diff --check` passed. These
offline contract tests were compared with the candidate server schemas in
`open-job-contracts.ts`, `external-job-children.ts` and
`external-child-lifecycle-contracts.ts`; they are not a mounted-server run.
