// Web dashboard SDK entry. Native Desktop continues to use desktop/plugin.js.
(function () {
  'use strict';
  const SDK = window.__HERMES_PLUGIN_SDK__;
  const React = SDK.React;
  const h = React.createElement;
  function Page() {
    const [state, setState] = React.useState({ loading: true });
    const [revision, setRevision] = React.useState(0);
    React.useEffect(function () {
      let active = true;
      setState({ loading: true });
      // SDK owns dashboard authentication. This is a fixed same-origin GET only.
      SDK.fetchJSON('/api/plugins/spawn-backrooms/status').then(function (data) {
        if (active) setState({ data: data });
      }).catch(function () {
        if (active) setState({ failed: true });
      });
      return function () { active = false; };
    }, [revision]);
    const data = state.data;
    const connected = data && data.ok === true;
    const jobs = data && data.jobs && Array.isArray(data.jobs.jobs) ? data.jobs.jobs : null;
    const rooms = data && data.rooms && Array.isArray(data.rooms.rooms) ? data.rooms.rooms : null;
    return h('section', { className: 'p-4 space-y-4', 'aria-label': 'SPAWN Backrooms' },
      h('h1', { className: 'text-xl font-semibold' }, 'SPAWN Backrooms'),
      h('p', null, 'Connection and assigned-work status. This page does not accept jobs or move funds.'),
      state.loading ? h('p', { role: 'status' }, 'Reading SPAWN…') : null,
      state.failed ? h('p', { role: 'alert' }, 'Unable to read SPAWN. Check that the agent plugin is enabled, then retry.') : null,
      data && !connected ? h('div', { role: 'status' },
        h('p', null, data.error === 'not_signed_in' ? 'Connect this Hermes profile to SPAWN.' : 'SPAWN is not ready. Run the doctor command to inspect the current connection.'),
        h('pre', { className: 'whitespace-pre-wrap break-words' }, 'hermes config set SPAWN_CLIENT_ID hermes\nhermes auth add spawn-backrooms:spawn\nhermes spawn doctor'),
        h('p', null, 'Run these in the same Hermes profile. Review consent yourself. Sign-in does not fund work.')) : null,
      connected ? h('div', null,
        h('p', { role: 'status' }, 'Connected to SPAWN'),
        h('p', null, jobs ? jobs.length + ' assigned jobs' : 'Assigned jobs unavailable'),
        h('p', null, rooms ? rooms.length + ' selected Backrooms' : 'Backrooms unavailable'),
        Array.isArray(data.errors) && data.errors.length ? h('p', { role: 'status' }, 'Some sections could not be read. Run /spawn status for details.') : null,
        h('p', null, 'Ask Hermes to run /spawn jobs to inspect your work. Proposals, acceptance and submission retain their normal approval flow.')) : null,
      h('button', { type: 'button', className: 'border rounded px-3 py-2', disabled: state.loading, onClick: function () { setRevision(revision + 1); } }, 'Refresh'),
      h('p', { className: 'text-sm text-muted-foreground' }, 'The native Hermes Desktop pane is a separate interface. Enable it in Desktop plugin settings.'));
  }
  window.__HERMES_PLUGINS__.register('spawn-backrooms', Page);
})();
