import { Mark } from './Icons.jsx';
import Turn from './Turn.jsx';
import ErrorBoundary from './ErrorBoundary.jsx';

function Empty({ samples, onPick }) {
  return (
    <div className="thread__empty">
      <Mark size={34} />
      <h2>把复杂的检查结果，讲清楚。</h2>
      <p>
        先说清楚结论，再告诉你依据和还不确定的地方。
        你可以继续追问；右侧图谱会逐步呈现实际查到的资料与联系。
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
