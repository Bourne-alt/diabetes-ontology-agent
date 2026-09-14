/* POST /chat/stream 的 SSE 客户端。
 *
 * 与框架无关：只负责把字节流切成事件交给 onEvent，成败判定留给调用方。
 * 三条约束直接来自服务端契约：
 *   1. 开流前的失败走 HTTP 状态码（503 初始化失败 / 422 空白输入）。
 *   2. 开流后 HTTP 永远是 200，缺 done 即判本轮作废（当前不支持断线重放）。
 *   3. 帧以 \n\n 分隔，只取 data: 行；其余行（id/event）是冗余信息。
 */

export const CHAT_ENDPOINT = '/chat/stream';

export class StreamAborted extends Error {}

export async function runQuery({ message, conversationId, signal, onEvent }) {
  const response = await fetch(CHAT_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    // 省略 conversation_id 即开新会话，服务端生成并在 run_start 里回传。
    body: JSON.stringify(
      conversationId ? { message, conversation_id: conversationId } : { message },
    ),
    signal,
  });

  if (!response.ok) {
    let detail = '';
    try {
      detail = (await response.json()).detail ?? '';
    } catch {
      /* 非 JSON 响应，用状态码兜底 */
    }
    throw new Error(detail || `请求失败：HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let sawDone = false;

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let split;
    while ((split = buffer.indexOf('\n\n')) >= 0) {
      const frame = buffer.slice(0, split);
      buffer = buffer.slice(split + 2);
      const line = frame.split('\n').find((x) => x.startsWith('data: '));
      if (!line) continue;

      let evt;
      try {
        evt = JSON.parse(line.slice(6));
      } catch {
        continue; // 半帧或脏数据：丢掉这一帧，不让整轮崩掉
      }
      onEvent(evt);
      if (evt.type === 'done') sawDone = true;
    }
  }

  if (!sawDone) throw new Error('连接中断，本轮未完成');
}
