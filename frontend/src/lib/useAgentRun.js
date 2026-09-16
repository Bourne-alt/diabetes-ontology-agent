import { useCallback, useReducer, useRef, useState } from 'react';

import { runQuery } from './stream.js';
import { initialRun, runReducer } from './runReducer.js';

export function useAgentRun() {
  const [run, dispatch] = useReducer(runReducer, undefined, initialRun);
  const [conversationId, setConversationId] = useState(null);
  const abortRef = useRef(null);
  const conversationRef = useRef(null);

  const start = useCallback(async (message, model) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    dispatch({ type: 'start', at: performance.now() });

    try {
      await runQuery({
        message,
        model,
        conversationId: conversationRef.current,
        signal: controller.signal,
        onEvent: (evt) => {
          // 首轮由服务端生成 conversation_id，之后每次请求带回去续上同一段对话。
          if (
            evt.type === 'run_start'
            && evt.conversation_id
            && conversationRef.current !== evt.conversation_id
          ) {
            conversationRef.current = evt.conversation_id;
            setConversationId(evt.conversation_id);
          }
          dispatch({ type: 'event', evt, at: performance.now() });
        },
      });
    } catch (err) {
      if (err.name === 'AbortError') dispatch({ type: 'stopped' });
      else dispatch({ type: 'failed', message: err.message });
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, []);

  const stop = useCallback(() => abortRef.current?.abort(), []);

  // 开新会话：丢掉 conversation_id，服务端那边的旧会话由 LRU 自行回收。
  const newSession = useCallback(() => {
    abortRef.current?.abort();
    conversationRef.current = null;
    setConversationId(null);
  }, []);

  const busy = run.phase === 'connecting' || run.phase === 'running';
  return { run, start, stop, newSession, conversationId, busy };
}
