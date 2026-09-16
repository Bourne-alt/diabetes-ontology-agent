import { Mark } from './Icons.jsx';
import Trace from './Trace.jsx';
import Alert from './Alert.jsx';
import TodoList from './TodoList.jsx';
import Answer from './Answer.jsx';
import Evidence from './Evidence.jsx';
import Citations from './Citations.jsx';
import { bagSize } from '../lib/evidence.js';

function shortId(id) {
  if (!id) return null;
  return id.length > 12 ? `${id.slice(0, 6)}…${id.slice(-4)}` : id;
}

export default function Turn({ index, asked, run, live, busy }) {
  const planning = live && busy && run.toolCalls > 0;
  const hasContent =
    run.alert || run.todos.length > 0 || planning || run.draft || run.answer !== null
    || bagSize(run.bag) > 0 || run.bag.gaps.length > 0;

  return (
    <div className="turn">
      <div className="turnmark">
        <span className="lbl turnmark__text">
          第 {index} 轮{index > 1 ? ' · 同一会话，模型看得到前面几轮' : ''}
        </span>
        <span className="turnmark__line" />
        {run.runId && <span className="lbl turnmark__text">run_id {shortId(run.runId)}</span>}
        {!live && <span className="lbl turnmark__text">{run.events.length} events</span>}
      </div>

      <div className="msg msg--user">
        <div className="msg__bubble">{asked}</div>
      </div>

      <div className="msg msg--agent">
        <span className="msg__avatar"><Mark size={17} /></span>
        <div className="msg__stack">
          {live && !hasContent && (
            <div className="todos__empty">
              <span className="pulse" style={{ width: 7, height: 7, borderRadius: '50%', background: '#34477a', display: 'inline-block' }} />
              {run.phase === 'connecting' ? '正在连接…' : '正在选择查询…'}
            </div>
          )}
          <Alert alert={run.alert} />
          <TodoList todos={run.todos} seq={run.todoSeq} planning={planning} />
          <Trace events={run.events} phase={run.phase} />
          <Answer draft={run.draft} answer={run.answer} />
          {run.bag.quotes.length > 0 && <Citations quotes={run.bag.quotes}/>}
          <Evidence bag={run.bag} />
        </div>
      </div>
    </div>
  );
}
