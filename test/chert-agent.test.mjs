import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import { mkdtempSync, cpSync, chmodSync, rmSync, writeFileSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';

// Tests must never load or copy the owner's actual credentials.
const fixture = mkdtempSync(resolve(tmpdir(), 'chert-agent-tests-'));
for (const name of ['chert-agent.mjs', 'chert-contract.mjs', 'chert-agent.config.json']) {
  cpSync(resolve(name), resolve(fixture, name));
}
writeFileSync(resolve(fixture, '.env.local'), '', { mode: 0o600 });
symlinkSync(resolve('node_modules'), resolve(fixture, 'node_modules'), 'dir');
after(() => rmSync(fixture, { recursive: true, force: true }));
const script = resolve(fixture, 'chert-agent.mjs');
function run(...args) {
  const result = spawnSync(process.execPath, [script, ...args], {
    encoding: 'utf8', env: { PATH: process.env.PATH }, timeout: 3000,
  });
  const records = result.stdout.trim().split('\n').filter(Boolean).map(line => JSON.parse(line));
  return { ...result, records, record: records.length === 1 ? records[0] : null };
}

test('outbound call fails closed without claiming success', () => {
  const result = run('call');
  assert.equal(result.record?.state, 'capability_pending');
  assert.notEqual(result.status, 0);
});
test('iMessage watch does not invent an inbox API', () => {
  const result = run('watch', 'imessage');
  assert.equal(result.record?.state, 'capability_pending');
});
test('noninteractive message cannot send without fresh human approval', () => {
  const result = run('message');
  assert.equal(result.record?.state, 'approval_required');
});
test('noninteractive start cannot expose inbound line', () => {
  const result = run('start');
  assert.equal(result.record?.state, 'approval_required');
});
test('setup reports missing configuration without leaking values', () => {
  const result = run('setup');
  assert.equal(result.record?.state, 'configuration_pending');
  assert.equal(result.record?.variables?.LIVEKIT_API_SECRET, false);
  assert.equal(result.record?.media_verified, false);
});
test('stop without connector does not claim release', () => {
  const result = run('stop');
  assert.equal(result.record?.state, 'no_local_connector');
  assert.equal(result.record?.allocation_released, false);
});

test('private environment file with public permissions is rejected', () => {
  const directory = mkdtempSync(resolve(tmpdir(), 'chert-permissions-'));
  try {
    for (const name of ['chert-agent.mjs', 'chert-contract.mjs', 'chert-agent.config.json']) cpSync(resolve(name), resolve(directory, name));
    writeFileSync(resolve(directory, '.env.local'), '', { mode: 0o600 });
    chmodSync(resolve(directory, '.env.local'), 0o644);
    const result = spawnSync(process.execPath, [resolve(directory, 'chert-agent.mjs'), 'setup'], { encoding: 'utf8' });
    assert.equal(JSON.parse(result.stdout).state, 'private_env_permissions_required');
    assert.equal(result.status, 1);
  } finally { rmSync(directory, { recursive: true, force: true }); }
});

test('health marks optional SDK credentials unconfigured without mixing them with CLI login', () => {
  const result = run('health');
  const checks = result.records.filter(record => record.check?.startsWith('chert-sdk facetime'));
  assert.equal(checks.length, 3);
  assert.ok(checks.every(record => record.state === 'capability_unconfigured'));
  assert.ok(checks.every(record => record.required_for_inbound_connector === false));
});

test('published dev codes distinguish retained cleanup from confirmed release', async () => {
  const { classifyDevRecord } = await import('../chert-contract.mjs');
  assert.equal(classifyDevRecord({ schema_version: 1, command: 'dev', code: 'dev_stopped', retained: 0 }), 'binding_released');
  assert.equal(classifyDevRecord({ schema_version: 1, command: 'dev', code: 'dev_stopped', retained: 1 }), 'release_unconfirmed');
  assert.equal(classifyDevRecord({ schema_version: 1, command: 'dev', code: 'release_failed' }), 'release_unconfirmed');
  assert.equal(classifyDevRecord({ schema_version: 1, command: 'dev', code: 'call_bridge_ready' }), 'event');
  assert.equal(classifyDevRecord({ schema_version: 2, command: 'dev', code: 'dev_stopped', retained: 0 }), 'invalid');
});

test('queued SDK receipt is read from data and never treated as delivered', async () => {
  const { queuedReceipt } = await import('../chert-contract.mjs');
  assert.equal(queuedReceipt({ channel: 'imessage', data: { success: true, status: 'queued', message_id: 'm1', chat_id: 'c1' } }), true);
  assert.equal(queuedReceipt({ channel: 'imessage', data: { status: 'delivered' } }), false);
  assert.equal(queuedReceipt({ status: 'queued' }), false);
});

test('hosted agent uses configured dispatch name and never launches local runtime', async () => {
  const { agentTarget } = await import('../chert-contract.mjs');
  const target = agentTarget({ mode: 'livekit-cloud', livekit: { agentName: 'assistant-0c8', url: 'wss://chris-1zd6fz6o.livekit.cloud' }, runtime: ['must-not-run'] }, {});
  assert.equal(target.agentName, 'assistant-0c8');
  assert.equal(target.url, 'wss://chris-1zd6fz6o.livekit.cloud');
  assert.equal(target.runtime, null);
});

test('hosted target rejects environment accidentally pointing at another project or agent', async () => {
  const { agentTarget } = await import('../chert-contract.mjs');
  const config = { mode: 'livekit-cloud', livekit: { agentName: 'assistant-0c8', url: 'wss://chris-1zd6fz6o.livekit.cloud' } };
  assert.throws(() => agentTarget(config, { AGENT_NAME: 'other-agent' }), /target_mismatch/);
  assert.throws(() => agentTarget(config, { LIVEKIT_URL: 'wss://other.livekit.cloud' }), /target_mismatch/);
});

test('local mode still requires a valid runtime and unknown modes fail closed', async () => {
  const { agentTarget } = await import('../chert-contract.mjs');
  assert.throws(() => agentTarget({ mode: 'invalid' }, {}), /invalid_execution_mode/);
  assert.throws(() => agentTarget({ runtime: [] }, {}), /runtime_required/);
  assert.deepEqual(agentTarget({ runtime: ['node', '/local/agent.mjs'] }, {}).runtime, ['node', '/local/agent.mjs']);
});
