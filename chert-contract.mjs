export function classifyDevRecord(record) {
  if (record?.schema_version !== 1 || record.command !== 'dev') return 'invalid';
  if (record.code === 'dev_stopped') return record.retained === 0 ? 'binding_released' : 'release_unconfirmed';
  if (['cleanup_pending', 'release_failed'].includes(record.code)) return 'release_unconfirmed';
  return 'event';
}

export function queuedReceipt(record) {
  return record?.channel === 'imessage' && record.data?.success === true && record.data.status === 'queued' &&
    typeof record.data.message_id === 'string' && typeof record.data.chat_id === 'string';
}

export function agentTarget(config, env) {
  const mode = config.mode ?? 'local';
  if (mode === 'livekit-cloud') {
    const { agentName, url } = config.livekit ?? {};
    if (!agentName || !/^wss:\/\/[a-z0-9.-]+\.livekit\.cloud\/?$/.test(url ?? '')) throw new Error('cloud_target_required');
    if ((env.AGENT_NAME && env.AGENT_NAME !== agentName) ||
        (env.LIVEKIT_URL && env.LIVEKIT_URL.replace(/\/$/, '') !== url.replace(/\/$/, ''))) throw new Error('target_mismatch');
    return { mode, agentName, url, runtime: null };
  }
  if (mode !== 'local') throw new Error('invalid_execution_mode');
  if (!Array.isArray(config.runtime) || !config.runtime.length ||
      !config.runtime.every(arg => typeof arg === 'string' && arg.length > 0)) throw new Error('runtime_required');
  return { mode, agentName: env.AGENT_NAME, url: env.LIVEKIT_URL, runtime: config.runtime };
}
