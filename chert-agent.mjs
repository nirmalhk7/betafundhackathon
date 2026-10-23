#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync, chmodSync } from 'node:fs';
import { createServer, createConnection } from 'node:net';
import { createInterface } from 'node:readline/promises';
import { createInterface as lines } from 'node:readline';
import { randomUUID } from 'node:crypto';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { classifyDevRecord, queuedReceipt, agentTarget } from './chert-contract.mjs';

const root = dirname(fileURLToPath(import.meta.url));
process.chdir(root);
const command = process.argv[2] || 'help';
const stateDir = join(root, '.chert-agent');
const socketPath = join(stateDir, 'control.sock');
const sessionPath = join(stateDir, 'connector.json');
const names = ['CHERT_PROJECT_ID', 'CHERT_BASE_URL', 'CHERT_API_KEY', 'CHERT_FACETIME_URL',
  'CHERT_FACETIME_TOKEN', 'LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET', 'AGENT_NAME', 'OPENAI_API_KEY'];
const envPath = join(root, '.env.local');
if (existsSync(envPath)) {
  if ((statSync(envPath).mode & 0o777) !== 0o600) {
    console.log(JSON.stringify({ wrapper_schema_version: 1, command, state: 'private_env_permissions_required' }));
    process.exit(1);
  }
  process.loadEnvFile(envPath);
}
const config = JSON.parse(readFileSync(join(root, 'chert-agent.config.json'), 'utf8'));
let target;
try {
  target = agentTarget(config, process.env);
  if (target.agentName) process.env.AGENT_NAME = target.agentName;
  if (target.url) process.env.LIVEKIT_URL = target.url;
} catch (error) {
  console.log(JSON.stringify({ wrapper_schema_version: 1, command, state: error.message }));
  process.exit(1);
}
const binary = name => join(root, 'node_modules', '.bin', name);
const emit = (state, extra = {}) => console.log(JSON.stringify({ wrapper_schema_version: 1, command, state, ...extra }));
const variables = () => Object.fromEntries(names.map(name => [name, Boolean(process.env[name])]));
const configured = () => Boolean(process.env.CHERT_PROJECT_ID && process.env.AGENT_NAME &&
  process.env.LIVEKIT_URL && process.env.LIVEKIT_API_KEY && process.env.LIVEKIT_API_SECRET);
const privateDir = () => { mkdirSync(stateDir, { recursive: true, mode: 0o700 }); chmodSync(stateDir, 0o700); };

// Child output stays in memory. Never persist raw provider responses or stderr.
function run(name, args) {
  return new Promise(resolve => {
    const child = spawn(binary(name), args, { cwd: root, stdio: ['ignore', 'pipe', 'pipe'] });
    let stdout = '';
    child.stdout.on('data', chunk => { if (stdout.length < 1024 * 1024) stdout += chunk; });
    child.stderr.resume();
    child.on('error', () => resolve({ code: 1, output: '' }));
    child.on('close', code => resolve({ code: code ?? 1, output: stdout }));
  });
}
async function confirm(prompt) {
  if (!process.stdin.isTTY || !process.stdout.isTTY) return false;
  const input = createInterface({ input: process.stdin, output: process.stdout });
  try { return (await input.question(`${prompt}\nType YES to approve: `)) === 'YES'; }
  finally { input.close(); }
}
function control(action) {
  return new Promise(resolve => {
    const connection = createConnection(socketPath);
    connection.on('connect', () => connection.write(`${action}\n`));
    connection.on('data', chunk => process.stdout.write(chunk));
    connection.on('error', () => { emit('no_local_connector', { allocation_released: false }); resolve(); });
    connection.on('end', resolve);
  });
}
async function reads() {
  const checks = [['chert', ['doctor', '--json', '--project', process.env.CHERT_PROJECT_ID || '']],
    ...['context', 'facetime status', 'facetime lines', 'facetime workers'].map(item => ['chert-sdk', item.split(' ')])];
  for (const [name, args] of checks) {
    if (name === 'chert' && !process.env.CHERT_PROJECT_ID) {
      emit('configuration_pending', { check: 'doctor', missing: 'CHERT_PROJECT_ID' }); process.exitCode = 1; continue;
    }
    const result = await run(name, args);
    if (result.code !== 0) process.exitCode = 1;
    // Exit status is a diagnostic result, never evidence of media or delivery.
    emit('check_result', { check: `${name} ${args.slice(0, name === 'chert' ? 1 : 2).join(' ')}`,
      exit_code: result.code, media_verified: false, details: 'Use the native CLI privately to inspect project and line identity.' });
  }
}
async function message() {
  if (!process.stdin.isTTY || !process.stdout.isTTY) { emit('approval_required'); process.exitCode = 1; return; }
  if (!process.env.CHERT_BASE_URL || !process.env.CHERT_API_KEY || !process.env.CHERT_PROJECT_ID) {
    emit('configuration_pending'); process.exitCode = 1; return;
  }
  const input = createInterface({ input: process.stdin, output: process.stdout });
  let phone, body;
  try {
    phone = await input.question('Recipient (E.164): ');
    body = await input.question('Exact message body (single line): ');
  } finally { input.close(); }
  if (!/^\+[1-9]\d{7,14}$/.test(phone) || !body.trim()) { emit('invalid_message'); process.exitCode = 1; return; }
  if (!await confirm(`Send iMessage to ${phone}:\n${body}\nRecipient and Chert will receive this content. Provider charges may apply; pricing is not configured.`)) {
    emit('approval_required'); process.exitCode = 1; return;
  }
  privateDir();
  // One unresolved request blocks future sends, including after a process restart.
  const pending = join(stateDir, 'pending-message.json');
  const requestId = randomUUID();
  try { writeFileSync(pending, JSON.stringify({ request_id: requestId, state: 'unconfirmed_text_outcome' }), { flag: 'wx', mode: 0o600 }); }
  catch (error) { if (error.code !== 'EEXIST') throw error; emit('unconfirmed_text_outcome', { reconciliation_required: true }); process.exitCode = 1; return; }
  const result = await run('chert-sdk', ['imessage', 'send', '--phone', phone, '--body', body, '--idempotency-key', requestId]);
  let receipt;
  try { receipt = JSON.parse(result.output); } catch { /* Fail closed for unknown responses. */ }
  const state = result.code === 0 && queuedReceipt(receipt) ? 'queued' : 'unconfirmed_text_outcome';
  writeFileSync(pending, JSON.stringify({ request_id: requestId, state }), { mode: 0o600 });
  emit(state, { request_id: requestId, delivered: false, reconciliation_required: true });
  if (state !== 'queued') process.exitCode = 1;
}
async function start() {
  if (!process.stdin.isTTY || !process.stdout.isTTY) { emit('approval_required'); process.exitCode = 1; return; }
  if (!configured()) {
    emit('configuration_pending', { variables: variables(), execution_mode: target.mode }); process.exitCode = 1; return;
  }
  if (existsSync(socketPath)) { emit('local_session_exists', { action: 'Inspect status; do not overwrite session state.' }); return; }
  if (existsSync(sessionPath) && JSON.parse(readFileSync(sessionPath, 'utf8')).state !== 'binding_released') {
    emit('release_unconfirmed', { action: 'Have project owner/admin reconcile previous session before removing local connector receipt.' }); return;
  }
  const doctor = await run('chert', ['doctor', '--project', process.env.CHERT_PROJECT_ID, '--json']);
  if (doctor.code !== 0) { emit('health_failed', { exit_code: doctor.code, media_verified: false }); process.exitCode = 1; return; }
  const action = target.runtime ? 'Start configured personal-agent runtime and connect approved project line' : `Connect approved project line to hosted LiveKit agent ${target.agentName}`;
  if (!await confirm(`${action} for incoming FaceTime calls? Callers may interact with your agent. Provider charges may apply.`)) {
    emit('approval_required'); return;
  }
  privateDir();
  writeFileSync(sessionPath, JSON.stringify({ request_id: randomUUID(), state: 'release_unconfirmed' }), { mode: 0o600 });
  const viewers = new Set();
  let connector, runtime, stopping = false, released = false;
  const broadcast = event => {
    const record = JSON.stringify(event) + '\n';
    process.stdout.write(record);
    for (const viewer of viewers) viewer.write(record);
  };
  const stop = () => {
    if (!stopping && connector) { stopping = true; connector.kill('SIGINT'); }
  };
  const server = createServer(client => {
    client.on('error', () => viewers.delete(client));
    client.once('data', data => {
      const action = data.toString().trim();
      if (action === 'watch') { viewers.add(client); client.on('close', () => viewers.delete(client)); }
      else if (action === 'stop') { viewers.add(client); stop(); }
      else client.end(JSON.stringify({ wrapper_schema_version: 1, state: stopping ? 'stopping' : 'running', media_verified: false }) + '\n');
    });
  });
  server.on('error', () => { emit('control_unavailable'); process.exitCode = 1; });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(socketPath, resolve); });
  chmodSync(socketPath, 0o600);
  if (target.runtime) {
    runtime = spawn(target.runtime[0], target.runtime.slice(1), { cwd: root, stdio: 'ignore' });
    runtime.on('error', () => { emit('runtime_failed'); stop(); });
    runtime.on('close', () => stop());
  }
  connector = spawn(binary('chert'), ['dev', '--agent', process.env.AGENT_NAME, '--project', process.env.CHERT_PROJECT_ID, '--json'], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'] });
  connector.stderr.resume();
  const input = lines({ input: connector.stdout });
  input.on('line', line => {
    let event;
    try { event = JSON.parse(line); } catch { return; }
    const classification = classifyDevRecord(event);
    if (classification === 'invalid') return;
    // Forward only documented event names and schema metadata; raw payloads may contain private caller data.
    if (classification === 'binding_released') released = true;
    if (classification === 'release_unconfirmed') { released = false; stop(); }
    broadcast({ wrapper_schema_version: 1, command: 'watch', state: 'chert_event', chert: { schema_version: 1, command: 'dev', code: event.code, ...(typeof event.retained === 'number' ? { retained: event.retained } : {}) }, payload_redacted: true });
  });
  process.on('SIGINT', stop);
  process.on('SIGTERM', stop);
  connector.on('error', () => { emit('connector_failed'); runtime?.kill('SIGINT'); server.close(); });
  connector.on('close', code => {
    runtime?.kill('SIGINT');
    writeFileSync(sessionPath, JSON.stringify({ state: released ? 'binding_released' : 'release_unconfirmed' }), { mode: 0o600 });
    broadcast({ wrapper_schema_version: 1, command: 'stop', state: released ? 'binding_released' : 'release_unconfirmed', allocation_released: false, exit_code: code });
    for (const viewer of viewers) viewer.end();
    server.close();
    if (!released) process.exitCode = 1;
  });
}

try {
  switch (command) {
    case 'setup': emit(configured() ? 'configured' : 'configuration_pending', { variables: variables(), execution_mode: target.mode, agent_name: target.agentName, runtime_required: Boolean(target.runtime), media_verified: false }); break;
    case 'health': await reads(); break;
    case 'status': await control('status'); await reads(); break;
    case 'start': await start(); break;
    case 'message': await message(); break;
    case 'call': emit('capability_pending', { capability: 'outbound_facetime' }); process.exitCode = 1; break;
    case 'watch': if (process.argv[3] === 'imessage') { emit('capability_pending', { capability: 'imessage_inbox' }); process.exitCode = 1; } else await control('watch'); break;
    case 'stop': await control('stop'); break;
    case 'help': emit('help', { commands: ['setup', 'start', 'health', 'message', 'call', 'status', 'watch', 'stop'] }); break;
    default: emit('unknown_command'); process.exitCode = 1;
  }
} catch { emit('local_error', { action: 'Check local configuration, permissions, and installed dependencies. No automatic retry.' }); process.exitCode = 1; }
