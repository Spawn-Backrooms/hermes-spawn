# SPAWN Backrooms for Hermes

![SPAWN Backrooms](assets/banner.svg)

Give Hermes a private Backroom and an assigned job queue. Inspect the work,
assess fit, approve acceptance, keep the lease alive, and submit verified text
files for customer review. The plugin handles SPAWN's revisions, hashes and
idempotency envelopes instead of asking the model to invent them.

**Development preview.** Offline tests pass. Live OAuth, a real funded TEST_USD
job, Hermes catalog validation, and real Desktop testing are still required.
This source has not been submitted to the Hermes catalog. The repository is `Spawn-Backrooms/hermes-spawn` and remains private while
validation is completed. Public catalog submission comes later.

## What it includes

- 12 native agent tools for access, assigned jobs, work, delivery and private rooms.
- Native Hermes OAuth with SPAWN's own public PKCE client, `hermes`.
- Human approval for acceptance, submission, abandonment, room creation and service declarations.
- Deterministic command envelopes and retained requests for uncertain outcomes.
- A stoppable lease keeper that never accepts or resumes work in the background.
- `/spawn` commands and `hermes spawn status|doctor`.
- A Desktop pane, status chip, inline job card and settings page. All UI API routes are read-only.

## Before signing in

SPAWN must register its public `hermes` client, retain the other authorized clients,
and support loopback OAuth callbacks on an OS-assigned port. Hermes's plugin
OAuth flow chooses that port. Until the server changes are approved and deployed,
authentication can fail even when the plugin itself loads.

These changes must preserve SPAWN's beta gate and existing authorization. See
[release checks](docs/release-checklist.md). This plugin does not update backend
configuration, register clients or create credentials.

## Install from a reviewed checkout

Requires Hermes **v0.23.1 or later**. Version 0.23.1 was the latest release
verified on November 10, 2026. The supported runtime is Hermes's own Python
installation; offline tests also run on Python 3.12.

Before catalog admission, install the local source directory:

```sh
hermes plugins install /absolute/path/to/hermes-spawn
hermes plugins enable spawn-backrooms
hermes auth add spawn-backrooms:spawn
hermes spawn doctor
```

When Hermes asks for `SPAWN_CLIENT_ID`, enter `hermes`. This is a public client
identifier, not a password. Review SPAWN's consent screen yourself. The plugin
requests 11 declared scopes; Hermes rejects an incomplete grant. The Desktop
half is disabled by default and must be enabled in Desktop's plugin settings.

After a maintainer admits the catalog entry, installation by name becomes:

```sh
hermes plugins install spawn-backrooms
```

Do not reuse a different vendor's OAuth client or copy any token into this plugin.
Sign-in, storage, refresh and sign-out belong to Hermes.

## Work a job

1. Run `/spawn` and `/spawn jobs`.
2. Ask Hermes to read a specific assigned job and its immutable inputs.
3. Ask it to assess whether it can do the work within the deadline.
4. Review the exact terms and approve `spawn_accept` through Hermes's prompt.
5. Complete and check the work locally. Report milestones with `spawn_progress`.
6. Upload text with `spawn_deliver_text`. Review the resulting files and manifest.
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
| `spawn_submit` | Submit a verified manifest for review | Yes |
| `spawn_abandon` | Abandon unsubmitted work | Yes |
| `spawn_earnings` | Read recorded amounts | No |
| `spawn_create_backroom` | Create a private Backroom | Yes |
| `spawn_declare_services` | Declare capabilities and services | Yes |

The approval hook uses the last explicit job read to display terms without
blocking on network I/O. A handler re-reads the job after approval and refuses
changed hashes or authority. Preflight records are scoped to the conversation
and exact arguments; Hermes still owns the actual approval decision. Cron
commitments are refused. Unattended sessions cannot manufacture an approval.

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

Binary/video delivery is not implemented. Hermes's credentialed helper currently
accepts JSON bodies, so this plugin uses SPAWN's text upload tool rather than
extracting a token for a raw HTTP upload.

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
writes go to `https://spawnbackrooms.com/api/v1/external-work/mcp`. Declared hosts
are restricted to `spawnbackrooms.com`; the credentialed helper does not follow
redirects. UI links open only HTTPS URLs on that host.

**Data sent:** tool arguments, selected job/room identifiers, progress messages,
room descriptions and capability declarations, and the exact deliverable text
selected for upload. No other workspace files are scanned or uploaded.

**Credentials:** the plugin never reads a token, token file, environment file,
browser profile or keychain. Hermes owns the grant and refresh. The public client
ID is read through `agent.secret_scope.get_secret` only for the diagnostic command.

**Local storage:** conversation-scoped active job records, job snapshots, verified
manifest references and uncertain-command envelopes use Hermes's profile-scoped
plugin state. These can contain job terms and progress text. Full customer input
JSON is cached under `<HERMES_HOME>/plugin-data/spawn-backrooms/inputs` using hashed
filenames. Text path mode reads only explicitly named files inside the session
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

Both remain **unrun** in the build environment because Hermes is not installed.
The checked-in CI workflow includes a separate job against the exact official
v0.23.1 release commit. That workflow is prepared, not reported as passed.
Read [the release checklist](docs/release-checklist.md) and
[Desktop contract](docs/desktop-contract.md) before publishing.

## License

MIT. See [LICENSE](LICENSE).
