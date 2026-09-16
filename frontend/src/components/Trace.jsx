import { useMemo } from 'react';
import Section from './Section.jsx';
import { formatMs } from '../lib/runReducer.js';
import { groupCalls } from '../lib/groupCalls.js';
import { toolLabel } from '../lib/toolLabels.js';
import { callStatus } from '../lib/groupCalls.js';
import { asText } from '../lib/text.js';

function pretty(value) {
  if (value === undefined) return '';
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function shortId(id) {
  if (!id) return '—';
  const text = asText(id);
  return text.length > 12 ? `${text.slice(0, 6)}…${text.slice(-4)}` : text;
}

function Grouped({ calls, phase }) {

  return (
    <>
      {calls.map((call, i) => {
        const { state, badge } = callStatus(call, phase);
        const spent = call.done && call.startMs !== undefined
          ? formatMs(call.endMs - call.startMs)
          : '';
        return (
          <details className="call" data-state={state} key={`${call.callId ?? 'noid'}:${i}`}>
            <summary className="call__head">
              <span className="call__dot" />
              <span className="call__tool">{toolLabel(call.tool)} <small>{asText(call.tool)}</small></span>
              <div className="spacer" />
              <span className="call__badge">{badge}</span>
              <span className="call__ms">{spent}</span>
            </summary>
            <div className="call__body">
              <div>
                <div className="call__k">
                  call_id {shortId(call.callId)} · seq {call.startSeq ?? '—'}
                  {call.done ? ` → ${call.endSeq}` : ''}
                </div>
                <pre>
                  {call.startSeq === undefined
                    ? '没有收到配对的 tool_start，参数不可知。'
                    : pretty(call.args)}
                </pre>
              </div>
              <div>
                <div className="call__k">{call.done ? 'tool_end · result' : 'tool_end 尚未到达'}</div>
                <pre>
                  {call.done
                    ? pretty(call.result)
                    : (['done', 'failed', 'stopped'].includes(phase) ? '本轮已结束，未收到工具返回结果。' : '正在等待工具返回结果。')}
                </pre>
              </div>
            </div>
          </details>
        );
      })}
    </>
  );
}

export default function Trace({ events, phase }) {
  const calls = useMemo(() => groupCalls(events), [events]);
  if (calls.length === 0) return null;

  return (
    <Section
      className="trace trace--inline"
      title={<span className="lbl">tools</span>}
      right={<span className="trace__count">{calls.length} 次调用</span>}
    >
      <div className="trace__body scroll">
        <Grouped calls={calls} phase={phase} />
      </div>

      <div className="trace__foot">
        <div className="trace__note">
          <span className="chip chip--neutral">[redacted]</span>
          <span>连接串、密钥与 sk- 前缀值在进入事件前已被替换。</span>
        </div>
        <div className="trace__note">
          <span className="chip chip--bad">ok=false</span>
          <span>工具失败是执行问题，不是查无数据。</span>
        </div>
      </div>
    </Section>
  );
}
