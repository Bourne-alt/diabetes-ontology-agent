/* 从事件流派生「按 call_id 归组」的视图。
 *
 * 以前 reducer 另存一份 calls 数组 —— 和 events 是同一批数据的两种形状，
 * 一旦哪一侧没同步上，归组视图就整块空掉，而且不报错。这里只认事件流一个来源。
 *
 * 两种反常情况都显示出来，不静默丢：
 *   - 只有 tool_start 没等到 tool_end  → 进行中（并行调用交错时的正常中间态）
 *   - 只有 tool_end 没有配对的 tool_start → 标成「缺 tool_start」，说明事件有丢失
 */

export function groupCalls(events) {
  const order = [];
  const byKey = new Map();

  const put = (key, value) => {
    if (!byKey.has(key)) order.push(key);
    byKey.set(key, { ...(byKey.get(key) ?? {}), ...value });
  };

  for (const evt of events) {
    const raw = evt.raw ?? {};
    const callId = raw.call_id ?? null;

    if (evt.type === 'tool_start') {
      put(callId ? `id:${callId}` : `seq:${evt.seq}`, {
        callId,
        tool: raw.tool ?? '(未命名工具)',
        args: raw.arguments ?? {},
        startSeq: evt.seq,
        startMs: evt.atMs,
        orphan: false,
      });
    } else if (evt.type === 'tool_end') {
      const key = callId ? `id:${callId}` : `seq:${evt.seq}`;
      const known = byKey.has(key);
      put(key, {
        callId,
        tool: raw.tool ?? '(未命名工具)',
        result: raw.result,
        ok: raw.ok !== false,
        endSeq: evt.seq,
        endMs: evt.atMs,
        done: true,
        orphan: !known,
      });
    }
  }

  return order.map((key) => byKey.get(key));
}

export function callStatus(call, phase) {
  if (call.orphan) return { state: 'fail', badge: '记录不完整' };
  if (call.done) return call.ok
    ? { state: 'ok', badge: '成功' }
    : { state: 'fail', badge: '失败' };
  if (['done', 'failed', 'stopped'].includes(phase)) {
    return { state: 'fail', badge: '未收到结果' };
  }
  return { state: 'running', badge: '进行中' };
}
