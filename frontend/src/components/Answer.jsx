import Section from './Section.jsx';

export default function Answer({ draft, answer }) {
  const final = answer !== null;
  const text = final ? answer : draft;
  if (!text) return null;

  return (
    <Section
      title={<>
        <h2>回答</h2>
        <span className="lbl">{final ? 'event answer' : 'event text_delta'}</span>
      </>}
    >
      {!final && (
        <div className="draftnote">正在流式输出，尚未定稿；最终 answer 事件会整段替换这里。</div>
      )}
      <div className={'answer__body' + (final ? '' : ' is-draft')} aria-live="polite">{text}</div>
    </Section>
  );
}
