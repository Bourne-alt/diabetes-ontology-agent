/* 一轮查询的全部状态。纯 reducer：事件进，快照出。
 * 时间戳由调用方随 action 传入（at），reducer 自己不读时钟。 */

import { cloneBag, createBag, harvest } from './evidence.js';
import { asText } from './text.js';
import { toolLabel } from './toolLabels.js';

// 与 AgentSettings 的默认值保持一致（src/agent/settings.py）。
// 服务端目前没有在事件里公开预算上限；改了那边记得同步这里。
export const MODEL_CALL_LIMIT = 12;
export const TOOL_CALL_LIMIT = 24;

export function initialRun() {
  return {
    runId: null,
    conversationId: null,
    model: null,
    phase: 'idle', // idle | connecting | running | done | stopped | failed
    statusText: '等待查询',
    alert: null,
    startedAt: 0,
    elapsed: null,
    modelCalls: 0,
    toolCalls: 0,
    events: [],
    todos: [],
    todoSeq: null,
    draft: '',
    answer: null,
    bag: createBag(),
  };
}

export function formatMs(ms) {
  if (!Number.isFinite(ms)) return '';
  return ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(1)}s`;
}

function withEvent(state, evt, detail, bad, at) {
  return {
    ...state,
    events: [
      ...state.events,
      {
        seq: evt.seq,
        type: asText(evt.type),
        detail: asText(detail),
        bad: Boolean(bad),
        atMs: at - state.startedAt,
        ms: formatMs(at - state.startedAt),
        raw: evt,
      },
    ],
  };
}

export function runReducer(state, action) {
  switch (action.type) {
    case 'start':
      return { ...initialRun(), phase: 'connecting', statusText: '正在连接', startedAt: action.at };

    case 'stopped':
      return {
        ...state,
        phase: 'stopped',
        statusText: '已停止请求',
        alert: {
          kind: 'warn',
          title: '已停止请求 · 后台可能仍在收尾',
          text: '前端已断开连接，取消会向模型流传播；但已经开始的 DMO / SQL 工作会继续跑到各自的超时。本轮没有最终回答，已收到的部分证据保留在下方供排查。',
        },
      };

    case 'failed':
      return {
        ...state,
        phase: 'failed',
        statusText: action.message,
        alert: { kind: 'bad', title: '本轮未完成', text: action.message },
      };

    case 'event':
      return applyEvent(state, action.evt, action.at);

    default:
      return state;
  }
}

function applyEvent(state, evt, at) {
  switch (evt.type) {
    case 'run_start':
      return withEvent(
        {
          ...state,
          runId: asText(evt.run_id) || null,
          conversationId: asText(evt.conversation_id) || null,
          model: asText(evt.model) || null,
          phase: 'running',
          statusText: '开始查询',
        },
        evt, evt.message ?? '开始查询', false, at,
      );

    case 'model_start':
      return withEvent(
        { ...state, modelCalls: state.modelCalls + 1, phase: 'running', statusText: '正在选择查询或组织回答' },
        evt, asText(evt.message), false, at,
      );

    // 增量不进轨迹列表，否则会把工具事件淹掉。
    case 'text_delta':
      return { ...state, draft: state.draft + asText(evt.text) };

    case 'todo_update': {
      const todos = Array.isArray(evt.todos) ? evt.todos : [];
      const done = todos.filter((t) => t.status === 'completed').length;
      return withEvent(
        { ...state, todos, todoSeq: evt.seq },
        evt, `${todos.length} 项 · ${done} 已完成`, false, at,
      );
    }

    case 'tool_start':
      return withEvent(
        {
          ...state,
          toolCalls: state.toolCalls + 1,
          phase: 'running',
          statusText: toolLabel(evt.tool),
        },
        evt, asText(evt.tool), false, at,
      );

    case 'tool_end': {
      const failed = evt.ok === false;
      const bag = failed ? state.bag : harvest(evt.result, evt.tool, cloneBag(state.bag));
      return withEvent(
        { ...state, bag },
        evt, `${asText(evt.tool)} · ${failed ? 'ok=false' : 'ok'}`, failed, at,
      );
    }

    case 'answer':
      return withEvent({ ...state, answer: asText(evt.text) }, evt, '最终回答，整段替换增量区', false, at);

    case 'error':
      return withEvent(
        {
          ...state,
          phase: 'failed',
          statusText: asText(evt.message) || '本轮未完成',
          alert: { kind: 'bad', title: '本轮未完成', text: asText(evt.message) || '未提供错误说明。' },
        },
        evt, asText(evt.message) || asText(evt.code), true, at,
      );

    case 'done': {
      const completed = evt.status === 'completed';
      return withEvent(
        {
          ...state,
          phase: completed ? 'done' : 'failed',
          elapsed: at - state.startedAt,
          statusText: completed ? `查询完成 · ${formatMs(at - state.startedAt)}` : '本轮未完成',
        },
        evt, `status ${asText(evt.status)}`, !completed, at,
      );
    }

    default:
      return withEvent(state, evt, '', false, at);
  }
}
