# Implementation references

Checked November 10, 2026:

- https://hermes-agent.nousresearch.com/docs/developer-guide/plugins
- https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/public-api
- https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/catalog-submission
- https://hermes-agent.nousresearch.com/docs/developer-guide/desktop-plugin-sdk
- https://hermes-agent.nousresearch.com/docs/user-guide/features/extending-the-dashboard
- https://github.com/NousResearch/hermes-agent/releases/tag/v0.23.1

The current public Hermes PluginContext source confirmed tool/command/hook,
state, cleanup and settings APIs. Its provider-request implementation confirmed
response shape, caller attribution, host restrictions and token ownership.
The current SPAWN server schemas were checked read-only to verify command pins,
job snapshots, text upload descriptors, manifests, room inputs and capability
names. Private backend source is deliberately not bundled in this plugin.

Runtime code uses only documented public Hermes imports. Test-only SDK and
module fakes are not shipped executable host overrides.
