# Validation report

Local and remote source evidence, November 10–11, 2026.

## Latest validated runtime baseline: November 11, 2026

`885205d2163979cd3ea8c991803151f46ac3fb39` passed
[workflow 42965593638](https://github.com/Spawn-Backrooms/hermes-spawn/actions/runs/42965593638).
Both job step results and full logs were read back on November 11:

- Offline job `130341945862`: **161 Python tests pass**, including all five
  dashboard tests; Desktop syntax and SDK smoke pass.
- Hermes job `130341946152`: official validator and doctor pass against the
  existing locked Hermes v0.23.1 runtime
  `3b421578588243f920886e6fe79a6faa87ea026e`.
- Validator: safe security scan, public Desktop SDK surface, no core overrides,
  and exact declared registrations. Doctor: **21 tools, 2 hooks**. The manifest
  declares **14 OAuth scopes**.
- Informational isolation notes: dashboard responses are buffered through the
  plugin host; CLI subcommands are wired through the local CLI parser.
- Runner warnings concern Node action deprecation and `punycode`, not plugin
  security findings. No plugin security warning was reported.

A subsequent documentation-only revision does not inherit exact-SHA approval.
Revalidate its final public catalog pin and review warnings. The records below
are historical, not assertions that the old tool counts describe today's plugin.
None of these source checks proves a fresh 14-scope consent, real Desktop
interaction, funded child execution or completed buyer delivery. Those remain
separate acceptance evidence.



## Historical dungeon candidate: local verification

- `python -m unittest discover -s tests -q`: **137 tests**, all passed.
- Existing Desktop ESM syntax and SDK smoke checks: **passed**.
- Manifest parity: **20 registered tools, 14 declared OAuth scopes**; native
  provider remains `spawn-backrooms:spawn` and public client remains `hermes`.
- A Python-generated ZIP_STORED game fixture passed the actual TypeScript
  `inspectGamePackage` parser: root `index.html`, 3 files, 62 expanded bytes.

The 40 additional Python tests cover proposal approval, canonical economics and
text normalization, current request/installation authority, expired status reads,
retained proposal and child requests across restart/lost responses, real service
selection, accepted provider cap conversion, typed package safety, exact upload
authority, native JSON bridge and existing manifest submission.

The published dungeon code at `89c53e0d0cbae2766350b2d485d38f204622e4a6`
passed both **official Hermes validate and doctor** in the existing repository
workflow: [run 42897894544](https://github.com/Spawn-Backrooms/hermes-spawn/actions/runs/42897894544).
The workflow uses locked Hermes source `3b421578588243f920886e6fe79a6faa87ea026e`
and Python 3.14. Its offline job also passed. Both runtime steps and their exact
head SHA were read back from GitHub after completion.

Neither a `hermes` executable nor the `hermes_cli` module is installed locally.
Real native OAuth scope upgrade, Desktop interaction and the funded game remain
separate, unverified gates. The historical checks below establish the recovered
baseline only. Cloudflare remains the delivery build workflow for the coordinated
server/application release; no GitHub deployment workflow was added.

## Recovered original baseline

- `python -m unittest discover -s tests -q`: **97 tests**, all passed.
- `node tests/desktop-smoke.mjs`: registration, basic no-session rendering,
  invalid/unknown inline directives and disposal passed.
- `node --input-type=module --check < desktop/plugin.js`: ESM syntax passed.
- `python -m compileall -q .`: Python syntax passed. Generated caches are excluded
  from publication and delivery.

Python tests cover JSON/SSE transport, native auth/error mapping, no redirect
following, bounded payloads, exact immutable pins and stable keys, uncertain
mutation receipt replay, active-job ownership, UTF-16 upload limits, hash checks,
manifest scope, path traversal/symlink/credential-file refusal, lease stop behavior,
human-approval preflight binding, cron refusal, read-only dashboard/cache/profile
behavior, diagnostic access checks and registration without network side effects.

## Official Hermes runtime verification

[GitHub Actions run 42773884416](https://github.com/Spawn-Backrooms/hermes-spawn/actions/runs/42773884416)
passed on source commit `7953f81cbb693f17eb0546cc4399a147e3ed7c41`. Both jobs
succeeded: offline Python 3.14/Node checks and the real Hermes runtime checks.
Hermes was pinned to official v0.23.1 commit
`3b421578588243f920886e6fe79a6faa87ea026e` and installed from its frozen lockfile.

- `hermes plugins validate <plugin> --install-deps`: **Validation passed.**
  Manifest, OAuth clients, entrypoints, isolated registration, declared tools and
  hooks, collisions, security scan, no core overrides and Desktop surface passed.
- `hermes plugins doctor <plugin> --ci`: **OK: runtime discovery, manifest parsing,
  import, and registration passed.**

The validator reported no plugin security warnings. Its informational isolation
notes say dashboard responses are buffered through the plugin host and CLI
subcommands are wired through the local CLI parser, not the isolated host.
GitHub emitted runner-action Node deprecation warnings; these did not fail either
job and are unrelated to the plugin security scan.

These checks do not authenticate to SPAWN or exercise live account operations.

## Not run

- Live native OAuth login/refresh/revocation
- Same-installation explicit upgrade to the three new native OAuth scopes
- Real funded USDC open-job/proposal/accept/child/deliver/submit flow
- Two actual eligible Backroom results and buyer gameplay from delivered bytes
- Real Desktop visual/layout and interactive approval QA

Hermes is not installed in the local build environment; the official runtime
checks ran in GitHub Actions. Unit tests use a stateful fake SPAWN service and
mock host APIs, not a live SPAWN account.
No backend deployment, production setting change, credential registration, paid
API work, catalog PR or public demo was performed. The repository must remain
private until its owner asks to change that.

## First remote CI run

[Run 42772923991](https://github.com/Spawn-Backrooms/hermes-spawn/actions/runs/42772923991)
on `e57dea33f04d7909d833af166476d847ab583668` failed because standalone dashboard
tests had no FastAPI installed, and Hermes's minimal capability recorder has no
runtime `ctx.state` property at registration. The official v0.23.1 validator
passed the manifest, OAuth, dependency, security scan, core-override and Desktop
surface checks, but failed the registration probe. Doctor was not reached.

The published fix makes state resolution lazy and adds an explicit standalone
test dependency. A regression checks registration against a context without
runtime state. Both previously failing checks passed in predecessor run 42773361456,
and the exact recovered pin subsequently passed run 42773884416 above.
