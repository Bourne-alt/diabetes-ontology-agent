import { Check } from './Icons.jsx';
import Section from './Section.jsx';
import { asText } from '../lib/text.js';

const LABEL = { pending: '待处理', in_progress: '进行中', completed: '已完成' };

export default function TodoList({ todos }) {
  if (todos.length === 0) return null;

  const done = todos.filter((t) => t.status === 'completed').length;
  const pct = Math.round((done / todos.length) * 100);

  // 只脉冲第一个 in_progress —— 同时亮多个会让当前步骤失焦。
  let pulsed = false;

  return (
    <Section
      title={<>
        <span className="lbl">待办清单</span>
        <span className="chip chip--indigo">本轮查询计划</span>
      </>}
      right={<>
        <span className="todos__pct">{pct}%</span>
        <span className="todos__ratio">{done} / {todos.length} 已完成</span>
      </>}
    >
      <div className="todos__track"><div className="todos__fill" style={{ width: `${pct}%` }} /></div>

      <div className="todos__list">
        {todos.map((todo, i) => {
          const status = LABEL[todo.status] ? todo.status : 'pending';
          const running = status === 'in_progress';
          const showPulse = running && !pulsed;
          if (running) pulsed = true;
          return (
            <div className="todo" data-status={status} key={`${i}:${asText(todo.content)}`}>
              <span className="todo__mark">
                {status === 'completed' && <Check />}
                {running && (
                  <span
                    className={showPulse ? 'pulse' : undefined}
                    style={{ width: 6, height: 6, borderRadius: '50%', background: '#34477a' }}
                  />
                )}
              </span>
              <span className="todo__text">{asText(todo.content)}</span>
              <span className="todo__tag lbl">{LABEL[status]}</span>
            </div>
          );
        })}
      </div>
    </Section>
  );
}
