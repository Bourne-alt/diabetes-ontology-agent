import { useState } from 'react';

function Caret({ open }) {
  return (
    <span className="sect__caret" data-open={String(open)} aria-hidden="true">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M6 9.5 12 15.5 18 9.5" />
      </svg>
    </span>
  );
}

/** 会话里的可折叠模块。标题行整条可点，折起后只留标题与右侧摘要。 */
export default function Section({
  className = 'card',
  title,
  right,
  children,
  defaultOpen = true,
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className={className}>
      <button
        type="button"
        className="sect__head"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Caret open={open} />
        <span className="sect__title">{title}</span>
        <div className="spacer" />
        {right}
      </button>
      {open && <div className="sect__body">{children}</div>}
    </section>
  );
}
