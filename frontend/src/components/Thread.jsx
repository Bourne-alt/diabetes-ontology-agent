import { Mark } from './Icons.jsx';
import Turn from './Turn.jsx';
import ErrorBoundary from './ErrorBoundary.jsx';

function Empty({ samples, onPick }) {
  return (
    <div className="thread__empty">
      <Mark size={34} />
      <h2>在下方输入用户的问题</h2>
      <p>
        同一会话内模型看得到之前几轮，可以直接追问；换新会话即清空，两个会话之间不共享任何内容。
        回答与证据链按本轮工具实际返回的内容显示，取不到就不显示。
      </p>
      <div className="samples">
        {samples.map((s) => (
          <button key={s.text} type="button" className="sample" onClick={() => onPick(s.text)}>
            <span className="sample__text">{s.text}</span>
            <span className="sample__route">{s.route}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export default function Thread({ history, asked, run, busy, samples, onPick }) {
  if (history.length === 0 && !asked) return <Empty samples={samples} onPick={onPick} />;

  return (
    <>
      {history.map((turn, i) => (
        <ErrorBoundary key={turn.id} label={`第 ${i + 1} 轮渲染失败`}>
          <Turn index={i + 1} asked={turn.asked} run={turn.run} live={false} />
        </ErrorBoundary>
      ))}
      {asked !== null && (
        <ErrorBoundary key={`live:${run.runId ?? 'pending'}`} label={`第 ${history.length + 1} 轮渲染失败`}>
          <Turn index={history.length + 1} asked={asked} run={run} live busy={busy} />
        </ErrorBoundary>
      )}
    </>
  );
}
