import { useEffect, useRef, useState } from 'react';

import { useAgentRun } from './lib/useAgentRun.js';
import TopBar from './components/TopBar.jsx';
import Composer from './components/Composer.jsx';
import Thread from './components/Thread.jsx';
import KnowledgePanel from './components/KnowledgePanel.jsx';
import ErrorBoundary from './components/ErrorBoundary.jsx';

export default function App() {
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [modelError, setModelError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    fetch('/chat/models', { signal: controller.signal })
      .then(response => { if (!response.ok) throw new Error('无法读取模型配置'); return response.json(); })
      .then(data => { setModels(data.models); setSelectedModel(data.default_model); })
      .catch(error => { if (error.name !== 'AbortError') setModelError(error.message); });
    return () => controller.abort();
  }, []);
  const [message, setMessage] = useState('');
  const [asked, setAsked] = useState(null);
  // 旧轮次留在屏幕上；服务端的上下文由 conversation_id 维持，两者是各自独立的。
  const [history, setHistory] = useState([]);

  const { run, start, stop, newSession, busy } = useAgentRun();

  const threadRef = useRef(null);
  const stickRef = useRef(true);
  const inputRef = useRef(null);

  // 内容增长时贴底；用户手动往回翻时不抢滚动条。
  useEffect(() => {
    const node = threadRef.current;
    if (node && stickRef.current) node.scrollTop = node.scrollHeight;
  });

  function resetSession() {
    newSession();
    setHistory([]);
    setAsked(null);
    stickRef.current = true;
  }

  function submit(text) {
    if (asked !== null) {
      const finished = { id: run.runId ?? `turn-${history.length}`, asked, run };
      setHistory((prev) => [...prev, finished]);
    }
    setAsked(text);
    setMessage('');
    stickRef.current = true;
    start(text, selectedModel);
  }

  function onScroll(event) {
    const node = event.currentTarget;
    stickRef.current = node.scrollHeight - node.scrollTop - node.clientHeight < 80;
  }

  return (
    <div className="app">
      <TopBar />

      <div className="body">
        <main className="main">
          <div className="thread scroll" ref={threadRef} onScroll={onScroll}>
            <ErrorBoundary label="会话区渲染失败">
              <Thread
                history={history}
                asked={asked}
                run={run}
                busy={busy}
              />
            </ErrorBoundary>
          </div>
          <Composer
            models={models}
            selectedModel={selectedModel}
            actualModel={asked !== null ? run.model : null}
            modelError={modelError}
            onModelChange={(model) => { resetSession(); setSelectedModel(model); }}
            inputRef={inputRef}
            value={message}
            onChange={setMessage}
            onSubmit={submit}
            onStop={stop}
            onNewSession={resetSession}
            busy={busy}
            canReset={asked !== null || history.length > 0}
          />
        </main>

        <ErrorBoundary label="知识图谱渲染失败">
          {asked !== null && <KnowledgePanel run={run} history={history} />}
        </ErrorBoundary>
      </div>
    </div>
  );
}
