/* 从工具返回里提取证据。只认已知字段，认不出就不编。
 *
 * 两个容易踩的点，都是真实返回体教出来的：
 *   - 诊断状态那条 inferredFacts 只有 verificationStatus，没有 ruleId；
 *     按 ruleId 取会把「Provisional 不是确诊」整条丢掉。
 *   - caveat 跟着事实一起展示后，就不该再重复进「服务端告示」。
 */

import { asText } from './text.js';

const GAP_KEYS = ['unmapped', 'monitoringGaps', 'brokenLinks', 'insufficient_reason', 'notes'];
const NOTICE_KEYS = ['dataQualityNotice', 'disclaimer', 'caveat'];

export function createBag() {
  return { quotes: [], inferred: [], asserted: [], patients: [], gaps: [], notices: [], seen: new Set() };
}

export function cloneBag(bag) {
  return {
    quotes: [...bag.quotes],
    inferred: [...bag.inferred],
    asserted: [...bag.asserted],
    patients: [...bag.patients],
    gaps: [...bag.gaps],
    notices: [...bag.notices],
    seen: new Set(bag.seen),
  };
}

export function bagSize(bag) {
  return bag.quotes.length + bag.inferred.length + bag.asserted.length;
}

function once(bag, list, key, value) {
  if (bag.seen.has(key)) return;
  bag.seen.add(key);
  list.push(value);
}

function stringify(value) {
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

/** 就地写入 bag（调用方负责先 cloneBag）。 */
export function harvest(result, tool, bag, depth = 0) {
  if (depth > 4 || result === null || typeof result !== 'object') return bag;

  if (Array.isArray(result)) {
    for (const item of result.slice(0, 60)) harvest(item, tool, bag, depth + 1);
    return bag;
  }

  // 逐字出处：quote + 完整 sha256
  if (typeof result.quote === 'string' && typeof result.sha256 === 'string') {
    once(bag, bag.quotes, `q:${result.sha256}`, {
      quote: result.quote,
      sha256: result.sha256,
      supports: asText(result.supports ?? result.citedBy) || null,
      tool,
    });
  }

  // 推理结论：带 ruleId 的规则命中，或只带 verificationStatus 的诊断状态
  if (typeof result.ruleId === 'string' || typeof result.verificationStatus === 'string') {
    const caveat = typeof result.caveat === 'string' && result.caveat.trim() ? result.caveat : null;
    if (caveat) bag.seen.add(`n:caveat:${caveat.slice(0, 60)}`);

    const key = result.ruleId ?? result.type ?? 'status';
    once(bag, bag.inferred, `r:${key}:${result.conclusion ?? result.type ?? ''}`, {
      ruleId: asText(result.ruleId) || null,
      ruleVersion: asText(result.ruleVersion) || null,
      conclusion: asText(result.conclusion ?? result.type) || null,
      verificationStatus: asText(result.verificationStatus) || null,
      confirmationRequired: result.confirmationRequired === undefined || result.confirmationRequired === null
        ? null
        : String(result.confirmationRequired),
      interval: asText(result.interval) || null,
      appliesThreshold: asText(result.appliesThreshold) || null,
      applicableContext: asText(result.applicableContext) || null,
      basedOn: result.basedOn ?? null,
      caveat,
      tool,
    });
  }

  // 原始事实行：带 sqlRow，或带 trust 的测量
  if (result.sqlRow || (result.trust !== undefined && result.value !== undefined)) {
    const trust = asText(result.trust ?? result.trust_level).trim();
    once(bag, bag.asserted, `a:${result.iri ?? stringify(result.sqlRow ?? result.value)}`, {
      iri: asText(result.iri) || null,
      test: asText(result.test ?? result.testcode) || null,
      value: asText(result.value) || null,
      unit: asText(result.unit) || null,
      sourceValue: asText(result.sourceValue) || null,
      sourceUnit: asText(result.sourceUnit) || null,
      trust: trust || null,
      origin: asText(result.origin ?? result.fact_origin) || null,
      sqlRow: result.sqlRow ?? null,
      unverified: /^unverified$/i.test(trust),
      tool,
    });
  }

  // 患者身份与来源
  if (typeof result.patientid === 'string') {
    once(bag, bag.patients, `p:${result.patientid}`, {
      patientid: result.patientid,
      origin: asText(result.fact_origin) || null,
      tier: asText(result.tier) || null,
      sourceTable: asText(result.source_table) || null,
      tool,
    });
  }

  // 缺口：零行不是正常，未排除的原因必须单列
  for (const key of GAP_KEYS) {
    const raw = result[key];
    if (raw === undefined || raw === null) continue;
    const items = Array.isArray(raw) ? raw : [raw];
    items.slice(0, 30).forEach((item, i) => {
      const text = typeof item === 'string' ? item : stringify(item);
      if (!text || text === '[]' || text === '{}') return;
      once(bag, bag.gaps, `g:${key}:${text.slice(0, 80)}${i}`, { field: key, text });
    });
  }

  // 告示：按原文保留，不改写不摘要
  for (const key of NOTICE_KEYS) {
    if (typeof result[key] === 'string' && result[key].trim()) {
      once(bag, bag.notices, `n:${key}:${result[key].slice(0, 60)}`, { field: key, text: result[key] });
    }
  }

  for (const value of Object.values(result)) {
    if (value && typeof value === 'object') harvest(value, tool, bag, depth + 1);
  }
  return bag;
}
