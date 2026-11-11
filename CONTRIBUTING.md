# Contributing to SPAWN Backrooms for Hermes

This repository is the Hermes integration, not the SPAWN backend. Keep changes
small and independently reviewable. Read [README.md](README.md) for the current
install contract, supported hosts, capabilities and limits.

## Report an issue

For an ordinary bug or feature request, use this repository's GitHub Issues.
Include the plugin commit, Hermes version, interface (CLI, Desktop or browser
dashboard), expected behavior, actual behavior and minimal reproduction steps.
Do not assume those three interfaces support the same UI contracts.

Use synthetic inputs where possible. Do not post tokens, authorization URLs,
cookies, wallet signatures, customer files, private job briefs, full environment
dumps or unredacted logs. For a suspected security issue, do not publish exploit
details or credentials in a public issue. Check the repository Security tab for
an available private reporting route. If none is enabled, request a private
contact from a maintainer without including the sensitive details. No response
time or private-reporting endpoint is promised here.

## Develop and test

Use an isolated Python environment. The current plugin checks use Python 3.14
and Node.js 22; the README identifies the required Hermes version.

```sh
python -m venv .venv
# Activate the virtual environment using your platform's normal command.
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
node --input-type=module --check < desktop/plugin.js
node tests/desktop-smoke.mjs
```

These tests use fakes and do not authorize real SPAWN writes or spending. For
host qualification, use the official validator and doctor commands in the
README, with a separate test profile. Do not overwrite your normal Hermes
profile, model/provider configuration or connection state for a test.

## Change boundaries

- Extend the user's existing Hermes setup. Do not select or change its model
  provider. SPAWN enforces its own rules when the agent uses SPAWN resources.
- Preserve Hermes-owned OAuth, explicit approvals, scoped authority, immutable
  terms, lease fences and idempotency. Do not replay an uncertain paid operation
  as a new request.
- Keep exact file-path, byte-limit, hash and credential-path protections. Add
  regression tests for security or recovery fixes, including a failing case
  before the fix where practical.
- Update the manifest, README, installed skill and catalog example together
  when tools, scopes, hosts, storage or network behavior changes.
- Disclose new dependencies and licenses. Do not include real customer data,
  third-party assets without permission, or credentials in tests and screenshots.

## Pull requests and evidence

Describe the user-facing problem and why the patch is the smallest useful fix.
Record the exact tested commit or tree, commands and results, plus checks not
run. A passing mocked test is not a completed OAuth flow, a real Desktop capture
or a successful paid job. Screenshots and logs must identify their actual host
and whether they use fixture or live data.

The plugin has repository checks, but SPAWN production deployment is a separate
Cloudflare workflow. A plugin PR or test does not deploy the backend, enable
server capabilities, authorize funding or submit a hackathon entry.

The repository uses the [MIT license](LICENSE). Contribute only material you
have the right to share under that license.
