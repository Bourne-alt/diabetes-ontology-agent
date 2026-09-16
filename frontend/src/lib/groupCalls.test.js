import test from 'node:test';
import assert from 'node:assert/strict';
import { groupCalls, callStatus } from './groupCalls.js';

const event = (type, seq, id, extra = {}) => ({ type, seq, atMs: seq * 100, raw: { call_id: id, tool: 'run_prediction_demo', ...extra } });
test('parallel tool calls pair by ID and retain failures', () => {
  const calls = groupCalls([
    event('tool_start', 1, 'a', { arguments: { pid: 'P91001' } }),
    event('tool_start', 2, 'b'),
    event('tool_end', 3, 'b', { ok: false, result: { error: 'unavailable' } }),
    event('tool_end', 4, 'a', { ok: true, result: { predictions: [7, 14, 28] } }),
  ]);
  assert.equal(calls[0].args.pid, 'P91001');
  assert.deepEqual(calls[0].result.predictions, [7, 14, 28]);
  assert.equal(callStatus(calls[0], 'done').badge, '成功');
  assert.equal(callStatus(calls[1], 'done').badge, '失败');
});
test('missing results and missing starts never appear as successful calls', () => {
  const [pending] = groupCalls([event('tool_start', 1, 'a')]);
  assert.equal(callStatus(pending, 'running').badge, '进行中');
  for (const phase of ['done', 'failed', 'stopped']) assert.equal(callStatus(pending, phase).badge, '未收到结果');
  const [orphan] = groupCalls([event('tool_end', 2, 'a', { ok: true })]);
  assert.equal(callStatus(orphan, 'done').badge, '记录不完整');
});
