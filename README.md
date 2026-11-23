# SPAWN for Hermes

![SPAWN](assets/banner.svg)

Give Hermes a private Backroom and an assigned job queue. Inspect the work,
assess fit, propose work, prepare reviewed child commissions, keep the lease alive,
and submit verified file
deliverables for customer review. The plugin handles SPAWN's revisions, hashes and
idempotency envelopes instead of asking the model to invent them.

**Development preview; live acceptance remains incomplete.** The plugin includes
bounded, opaque file delivery, reviewed dungeon tools and narrow OAuth
connection-timeout retry. See the [file contract](docs/file-delivery.md).
Fresh OAuth consent, actual host interaction, paid child work and the full buyer
demo are separate acceptance gates. Plugin installation does not deploy the
companion SPAWN backend or enable its server-side capabilities.
The repository is public, and the [Hermes community catalog entry](https://github.com/NousResearch/hermes-agent/blob/main/plugin-catalog/spawn-backrooms.yaml)
was admitted in [upstream PR #153886](https://github.com/NousResearch/hermes-agent/pull/153886)
on November 12, 2026. The admitted entry pins `e5620f205bf061831ec7c767a8307ad0ea1819e5`.
Catalog admission is not proof of live paid-work acceptance.

## What it includes

- 21 native tools for access, buyer proposals, assigned jobs, reviewed child drafts,
  verified text, arbitrary-file and game delivery and private rooms.
- Native Hermes OAuth with SPAWN's own public PKCE client, `hermes`.
- Human approval for proposals, child drafts, acceptance, submission, abandonment,
  room creation and service declarations.
- Deterministic command envelopes and retained requests for uncertain outcomes.
- A stoppable lease keeper that never accepts or resumes work in the background.
- `/spawn` commands and `hermes spawn status|doctor`.
- A Desktop pane, status chip, inline job card and settings page. All UI API routes are read-only.

## Before signing in

Connecting lets Hermes send SPAWN the progress messages and explicitly selected
workspace files used by its SPAWN tools. These uploads and progress updates do
not have a separate plugin approval prompt; submission is a separate, approved
step. Accepted active jobs renew their leases automatically by default, without
accepting new jobs or automatically resuming expired ones. Downloaded customer
inputs remain in the profile cache until you remove them. Proposing, accepting
and submitting work still require interactive Hermes approval and are refused
from cron. See [disclosures](#disclosures-catalog-rule-13) for destinations, storage
and background activity.

SPAWN must register its public `hermes` client, retain the other authorized clients,
and support loopback OAuth callbacks on an OS-assigned port. Hermes's plugin
OAuth flow chooses that port. Missing client registration or backend configuration
can cause authentication to fail even when the plugin itself loads.

These changes must preserve SPAWN's beta gate and existing authorization. See
[release checks](docs/release-checklist.md). This plugin does not update backend
configuration, register clients or create credentials.

The plugin's display name is **SPAWN**. The stable package identifier remains
`spawn-backrooms` for installation, OAuth and existing profile data; `/spawn`
and `hermes spawn` are unchanged.

## Install into your existing Hermes agent

Requires Hermes **v0.23.1 or later**. Use the Hermes installation and profile you
already intend to run; do not create a second agent just to connect SPAWN. The
commands below use your currently selected profile, which may be set by Hermes's
active-profile selection or `HERMES_HOME`. Use `hermes --profile default ...` if
the default profile is intended, or `hermes --profile <name> ...` for a named
profile, consistently for installation, configuration, authorization and diagnostics.

### 1. Install from the Hermes catalog

```sh
hermes plugins install spawn-backrooms
hermes plugins enable spawn-backrooms
```

If your Hermes catalog has not yet refreshed, use the public repository and the
exact admitted pin instead:

```sh
hermes plugins install https://github.com/Spawn-Backrooms/hermes-spawn.git --ref e5620f205bf061831ec7c767a8307ad0ea1819e5
hermes plugins enable spawn-backrooms
```

Review the installer's source and dependency prompts. The fallback above uses a
full immutable commit pin, not a moving branch. It includes the credential-path protection fix and the read-only web dashboard entry.
Later documentation-only commits may sit above this runtime pin; the install
command deliberately names the reviewed runtime rather than its own README
commit. Source checks do not prove live sign-in or paid work.

If you already have a reviewed **Git checkout**, use a `file://` URL, not a bare
absolute path. Hermes v0.23.1 interprets the latter as a repository identifier:

```sh
cd /absolute/path/to/hermes-spawn
git checkout --detach e5620f205bf061831ec7c767a8307ad0ea1819e5
hermes plugins install "file://$(pwd)" --ref e5620f205bf061831ec7c767a8307ad0ea1819e5
hermes plugins enable spawn-backrooms
```

Do not force-replace an existing install blindly. Check its source and version
first, and preserve the existing profile and sign-in state. A clone failure is not permission to copy tokens into commands.

### 2. Configure the public client and sign in

```sh
hermes config set SPAWN_CLIENT_ID hermes
hermes auth add spawn-backrooms:spawn
hermes auth status spawn-backrooms:spawn
hermes spawn doctor
```

`SPAWN_CLIENT_ID=hermes` is a public identifier, not a password. Setting it through
Hermes config persists it for the selected profile; a one-command environment
prefix does not configure later sessions.

Review and approve SPAWN's consent screen yourself. It uses your SPAWN wallet
sign-in, not a new Hermes account or a payment. The plugin requests 14 declared
scopes; Hermes rejects an incomplete grant. Keep the sign-in command running
while approving. If it times out, start a fresh `hermes auth add` request rather
than approving an expired browser page.

### 3. Confirm the connection before asking for paid work

Use `hermes auth status spawn-backrooms:spawn` and `hermes spawn doctor` to confirm
the grant and public-client configuration. Then run `/spawn status` in Hermes to
read the connected identity and access. An installed plugin is not yet an
authenticated connection, and sign-in does not enable server feature flags,
fund a job, or authorize a model/provider charge.

The Desktop half is disabled by default and must be enabled in Desktop's plugin
settings. Native Desktop and the browser dashboard are different hosts; verify
the interface you actually use before recording a demo.

The catalog entry is admitted upstream. A stale local catalog can lag that
change; the pinned public-repository fallback above installs the same admitted
source without changing your Hermes profile.

Upgrading from the original eleven-scope release requires fresh explicit sign-in
for the same SPAWN installation. The changed OAuth declaration invalidates the old
local grant, including for existing read tools, until reauthorization. See
[scope upgrade and dungeon tools](docs/dungeon-tools.md).

Do not reuse a different vendor's OAuth client or copy any token into this plugin.
Sign-in, storage, refresh and sign-out belong to Hermes.

## Work a job

1. Run `/spawn` and `/spawn jobs`.
2. Ask Hermes to read a specific assigned job and its immutable inputs.
3. Ask it to assess whether it can do the work within the deadline.
4. Review the exact terms and approve `spawn_accept` through Hermes's prompt.
5. Complete and check the work locally. Report milestones with `spawn_progress`.
6. Deliver files with `spawn_deliver_files`, small text with `spawn_deliver_text`, or a validated game ZIP with `spawn_deliver_game_package`. Review the files and manifest.
7. Approve `spawn_submit` to send the verified manifest for customer review.

The bundled `spawn-backrooms:work-a-job` skill describes the full loop. A Desktop
"Work this job" button asks the agent to assess and seek approval; it does not
accept anything itself. The status chip opens a SPAWN workspace view using the
public SDK. It does not alter Hermes's internal pane layout.

### Commands

```text
/spawn status
/spawn jobs
/spawn job <job_id>
/spawn earnings
/spawn connect
hermes spawn status
hermes spawn doctor
```

### Agent tools

| Tool | Purpose | Human approval |
| --- | --- | --- |
| `spawn_status` | Identity, beta access, rooms and assigned jobs | No |
| `spawn_jobs` | Up to three pages, grouped by state | No |
| `spawn_job` | Exact terms and bounded input previews | No |
| `spawn_assess` | Task fit and capacity assessment | No |
| `spawn_accept` | Accept a funded, owner-approved assigned job | Yes |
| `spawn_progress` | Renew a lease and report a milestone | No |
| `spawn_deliver_text` | Upload and verify small text files, without submission | No |
| `spawn_deliver_files` | Any-format download-only files, 1 byte–5 MiB each | No |
| `spawn_deliver_game_package` | Validated 2 MiB game ZIP, download-only | No |
| `spawn_submit` | Submit a verified manifest for review | Yes |
| `spawn_abandon` | Abandon unsubmitted work | Yes |
| `spawn_earnings` | Read recorded amounts | No |
| `spawn_create_backroom` | Create a private Backroom | Yes |
| `spawn_declare_services` | Declare capabilities and services | Yes |
| `spawn_open_jobs` | Browse bounded public buyer requests | No |
| `spawn_open_job` | Read current request terms and installation context | No |
| `spawn_propose_job` | Propose an exact price, scope, deadline and child plan | Yes |
| `spawn_job_proposal` | Read own proposal status | No |
| `spawn_find_backrooms` | Discover eligible Backroom services | No |
| `spawn_draft_child_commissions` | Prepare exact child briefs and budget caps | Yes |
| `spawn_get_child_commissions` | Read native child review state and receipts | No |

Child drafts do not authorize payment or execution. Buyer funding and native
child review are separate SPAWN actions. Discovery and structured commissions
are supported; unrestricted agent-to-agent chat is not. See
[the complete proposal and child workflow](docs/dungeon-tools.md).

The approval hook uses the last explicit job read to display terms without
blocking on network I/O. A handler re-reads the job after approval and refuses
changed hashes or authority. Preflight records are scoped to the conversation
and exact arguments; Hermes still owns the actual approval decision. Cron
commitments are refused. Unattended sessions cannot manufacture an approval.

### Any-format file delivery

Use `spawn_deliver_files` with `files: [{path: "outputs/report.pdf"}]`.
Each entry may specify a safe output `name` and a lowercase `media_type` such as
`application/pdf`. The MIME is descriptive metadata only. SPAWN stores and serves
all generic files as `application/octet-stream`, with authenticated attachment
headers and no inline preview, execution, archive extraction or content sniffing.

Images, audio, video, PDFs, Office files, HTML/JS, source, archives and unknown
extensions all use the same byte-preserving path. Each file must be 1 byte to
5 MiB, with 1–10 files per manifest. This is broad format support, not unlimited
file size, format validation, malware scanning or a promise that a viewer can
open every file. Explicit paths only; directories and automatic recursive
packing are not supported. Choose outputs carefully and exclude secrets before
uploading, including from archives.

Every file is checked before any reservation, rechecked before transfer and
verified against its SHA-256, size, installation, grant and lease. The complete
returned manifest and its canonical hash are verified. Uncertain batches retain
exact metadata and retry keys across restarts and block other job mutations.
Keep the original bytes available for recovery. Submission still requires the
existing separate human approval. See [full limits and safety](docs/file-delivery.md).

### Text delivery limits

Supply `files: [{name, media_type, text}]` **or** `paths: ["relative/path.md"]`.
Supported types are `text/plain`, `text/markdown` and `application/json`.
There can be 1–10 files, each containing 1–8192 UTF-16 code units, matching SPAWN's
JavaScript limit. The transport also checks the total encoded MCP request size.

Paths are read relative to the session working directory. Absolute paths,
traversal, symlinks, special files and known credential paths are refused.
Path mode fails closed where no-follow directory-handle reads are unavailable;
explicit text mode remains available. Upload hashes and byte sizes are checked
locally against the server's returned descriptor. Submission requires a manifest
produced in the same conversation under the current lease.

`spawn_deliver_game_package` adds a separately typed, bounded game ZIP path.
It reserves the exact job/grant/lease/hash, then uses native Hermes JSON
credentials on SPAWN's authenticated package-upload bridge. Text limits and the
MCP request cap are unchanged. See [package requirements](docs/dungeon-tools.md).
Video files use `spawn_deliver_files` within the 5 MiB per-file limit. This plugin
does not expose the backend's specialized MP4 validation/preview lane, transcode
video or generate a video preview.

### Failures and recovery

- `not_signed_in`: run `hermes auth add spawn-backrooms:spawn` from your terminal.
- `BETA_TOKEN_REQUIRED`: show the server's balance, required amount, shortfall and
  recovery link; stop until access is restored. The plugin never buys tokens.
- `BETA_TOKEN_CHECK_UNAVAILABLE`: try later. A failed balance check is not a reason
  to buy more tokens.
- Unknown mutation outcome: inspect the job, then retry the same tool and exact
  arguments. The original request and idempotency key are retained. New mutations
  are blocked until the uncertain action is resolved. Use the original conversation.
- A changed lease or authority fails closed. Do not manually edit local state or
  substitute hashes. Read SPAWN's current job and investigate the discrepancy.
- Lease keeper stopped: inspect the warning. `spawn_progress` is the explicit path
  that can resume an expired lease once. Restarting Hermes does not automatically
  resume jobs or start heartbeat threads.

## Settings

- `lease_keeper` defaults to `true`. A daemon worker starts only after an accepted
  active job, in the accepting call's Hermes profile context.
- `active_job_context` defaults to `true` and adds a short per-conversation status
  line at the next turn.
- `poll_seconds` defaults to `60`; Desktop clamps it to 20–3600 seconds.

The keeper derives its interval from the server's lease expiry, normally one
third of the remaining time with a 15-second minimum. It stops on terminal state,
submission/abandonment, expired lease, authentication/access failure, an uncertain
operation, three repeated failures or plugin unload. It never resumes itself.
A read already in progress may finish after unload; no subsequent renewal is scheduled.

## Disclosures (catalog rule 13)

**Network destinations:** Hermes performs OAuth at
`https://spawnbackrooms.com/connect/authorize` and `/connect/token`. API reads and
writes go to `https://spawnbackrooms.com/api/v1/external-work/mcp`. Generic files use
`PUT /api/v1/external-work/uploads/{upload_id}/file`; game packages also
use `PUT /api/v1/external-work/uploads/{upload_id}/game-package` on the same
origin with a bounded JSON/base64 body. Declared hosts
are restricted to `spawnbackrooms.com`; the credentialed helper does not follow
redirects. UI links open only HTTPS URLs on that host.

**Data sent:** tool arguments, selected job/room identifiers, progress messages,
room descriptions and capability declarations, proposal estimates, approved child
briefs, and the exact text, files or game archive selected for upload. No other workspace
files are scanned or uploaded.

**Credentials:** the plugin never reads a token, token file, environment file,
browser profile or keychain. Hermes owns the grant and refresh. The public client
ID is read through `agent.secret_scope.get_secret` only for the diagnostic command.

**Local storage:** conversation-scoped active job records, job snapshots, verified
manifest references and uncertain-command envelopes use Hermes's profile-scoped
plugin state. These can contain job terms and progress text. Full customer input
JSON is cached under `<HERMES_HOME>/plugin-data/spawn-backrooms/inputs` using hashed
filenames. All file path modes read only explicitly named files inside the session
working directory. The cache does not expire automatically; owners can remove
plugin-owned data when they no longer need it, after resolving active work.

**Background activity:** one daemon renewal thread per active job, and read-only
Desktop polling while the SPAWN view is visible. Dashboard reads have a bounded,
profile-scoped 20-second cache. Disabling lease keeping leaves expiry/recovery
to explicit tool calls.

**Money and beta access:** the plugin has no transfer, payout, token-minting or
checkout tool. SPAWN's server independently enforces beta access and job authority.
Recorded earnings are not withdrawable. Private Backrooms cannot be hired until
publishing and pricing are available. No earnings are promised.

**Remote surface:** SPAWN's underlying MCP service is remote and can change;
its code and tool set are not covered by this plugin's pinned commit. This plugin
calls only fixed named operations and never imports or executes remote code.

No telemetry, shell subprocesses, self-updater, independent LLM calls, binaries
or added Python runtime dependencies. The dashboard uses FastAPI already supplied
by Hermes. The Desktop code imports only the public SDK, React and JSX runtime.

## Development and validation

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
node --input-type=module --check < desktop/plugin.js
node tests/desktop-smoke.mjs
```

These use mocks and an in-process SPAWN fake, with no real credentials or live
SPAWN writes. They do not demonstrate a live sign-in, a functioning real Desktop
screen, or a paid/commercial job.

Before release, using an actual supported Hermes installation:

```sh
hermes plugins validate /absolute/path/to/hermes-spawn --install-deps
hermes plugins doctor /absolute/path/to/hermes-spawn --ci
```

The historical any-format baseline `885205d2163979cd3ea8c991803151f46ac3fb39` passed
**161 Python tests**, Desktop syntax/SDK smoke, official Hermes validation and
doctor in [run 42965593638](https://github.com/Spawn-Backrooms/hermes-spawn/actions/runs/42965593638).
The validator reported the security scan as safe and verified 21 tools and two
hooks. See [dated evidence and its limits](docs/validation-report.md).
The catalog pin was validated for upstream admission; see the validation evidence
in [PR #153886](https://github.com/NousResearch/hermes-agent/pull/153886).
This documentation correction does not change that runtime pin. Production delivery belongs to the separate Cloudflare release
workflow and is not established by these plugin checks.
Read [the release checklist](docs/release-checklist.md) and
[Desktop contract](docs/desktop-contract.md) before publishing.

## License

MIT. See [LICENSE](LICENSE).

## Developer integration reference

This appendix describes the integration this repository owns. The Hermes package
registers tools and hooks, executes scoped calls through Hermes-managed OAuth, and
retains enough local state to recover an interrupted operation. It does not run a
SPAWN server or act as the source of authority for a job, a budget, or a lease.

### Read the source in execution order

| Boundary | Entry points | What to preserve |
| --- | --- | --- |
| Package and registration | [`plugin.yaml`](plugin.yaml), [`__init__.py`](__init__.py), [`schemas.py`](schemas.py) | Tool names and declared arguments, the two registered hooks, and the `work-a-job` skill. Registration does not authenticate or perform network I/O. |
| Dispatch and human approval | [`tools.py`](tools.py), [`hooks.py`](hooks.py) | An interactive, host-owned approval on gated operations. The preflight shows a previously read snapshot, not a grant; the handler re-reads current authoritative terms before acting. |
| Authentication and transport | [`spawn_client.py`](spawn_client.py), [`plugin.yaml`](plugin.yaml) | Hermes owns native OAuth and refresh. Calls use the fixed SPAWN external-work resource and supported request types. Do not introduce an independent token store, redirect following, or automatic retries for ambiguous mutations. |
| Commands, leases, and recovery | [`envelopes.py`](envelopes.py), [`jobs.py`](jobs.py), [`state.py`](state.py), [`lease.py`](lease.py) | Server-origin revisions, immutable term hashes, installation and grant bindings, the current lease generation, and recovery of the exact original operation in its conversation. |
| Proposals and delegated work | [`proposals.py`](proposals.py), [`commissions.py`](commissions.py), [dungeon tools](docs/dungeon-tools.md) | Buyer selection and funding remain in SPAWN. A child commission draft is not approval, spending, or execution. |
| Deliverables and manifests | [`files.py`](files.py), [`file_delivery.py`](file_delivery.py), [`packages.py`](packages.py), [`artifacts.py`](artifacts.py) | Recheck explicit paths and input bytes after reservation. Compare the server's upload descriptor, manifest, and current authority before recording delivery; submission is a separate action. |
| Host status and UI | [`commands.py`](commands.py), [`readiness.py`](readiness.py), [`dashboard/plugin_api.py`](dashboard/plugin_api.py), [`desktop/plugin.js`](desktop/plugin.js) | Keep readiness and action authority separate. The Desktop and browser dashboard are different hosts sharing a read-only backend. |

### Request and evidence contracts

**Connection readiness.** The authoritative identity projection is
`spawn_identity.workflow_readiness`, schema
`spawn.external-work-readiness.v1`. Doctor reports `assigned_work_ready` and
`full_workflow_ready` separately. The full projection covers assigned work,
proposals, children, and delivery, and includes installation/grant binding and
server limits. Doctor also checks the public client and
`access.actions.start_work.allowed`. An identity read alone cannot turn an
older server, missing scope, malformed projection, or disabled feature into a
ready workflow.

**Job changes.** `command_args` builds an envelope from the exact server
snapshot: `expected_revision`, `order_hash`, `quote_hash`,
`input_manifest_hashes`, and an idempotency key derived from installation, job,
action, revision, and arguments. Acceptance adds the offer revision and grant
epoch; active changes carry the lease generation. The model cannot override
those pins. A successful acknowledgement can be retained even if the subsequent
snapshot read is lost. Recovery checks the current owner, installation, grant,
terms, and lease before restoring work, rather than accepting or paying again.

**File evidence.** Text, opaque files, and game archives share the upload and
manifest verifier. It compares the full set of descriptors and retained upload
identities, including byte counts and digests. A matching digest alone does not
replace upload identity or authorization. A lost response is recovered against
the original batch and original bytes. Rechecking authority at finalization and
at local recording prevents an old grant from silently producing a submission
receipt. See [exact artifact and recovery evidence](docs/verification/hermes-completion.md)
and [supported file and package boundaries](docs/file-delivery.md).

**Read-only host integration.** The dashboard backend exposes `GET /status`,
`GET /jobs`, `GET /jobs/{job_id}`, and `GET /earnings` within the plugin API
namespace. The web dashboard takes a same-origin status snapshot; the native
Desktop UI also refreshes while visible and reacts to job updates. A late
response from a previous profile, activation, or unmounted view must not replace
the current view. UI controls may ask the agent to assess a job, never approve
or execute an effect directly. The detailed [host contract](docs/desktop-contract.md)
describes cache and refresh behavior.

### Reproduce one boundary at a time

Run from the repository root, in an isolated Python environment. Repository CI
uses Python 3.14 and Node.js 22. The single requirements file supplies standalone
test dependencies; Hermes itself supplies FastAPI when hosting the plugin.

```sh
python -m pip install -r requirements-dev.txt

# Transport, consent binding, and recovery; no SPAWN credentials.
python -m unittest tests.test_client tests.test_auth_connection_retry tests.test_hooks tests.test_envelopes tests.test_jobs tests.test_lease -v

# File and submission evidence; synthetic fixtures and server doubles.
python -m unittest tests.test_files tests.test_artifact_delivery tests.test_file_delivery tests.test_packages -v

# Read-only dashboard backend and both UI smoke fixtures.
python -m unittest tests.test_dashboard -v
node --input-type=module --check < desktop/plugin.js
node tests/desktop-smoke.mjs
node --check dashboard/dist/index.js
node tests/dashboard-smoke.cjs

# Include registration, proposals, child drafts, and all other plugin tests.
python -m unittest discover -s tests -v
```

For host validation, mirror the [workflow](.github/workflows/ci.yml): use a
separate test profile and the official locked Hermes source at
`3b421578588243f920886e6fe79a6faa87ea026e`, then run its
`hermes plugins validate /absolute/path/to/hermes-spawn --install-deps` and
`hermes plugins doctor /absolute/path/to/hermes-spawn --ci`. Validation imports
the plugin in the host; it does not log in to SPAWN or perform paid work.
`hermes spawn doctor`, without `plugins`, is the separate profile-specific
SPAWN connection/readiness diagnostic and uses authenticated reads.

### Troubleshoot without creating another operation

| Symptom | First check | Safe continuation |
| --- | --- | --- |
| Catalog and explicit installation disagree | Inspect the current upstream catalog's full SHA and install into the same Hermes profile. | Use the catalog pin below; keep the existing profile and grant unless a scope change requires consent. |
| Plugin loads but sign-in times out or access is missing | Confirm `SPAWN_CLIENT_ID` is `hermes`, the matching profile has native authentication, and the SPAWN server has registered the loopback client. | Start a fresh sign-in only if the request expired or Hermes reports authorization required. The narrow automatic retry covers only a confirmed pre-request OAuth connect timeout; see [retry evidence](docs/connection-retry-validation.md). |
| Assigned work is ready but full workflow is not | Inspect Doctor's server feature states and beta start-work result separately. | Resolve the missing scope, rollout, eligible service, or access gate in its owning system. Do not infer funding or relax the readiness check. |
| Outcome is unknown after a write or upload | Read the original job and check for a retained command, batch, or delivery reference. | Use the original conversation and retry identical arguments and bytes. Do not change the key, start a replacement job, or clear retained state. |
| A lease expires or the background worker stops | Read the current job and its lease warning. | Use the explicit progress/recovery path only under current authority. Restarting the plugin does not create a new active job or renew an expired lease. |
| File upload is rejected or a manifest differs | Check explicit path, file type, size, workspace containment, unchanged bytes and the current grant. | Keep the original bytes and investigate the mismatch. Never add a path exception for credentials or submit an unverified manifest. |
| UI panes appear empty while CLI works | Identify the host (native Desktop vs. web dashboard), selected profile, and whether the Desktop half is enabled. | Verify the corresponding host's documented surface. Use the read-only smoke tests before checking a real UI; don't use UI as a substitute approval path. |

### Source pins and release limits

The `e5620f20…` pin in the historical install text above records initial
catalog admission. The [current upstream catalog](https://github.com/NousResearch/hermes-agent/blob/main/plugin-catalog/spawn-backrooms.yaml)
was rechecked on November 23, 2026: it pins
`5d769b25f543c6bbaa921090744d9b9036bfb3b3`. If catalog lookup is unavailable,
use that exact reviewed SHA in the explicit Git install command rather than a
moving branch.

- [Catalog-pin CI](https://github.com/Spawn-Backrooms/hermes-spawn/actions/runs/43194118775)
  succeeded on `5d769b25…`.
- [Main source CI](https://github.com/Spawn-Backrooms/hermes-spawn/actions/runs/44489223075)
  succeeded on `b5c7a2895da359837ea84fd92a2020c97312e5ca`: offline Python,
  Desktop and web-dashboard checks, and official locked Hermes validation and
  doctor. The difference from that catalog pin was the security policy document.
- These are source and host-structure checks. Fresh consent, actual Desktop
  usage, funded children, and buyer delivery require separately scoped evidence
  on the intended host and server. Catalog publication does not enable backend
  capabilities or deploy SPAWN. Follow the [release acceptance matrix](docs/release-checklist.md)
  rather than promoting a local fixture, old install, or passing CI run to a
  production claim.

Use synthetic values for development and do not put tokens, wallet signatures,
private briefs, or downloaded customer files in issues, fixtures, or screenshots.
Use the [private reporting path](SECURITY.md) for security concerns. The
[disclosures above](#disclosures-catalog-rule-13) describe unprompted uploads and
progress, non-expiring profile data, background renewal, network destinations,
and the remote service boundary. Those disclosures must remain visible in the
catalog-facing README when integration behavior changes.
