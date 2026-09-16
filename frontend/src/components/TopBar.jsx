import { Mark } from './Icons.jsx';
import { MODEL_CALL_LIMIT, TOOL_CALL_LIMIT } from '../lib/runReducer.js';

const TONE = {
  idle: 'idle', connecting: 'running', running: 'running',
  done: 'done', stopped: 'warn', failed: 'bad',
};

function Meter({ used, limit }) {
  const pct = Math.min(100, (used / limit) * 100);
  return (
    <div className="budget__track">
      <div className={'budget__fill' + (used >= limit ? ' is-full' : '')} style={{ width: `${pct}%` }} />
    </div>
  );
}

function shortConversation(id) {
  if (!id) return null;
  return id.length > 10 ? `${id.slice(0, 8)}…` : id;
}

export default function TopBar({
  phase, statusText, modelCalls, toolCalls, conversationId,
}) {
  return (
    <header className="topbar">
      <div className="brand">
        <Mark />
        <div>
          <h1>本体智能体</h1>
          <div className="lbl sub">Ontology Evidence Console</div>
        </div>
      </div>

      <div className="spacer" />

      {conversationId && (
        <span className="chip chip--indigo">会话 {shortConversation(conversationId)}</span>
      )}
      <div className="vrule" />

      <div className="budget">
        <div className="budget__row">
          <span>模型 <b>{modelCalls}</b>/{MODEL_CALL_LIMIT}</span>
          <span>工具 <b>{toolCalls}</b>/{TOOL_CALL_LIMIT}</span>
        </div>
        <div className="budget__bars">
          <Meter used={modelCalls} limit={MODEL_CALL_LIMIT} />
          <Meter used={toolCalls} limit={TOOL_CALL_LIMIT} />
        </div>
      </div>

      <div className="vrule" />
      <div className="status" data-tone={TONE[phase] ?? 'idle'} role="status">
        <span className="status__dot" />
        <span className="status__text">{statusText}</span>
      </div>
    </header>
  );
}
