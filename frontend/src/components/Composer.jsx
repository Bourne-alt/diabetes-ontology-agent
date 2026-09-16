import { MAX_MESSAGE } from '../lib/limits.js';

export default function Composer({
  models, selectedModel, actualModel, modelError, onModelChange,
  inputRef, value, onChange, onSubmit, onStop, onNewSession, busy, canReset,
}) {
  function submit(event) {
    event.preventDefault();
    const message = value.trim();
    if (!message || busy || !selectedModel || modelError) return;
    onSubmit(message);
  }

  return (
    <form className="composer" onSubmit={submit}>
      <div className="composer__models">
        <label htmlFor="chat-model">模型</label>
        <select id="chat-model" value={selectedModel} onChange={e => onModelChange(e.target.value)} disabled={busy || !models.length}>
          {!models.includes(selectedModel) && <option value={selectedModel}>{selectedModel || '读取配置中…'}</option>}
          {models.map(model => <option key={model} value={model}>{model}</option>)}
        </select>
        <span>{actualModel ? `本轮使用：${actualModel}` : '默认读取服务端配置'}</span>
        <span>切换模型将开启新会话</span>
        {modelError && <span role="alert">{modelError}</span>}
      </div>
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
        <button className="btn btn--primary" type="submit" disabled={busy || !value.trim() || !selectedModel || Boolean(modelError)}>开始查询</button>
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
