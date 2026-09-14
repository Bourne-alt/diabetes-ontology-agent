/* 把任意工具返回的值压成可渲染文本。
 *
 * 为什么需要：证据字段（conclusion / supports / test / iri / tier …）在真实返回体里
 * 既可能是字符串，也可能是概念对象 {kind, id, iri}。直接塞进 JSX 会抛
 * "Objects are not valid as a React child" 并让整页白屏。渲染层不许假设形状。
 */

// 对象取这些键当显示名，按顺序优先。
const LABEL_KEYS = ['label', 'name', 'title', 'iri', 'id', 'code', 'value', 'text'];

export function asText(value) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);

  if (Array.isArray(value)) {
    return value.map(asText).filter(Boolean).join('、');
  }

  if (typeof value === 'object') {
    for (const key of LABEL_KEYS) {
      const inner = value[key];
      if (typeof inner === 'string' && inner.trim()) return inner;
      if (typeof inner === 'number') return String(inner);
    }
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }

  return String(value);
}

/** 用于 meta 行：对象压成一行 JSON，字符串原样。 */
export function asCompact(value) {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value).replace(/\s+/g, ' ');
  } catch {
    return String(value);
  }
}

/** 非空文本才返回，否则 null —— 方便 JSX 里直接做条件渲染。 */
export function asTextOrNull(value) {
  const text = asText(value);
  return text ? text : null;
}
