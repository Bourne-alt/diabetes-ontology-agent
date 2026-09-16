import { useId } from 'react';
import Turn from './Turn.jsx';
import ErrorBoundary from './ErrorBoundary.jsx';

function Empty() {
  const id = useId();
  return (
    <div className="thread__empty">
      <div className="welcome-art" aria-hidden="true">
        <svg className="welcome-art__scene" viewBox="0 0 1254 1254" fill="none">
          <defs>
            <clipPath id={`${id}-sphere`}><ellipse cx="627" cy="608" rx="496" ry="491" /></clipPath>
          </defs>
          <g className="welcome-art__sphere">
            <image href="/welcome/sphere.png" width="1254" height="1254" clipPath={`url(#${id}-sphere)`} />
          </g>
        </svg>
      </div>
      <h2>世界是一张图</h2>
      <p>患者分析 · 本体关联 · 证据追溯</p>
    </div>
  );
}

export default function Thread({ history, asked, run, busy }) {
  if (history.length === 0 && !asked) return <Empty />;

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
