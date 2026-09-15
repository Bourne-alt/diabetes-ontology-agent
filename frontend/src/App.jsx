import { useEffect, useRef, useState } from 'react';

import { useAgentRun } from './lib/useAgentRun.js';
import TopBar from './components/TopBar.jsx';
import Composer from './components/Composer.jsx';
import Thread from './components/Thread.jsx';
import KnowledgePanel from './components/KnowledgePanel.jsx';
import ErrorBoundary from './components/ErrorBoundary.jsx';

const SAMPLES = [
  { text: '请用容易理解的话，解释演示患者 P90002 的糖化血红蛋白检查结果。', route: '了解检查结果与依据' },
  { text: '如果 P90002 在 2026-02-20 再测一次 A1C 是 7.9%，结论会怎么变？', route: '了解假设成立后的变化' },
  { text: '为什么「糖尿病足」查不到映射？', route: '了解知识库的覆盖范围' },
  { text: 'ICD-10 为 E11 的 ehr-legacy 患者有多少，按风险档位分页列出前 10 个。', route: '查看患者记录' },
];

export default function App() {
  const [message, setMessage] = useState('');
  const [asked, setAsked] = useState(null);
  // 旧轮次留在屏幕上；服务端的上下文由 conversation_id 维持，两者是各自独立的。
  const [history, setHistory] = useState([]);

  const { run, start, stop, newSession, conversationId, busy } = useAgentRun();

  const threadRef = useRef(null);
  const stickRef = useRef(true);
  const inputRef = useRef(null);

  // 内容增长时贴底；用户手动往回翻时不抢滚动条。
  useEffect(() => {
    const node = threadRef.current;
    if (node && stickRef.current) node.scrollTop = node.scrollHeight;
  });

  function pickSample(text) {
    setMessage(text);
    inputRef.current?.focus();
  }

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
    start(text);
  }

  function onScroll(event) {
    const node = event.currentTarget;
    stickRef.current = node.scrollHeight - node.scrollTop - node.clientHeight < 80;
  }

  return (
    <div className="app">
      <TopBar
        model={run.model}
        phase={run.phase}
        statusText={run.statusText}
        modelCalls={run.modelCalls}
        toolCalls={run.toolCalls}
        conversationId={conversationId}
      />

      <div className="body">
        <main className="main">
          <div className="thread scroll" ref={threadRef} onScroll={onScroll}>
            <ErrorBoundary label="会话区渲染失败">
              <Thread
                history={history}
                asked={asked}
                run={run}
                busy={busy}
                samples={SAMPLES}
                onPick={pickSample}
              />
            </ErrorBoundary>
          </div>
          <Composer
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
          <KnowledgePanel key={run.runId ?? "idle"} run={run} />
        </ErrorBoundary>
      </div>
    </div>
  );
}
