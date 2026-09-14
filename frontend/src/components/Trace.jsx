import { useMemo, useState } from 'react';
import { formatMs } from '../lib/runReducer.js';
import { groupCalls } from '../lib/groupCalls.js';
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

function Grouped({ events }) {
  const calls = useMemo(() => groupCalls(events), [events]);

  if (calls.length === 0) {
    // 说清楚是「没有工具事件」而不是「面板坏了」—— 事件总数一并给出，便于自查。
    return (
      <div className="empty">
        本轮没有工具调用事件（共 {events.length} 个事件）。<br />
        切到「原始事件流」可以看到全部事件。
      </div>
    );
  }

  return (
    <>
      {calls.map((call, i) => {
        const state = call.orphan ? 'fail' : !call.done ? 'running' : call.ok ? 'ok' : 'fail';
        const badge = call.orphan
          ? '缺 tool_start'
          : !call.done ? '进行中' : call.ok ? 'ok' : 'ok=false';
        const spent = call.done && call.startMs !== undefined
          ? formatMs(call.endMs - call.startMs)
          : '';
        return (
          <div className="call" data-state={state} key={`${call.callId ?? 'noid'}:${i}`}>
            <div className="call__head">
              <span className="call__dot" />
              <span className="call__tool">{asText(call.tool)}</span>
              <div className="spacer" />
              <span className="call__badge">{badge}</span>
              <span className="call__ms">{spent}</span>
            </div>
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
                    : '等待同 call_id 的 tool_end。并行调用会交错到达，\n在配对事件到达前保持此状态。'}
                </pre>
              </div>
            </div>
          </div>
        );
      })}
    </>
  );
}

function Flat({ events }) {
  const [open, setOpen] = useState(() => new Set());

  function toggle(seq) {
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(seq)) next.delete(seq);
      else next.add(seq);
      return next;
    });
  }

  return (
    <>
      {events.map((evt) => {
        const isOpen = open.has(evt.seq);
        return (
          <div className="evt" data-bad={String(evt.bad)} data-open={String(isOpen)} key={evt.seq}>
            <button type="button" className="evt__row" aria-expanded={isOpen} onClick={() => toggle(evt.seq)}>
              <span className="evt__seq">{evt.seq}</span>
              <span className="evt__dot" />
              <span className="evt__type">{evt.type}</span>
              <span className="evt__detail">{evt.detail}</span>
              <span className="evt__ms">{evt.ms}</span>
            </button>
            {isOpen && <div className="evt__payload"><pre>{pretty(evt.raw)}</pre></div>}
          </div>
        );
      })}
    </>
  );
}

export default function Trace({ events }) {
  const [view, setView] = useState('grouped');

  return (
    <aside className="trace">
      <div className="trace__head">
        <div className="trace__title">
          <h2>执行轨迹</h2>
          <div className="spacer" />
          <span className="trace__count">{events.length} events</span>
        </div>
        <div className="tabs" role="tablist">
          <button
            type="button" role="tab" className="tab"
            aria-selected={view === 'grouped'} onClick={() => setView('grouped')}
          >按 call_id 归组</button>
          <button
            type="button" role="tab" className="tab"
            aria-selected={view === 'flat'} onClick={() => setView('flat')}
          >原始事件流</button>
        </div>
      </div>

      <div className="trace__body scroll">
        {events.length === 0
          ? <div className="empty">发起查询后，这里逐条显示模型阶段、工具参数与结果。</div>
          : view === 'grouped' ? <Grouped events={events} /> : <Flat events={events} />}
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
    </aside>
  );
}
