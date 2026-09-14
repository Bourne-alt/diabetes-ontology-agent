import { MAX_MESSAGE } from '../lib/limits.js';

export default function Composer({
  inputRef, value, onChange, onSubmit, onStop, onNewSession, busy, canReset,
}) {
  function submit(event) {
    event.preventDefault();
    const message = value.trim();
    if (!message || busy) return;
    onSubmit(message);
  }

  return (
    <form className="composer" onSubmit={submit}>
      <label className="lbl hidden" htmlFor="message">查询内容</label>
      <textarea
        id="message"
        ref={inputRef}
        rows={2}
        maxLength={MAX_MESSAGE}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') submit(e);
        }}
        placeholder="输入用户的问题。首轮请写明患者编号，同一会话内可以直接追问。"
      />
      <div className="composer__foot">
        <button className="btn btn--primary" type="submit" disabled={busy || !value.trim()}>开始查询</button>
        <button className="btn btn--ghost" type="button" onClick={onStop} disabled={!busy}>停止</button>
        <button className="btn btn--ghost" type="button" onClick={onNewSession} disabled={!canReset}>新会话</button>
        <span className="composer__hint">⌘/Ctrl + Enter 发送</span>
        <div className="spacer" />
        <span className={'counter' + (value.length > MAX_MESSAGE ? ' is-over' : '')}>
          {value.length} / {MAX_MESSAGE}
        </span>
      </div>
    </form>
  );
}
