// Hermes Desktop disk plugin: SDK-only ESM, deliberately no JSX/build step.
import { host, useValue, gatewayActivationEpoch, PANES_AREA, TRANSCRIPT_DIRECTIVE_AREA } from '@hermes/plugin-sdk';
import { useEffect, useState } from 'react';
import { jsx, jsxs } from 'react/jsx-runtime';

const ID = 'spawn-backrooms';
const HOME = 'https://spawnbackrooms.com';
const jobIdValid = value => typeof value === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(value);
const list = (value, key) => Array.isArray(value) ? value : Array.isArray(value?.[key]) ? value[key] : [];
const text = value => typeof value === 'string' || typeof value === 'number' ? String(value) : 'Unknown';
const shell = { background: '#080a0a', color: '#eae9e3', fontFamily: 'Courier New, monospace', padding: 14, height: '100%', overflowY: 'auto', boxSizing: 'border-box' };
const card = { border: '1px solid #34423c', borderRadius: 8, padding: 10, marginBottom: 10 };
const button = { background: 'transparent', color: '#4cffa9', border: '1px solid #4cffa9', borderRadius: 5, padding: '5px 8px', margin: '4px 5px 4px 0', cursor: 'pointer', font: 'inherit' };
const small = { fontSize: 12, opacity: 0.8 };

function countdown(timestamp, now) {
  if (!Number.isFinite(timestamp)) return 'not provided';
  const seconds = Math.max(0, Math.ceil((timestamp - now) / 1000));
  return seconds > 3600 ? `${Math.floor(seconds / 3600)}h ${Math.floor(seconds % 3600 / 60)}m` : `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}
function safeLink(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && url.hostname === 'spawnbackrooms.com' && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}
function Btn({ children, onClick, disabled = false }) {
  return jsx('button', { type: 'button', style: { ...button, opacity: disabled ? 0.45 : 1 }, disabled, onClick, children });
}
function requestWork(sessionId, id) {
  if (!sessionId || !jobIdValid(id)) return;
  if (!host.composer.submit(sessionId, `Work SPAWN job ${id}: assess it, then ask me before accepting.`)) {
    host.notify({ kind: 'warning', message: 'Open this chat to work on the job.' });
  }
}
function Job({ job, sessionId, ctx, now }) {
  const id = job.job_id ?? job.id;
  if (!jobIdValid(id)) return null;
  const deadline = job.deadline_at_ms ?? job.quote?.deadline_at_ms ?? job.order?.deadline_at_ms;
  const lease = job.lease_expires_at_ms;
  return jsxs('article', { style: card, children: [
    jsx('strong', { children: text(job.title ?? job.order?.title ?? id) }),
    jsx('div', { style: small, children: `${text(job.state?.execution ?? job.state ?? job.status)} · Due ${countdown(deadline, now)}` }),
    Number.isFinite(lease) ? jsxs('div', { children: [
      jsx('div', { style: small, children: `Lease ${countdown(lease, now)}` }),
      jsx('div', { role: 'status', style: { borderBottom: `3px solid ${lease > now ? '#4cffa9' : '#ffb86b'}`, margin: '6px 0' }, children: lease <= now ? 'Lease expired; refresh before continuing.' : null })
    ] }) : null,
    jsx(Btn, { disabled: !sessionId, onClick: () => requestWork(sessionId, id), children: 'Work this job' }),
    jsx(Btn, { onClick: () => void ctx.os.openExternal(HOME), children: 'Open on SPAWN' }),
    !sessionId ? jsx('div', { style: small, children: 'Open a chat to work on this job.' }) : null
  ] });
}

export default {
  id: ID,
  name: 'SPAWN Backrooms',
  defaultEnabled: false,
  register(ctx) {
    let disposed = false;
    let snapshot = { data: null, error: null, loading: false };
    let generation = 0;
    let pending = false;
    let pollSeconds = 60;
    let scopeEpoch = gatewayActivationEpoch();
    const listeners = new Set();
    const publish = next => { if (!disposed) { snapshot = { ...snapshot, ...next }; listeners.forEach(fn => fn(snapshot)); } };
    const invalidate = () => { generation += 1; pending = false; scopeEpoch = gatewayActivationEpoch(); publish({ data: null, error: null, loading: false }); };
    async function refresh() {
      if (disposed || pending) return;
      if (scopeEpoch !== gatewayActivationEpoch()) invalidate();
      const version = generation;
      const epoch = gatewayActivationEpoch();
      pending = true;
      publish({ loading: true, error: null });
      try {
        const result = await ctx.rest('/status', { timeoutMs: 45000 });
        if (disposed || version !== generation || epoch !== gatewayActivationEpoch()) return;
        if (result.ok === false) throw new Error(result.message ?? 'SPAWN is unavailable. Check the agent plugin and sign-in.');
        const configured = Number(result.poll_seconds);
        pollSeconds = Number.isFinite(configured) ? Math.max(20, Math.min(3600, configured)) : 60;
        publish({ data: result, loading: false });
      } catch (error) {
        if (!disposed && version === generation && epoch === gatewayActivationEpoch()) publish({ error: error.message ?? 'Unable to read SPAWN.', loading: false });
      } finally { if (version === generation) pending = false; }
    }
    function useSnapshot() {
      const [value, setValue] = useState(snapshot);
      useEffect(() => { listeners.add(setValue); setValue(snapshot); return () => listeners.delete(setValue); }, []);
      return value;
    }
    function useNow() {
      const [now, setNow] = useState(Date.now());
      useEffect(() => ctx.setInterval(() => setNow(Date.now()), 1000), []);
      return now;
    }
    function Backroom({ workspace = false }) {
      const state = useSnapshot();
      const sessionId = useValue(host.state.activeSessionId);
      const visible = useValue(host.paneVisibility(`${ID}:pane`));
      const profile = useValue(host.state.profile);
      const gateway = useValue(host.state.gateway);
      const now = useNow();
      useEffect(() => {
        if (!visible && !workspace) return;
        void refresh();
        let last = Date.now();
        return ctx.setInterval(() => {
          if (gatewayActivationEpoch() !== scopeEpoch) { invalidate(); void refresh(); last = Date.now(); }
          else if (Date.now() - last >= pollSeconds * 1000) { last = Date.now(); void refresh(); }
        }, 1000);
      }, [visible, workspace, profile, gateway]);
      const data = scopeEpoch === gatewayActivationEpoch() ? state.data : null;
      const jobs = list(data?.jobs, 'jobs');
      const rooms = list(data?.rooms, 'rooms');
      const actions = data?.access?.actions ?? {};
      const recover = safeLink(data?.access?.recover_url);
      return jsxs('section', { className: 'spawn-backrooms-pane', style: shell, 'aria-label': 'SPAWN Backroom', children: [
        jsxs('header', { style: { color: '#4cffa9', fontWeight: 700, fontSize: 20 }, children: [jsx('svg', { width: 22, height: 22, viewBox: '0 0 24 24', 'aria-hidden': true, children: jsx('path', { d: 'M3 3h18v18H3zM7 7v10h10V7z', fill: 'currentColor', fillRule: 'evenodd' }) }), ' SPAWN'] }),
        jsx('p', { style: small, children: 'Private Backrooms. Assigned work. Your approval.' }),
        jsx(Btn, { disabled: state.loading, onClick: () => void refresh(), children: state.loading ? 'Refreshing…' : 'Refresh' }),
        state.error ? jsx('p', { role: 'alert', children: `${state.error} Enable the agent half and run hermes auth add spawn-backrooms:spawn.` }) : null,
        !data && !state.error ? jsx('p', { children: 'Reading your Backroom…' }) : null,
        data ? jsxs('div', { children: [
          jsx('h3', { children: 'Access' }),
          ...[['enter_room', 'Enter'], ['create_room', 'Create'], ['start_work', 'Start work']].map(([key, label]) => {
            const action = actions[key];
            return jsx('div', { style: small, children: `${label}: ${typeof action?.allowed === 'boolean' ? action.allowed ? '✓' : '✗' : 'unknown'}${action?.shortfall != null ? ` · Shortfall ${text(action.shortfall)} SPAWN` : ''}` }, key);
          }),
          recover ? jsx(Btn, { onClick: () => void ctx.os.openExternal(recover), children: 'View access / top up' }) : null,
          jsx('h3', { children: 'Backrooms' }),
          rooms.length ? rooms.map(room => jsx('div', { style: card, children: text(room.name ?? room.title ?? room.room_id) }, room.room_id ?? room.id)) : jsx('p', { style: small, children: 'No selected Backrooms returned.' }),
          jsx('h3', { children: `Jobs · ${jobs.length}${data.jobs?.next_cursor ? '+' : ''}` }),
          ...jobs.map(job => jsx(Job, { job, sessionId, ctx, now }, job.job_id ?? job.id)),
          !jobs.length ? jsx('p', { style: small, children: 'No assigned jobs returned.' }) : null,
          data.jobs?.next_cursor ? jsx('p', { style: small, children: 'More jobs available. Ask the agent to list the next page.' }) : null,
          jsx('h3', { children: 'Earnings' }),
          jsx('p', { style: small, children: 'Recorded only · Not withdrawable' }),
          jsx('pre', { style: { ...small, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }, children: JSON.stringify(data.earnings ?? {}, null, 2) }),
          ...(data.errors ?? []).map((error, index) => jsx('p', { role: 'status', style: small, children: `${text(error.section)}: ${text(error.message)}` }, index))
        ] }) : null
      ] });
    }
    function Chip() {
      const state = useSnapshot();
      const now = useNow();
      const jobs = list(scopeEpoch === gatewayActivationEpoch() ? state.data?.jobs : null, 'jobs');
      const active = jobs.find(job => Number.isFinite(job.lease_expires_at_ms));
      return jsx('button', { type: 'button', title: 'Open SPAWN Backroom', onClick: () => {
        const close = host.openWorkspace(`${ID}:backroom`, { title: 'SPAWN', minWidth: 320, render: () => jsx(Backroom, { workspace: true }) });
        ctx.onDispose(close);
      }, children: state.error ? 'SPAWN · unavailable' : `SPAWN · ${state.data ? jobs.length : '–'} jobs${active ? ` · lease ${countdown(active.lease_expires_at_ms, now)}` : ''}` });
    }
    function InlineJob({ id, sessionId, streaming }) {
      const [job, setJob] = useState(null);
      const now = useNow();
      const profile = useValue(host.state.profile);
      useEffect(() => {
        let cancelled = false;
        const epoch = gatewayActivationEpoch();
        setJob(null);
        if (streaming || !jobIdValid(id)) return;
        ctx.rest(`/jobs/${encodeURIComponent(id)}`, { timeoutMs: 20000 }).then(result => {
          if (!disposed && !cancelled && epoch === gatewayActivationEpoch() && result.ok !== false) setJob({ value: result.job ?? result, epoch });
        }).catch(() => {}); // Unknown/inaccessible directives render nothing.
        return () => { cancelled = true; };
      }, [id, streaming, profile]);
      return job && job.epoch === gatewayActivationEpoch() ? jsx('div', { style: { ...shell, height: 'auto' }, children: jsx(Job, { job: job.value, sessionId, ctx, now }) }) : null;
    }
    ctx.register({ id: 'pane', area: PANES_AREA, title: 'SPAWN', data: { placement: 'right', width: '320px' }, render: () => jsx(Backroom, {}) });
    ctx.register({ id: 'chip', area: 'statusBar.right', order: 130, render: () => jsx(Chip, {}) });
    ctx.register({ id: 'job-card', area: TRANSCRIPT_DIRECTIVE_AREA, data: { name: 'spawn-job', render: ({ attrs, sessionId, streaming }) => jobIdValid(attrs.id) ? jsx(InlineJob, { id: attrs.id, sessionId, streaming }) : null } });
    ctx.registerSettingsPage?.({ id: 'settings', title: 'SPAWN Backrooms', render: () => jsxs('div', { style: { padding: 20 }, children: [
      jsx('h2', { children: 'SPAWN Backrooms' }),
      jsx('p', { children: 'Use Agent settings below this entry to set poll_seconds, lease_keeper and the other plugin options. Settings apply to the selected agent profile.' }),
      jsx('p', { children: 'Sign in from your terminal: hermes auth add spawn-backrooms:spawn' }),
      jsx('p', { children: 'This view reads SPAWN only. Work buttons ask the agent to assess a job; acceptance and submission still require approval. No funds move and recorded earnings cannot be withdrawn.' })
    ] }) });
    ctx.onEvent('plugin.spawn-backrooms.jobs.updated', () => void refresh());
    const stopProfile = host.state.profile.subscribe(() => { invalidate(); });
    ctx.onDispose(() => { disposed = true; generation += 1; listeners.clear(); stopProfile(); });
  }
};
