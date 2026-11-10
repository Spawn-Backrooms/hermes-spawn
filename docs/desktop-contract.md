# Desktop integration contract

Verified against the official documentation on 2026-11-10:

- [Plugin guide](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins)
- [Desktop SDK](https://hermes-agent.nousresearch.com/docs/developer-guide/desktop-plugin-sdk)
- [Dashboard API](https://hermes-agent.nousresearch.com/docs/user-guide/features/extending-the-dashboard)
- [Public Python API](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/public-api)

The backend-only dashboard manifest is the minimal `{name, api}` form documented under “One package, both SDKs.” Hermes imports the API as a standalone module, so it loads the adjacent plugin-owned client using a fixed file path. It does not modify core modules, import paths, or credentials.

The Desktop half is off by default. It contributes a 320px right-side pane, status chip, `spawn-job` transcript directive, and Settings page. Hermes supplies the unified package's schema form as the “Agent settings” child page. No custom settings writes are implemented.

The chip reveals a SPAWN workspace view with the documented `host.openWorkspace` API. It does not manipulate layout internals to focus the right pane. Both views use the same data snapshot.

`ctx.rest` documents a timeout but no AbortSignal. Requests therefore use timeouts and generation/activation guards: disabled, unmounted, or old-profile requests cannot publish their results. Already-running read-only server calls may finish. Polling runs while a SPAWN view is visible; updates also respond to `plugin.spawn-backrooms.jobs.updated`. Polling defaults to 60 seconds, clamped to 20–3600 seconds. The backend cache is profile-scoped, bounded, and expires after 20 seconds.

All four backend routes are GET-only. The client wrapper explicitly permits only identity, access, rooms, jobs, job details, and earnings reads. Each network call runs in `asyncio.to_thread`, preserving a plugin-owned stack frame and the request's profile context. Independent status sections run concurrently after identity succeeds.

No job writes, wallet operations, authentication, or acceptance happen inside the UI. “Work this job” submits an assessment request to the addressed chat; the ordinary tool approval boundary still applies. External links are restricted to HTTPS on `spawnbackrooms.com`. Unknown/inaccessible inline job IDs render nothing.

Offline checks:

```sh
python -m unittest tests.test_dashboard -v
node --input-type=module --check < desktop/plugin.js
node tests/desktop-smoke.mjs
```

These checks verify backend route restrictions, cache/profile behavior, error handling, settings reads, registration, basic no-session rendering, directive validation, and cleanup. They do not replace testing in a real Hermes Desktop instance. Live authentication, actual server response shapes, visual layout, plugin disable behavior, and job approval flows remain release checks.
