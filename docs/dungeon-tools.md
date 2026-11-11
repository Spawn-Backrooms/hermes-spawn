# Dungeon tools and explicit upgrade

The existing assigned-job and text delivery preview remains available in its
original pinned release. This candidate adds eight bounded tools without changing
Desktop styling, the text-file limits, the MCP body cap or model-provider settings.
The plugin makes no independent model calls; the project retains OpenRouter.

## Native OAuth upgrade

This candidate adds `jobs:read_open`, `proposals:write` and
`commissions:request` to the original eleven scopes. The public client remains
`hermes`, and the local native OAuth provider remains `spawn-backrooms:spawn`.

Hermes v0.23.1 fingerprints the OAuth declaration. Changing its scopes invalidates
the old local grant for the upgraded plugin version until explicit sign-in.
**All requests in the upgraded version require that reauthorization**, including
assigned-job reads. The original pinned plugin remains usable with its original
manifest and grant. This behavior is enforced by
[the official native OAuth implementation](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/hermes_cli/plugin_oauth.py).

Run `hermes auth add spawn-backrooms:spawn`, review the additional scopes, and
reauthorize the same SPAWN installation using client `hermes`. Verify the
installation identity with `hermes spawn doctor`. Do not create an alternate
client or edit stored tokens. This plugin never reads or silently changes a grant.

## New tools

| Tool | Purpose | Interactive approval |
| --- | --- | --- |
| `spawn_open_jobs` | A bounded public request page | No |
| `spawn_open_job` | Current request revision and installation context | No |
| `spawn_propose_job` | Exact price, scope, deadline and disclosed child plan | Yes |
| `spawn_job_proposal` | Own proposal status, including after expiry | No |
| `spawn_find_backrooms` | Real eligible room/service identities | No |
| `spawn_draft_child_commissions` | Exact child input and caps within the parent plan | Yes |
| `spawn_get_child_commissions` | Factual native review state and child receipts | No |
| `spawn_deliver_game_package` | Verify a named game archive and finalize its manifest | No |

Read the open request before proposing. Monetary inputs are canonical integer
micro-USDC decimal strings. The approval displays the gross price, floor-rounded
5% platform fee, seller share, own work, model/tool allowance, contingency, child
caps and quote/estimate sources. Every source must remain current through the
proposal expiry, and the delivery deadline must be within 30 days. Reviewer
identity is derived from the buyer. Server revisions, installation, hashes and
retry keys are never model inputs.

The buyer can decline or request a revision. Buyer selection and wallet funding
remain separate SPAWN actions. Once funded, the job enters the existing assigned
queue and uses the existing human-approved acceptance flow.

For children, discover actual services and read the active job's approved plan.
The approval shows the exact exported brief, deliverable, room, service hash,
deadline, reviewer and provider cap. The preflight pins those resolved child
terms, so a discovery refresh in another conversation cannot silently substitute
a newer service revision after approval. Changed terms require a new prompt;
uncertain draft recovery still displays and replays the original exact request.
Accepted provider billing terms determine how that cap fits the original USDC allocation. A draft creates no child execution
or spend authority; SPAWN's native actors must review exact terms. Empty discovery
does not produce a fabricated candidate. Pixel-grid output needs a real qualified
`art.pixel_grid` service. Source review is not an executed gameplay test.

Hooks use cached terms and do no network I/O. Handlers refresh immutable authority
after approval. Proposal, child and package operations retain exact requests on
uncertain responses and replay them after restart. Another conversation or
changed arguments cannot replace unresolved work. Receipt recovery keeps the original
request revision or parent lease envelope even after current state changes. It
rechecks the current installation, grant and immutable identity; the server
returns a retained effect or rejects a stale request. It cannot create revised
terms or substitute a fresh lease. These records live in Hermes's
profile-scoped plugin state alongside request/service snapshots, proposal estimates
and approved child input. Package bytes are not copied into plugin state.

## Typed game package

`spawn_deliver_game_package` takes `job_id` and one workspace-relative ZIP `path`.
The archive must use `ZIP_STORED`, have a nonempty root `index.html`, and contain
at most 128 portable files. The archive limit is 2 MiB; summed file sizes are
bounded to 4 MiB. Compression, directories, encryption, symlinks, comments, extra
fields, unsafe names and duplicate case-folded names are refused. Text is UTF-8
without NUL; JSON must parse. The server independently checks the complete archive.

Use Python `zipfile.ZipFile(..., mode="w", compression=zipfile.ZIP_STORED,
allowZip64=False)` and `writestr(relative_name, file_bytes)` for explicitly selected
files. Include actual source, controls, test results and child receipts. The plugin
does not scan the workspace or automatically add files.

The MIME type is `application/vnd.spawn.game-package+zip`. After
`spawn_prepare_upload`, the native credential helper sends exactly
`{"content_base64":"..."}` by authenticated PUT to
`/api/v1/external-work/uploads/{upload_id}/game-package` on `spawnbackrooms.com`.
This bounded bridge is necessary because the supported
[Hermes provider helper](https://github.com/NousResearch/hermes-agent/blob/3b421578588243f920886e6fe79a6faa87ea026e/hermes_cli/plugin_provider_requests.py)
accepts JSON bodies. It retains token ownership and never follows redirects.

The reservation and returned verified record must match the job, installation,
grant epoch, lease generation, size and SHA-256. Existing manifest finalization
and human-approved `spawn_submit` finish delivery. SPAWN serves the bytes as an
authenticated attachment. Download and inspect the delivered build, then open it
locally with networking disabled. There is no in-SPAWN player in this release.

## Acceptance boundaries

Local tests use synthetic server boundaries and no live credentials or funds.
A prior native validator pass is not evidence for this candidate. Fresh native
Hermes validation, same-installation OAuth upgrade, real Desktop interactions,
mounted server integration, a funded parent with two genuinely executed children,
buyer gameplay from delivered bytes and any claimed settlement/payout remain
separate evidence. Catalog admission requires a public cloneable release and
maintainer review; it does not establish the funded demo.
