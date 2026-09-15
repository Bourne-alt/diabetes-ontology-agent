// Evidence graph projection: only known response fields create edges.
// No relationships are inferred from co-occurrence or from the model's prose.
const uri = (v) => typeof v === 'string' && /^(https?:\/\/|urn:|dmo:)/.test(v);
const text = (v) => typeof v === 'string' ? v : '';
const tail = (v) => text(v).split(/[/#]/).pop() || text(v);
export const KIND = {
  patient: { label: '患者', color: '#5b9fc7' },
  fact: { label: '检查与记录', color: '#58b8b1' },
  concept: { label: '本体概念', color: '#729d85' },
  rule: { label: '判断规则', color: '#9f8bc3' },
  evidence: { label: '指南出处', color: '#d8a064' },
};
function kindOf(kind = '') {
  if (/Patient/i.test(kind)) return 'patient';
  if (/LabResult|Observation|MedicationUse/i.test(kind)) return 'fact';
  if (/Passage|Source/i.test(kind)) return 'evidence';
  if (/threshold|target|risk$|Rule|Assessment|Diagnosis/i.test(kind)) return 'rule';
  return 'concept';
}
export function graphFromEvents(events, through = Infinity) {
  const nodes = new Map(), edges = new Map();
  const notices = new Set();
  let clipped = false;
  for (const event of events) {
    const raw = event.raw ?? event;
    if (raw.seq > through || raw.type !== 'tool_end' || raw.ok !== true) continue;
    const payload = raw.result?.data ?? raw.result;
    if (!payload || typeof payload !== 'object' || payload.ok === false) continue;
    // Conditional results must never merge into the actual-patient graph.
    const scenario = raw.tool === 'simulate_patient_course';
    const scope = scenario ? `scenario:${raw.call_id}:` : '';
    const provenance = { tool: raw.tool, callId: raw.call_id, seq: raw.seq, scenario };
    function add(id, label, kind = 'concept', detail = {}) {
      if (!id || typeof id !== 'string') return null;
      const key = scope + id;
      if (!nodes.has(key) && nodes.size >= 70) { clipped = true; return null; }
      const old = nodes.get(key);
      nodes.set(key, { ...old, id: key, ref: id,
        label: label || old?.label || tail(id), kind: old?.kind !== 'concept' && old?.kind ? old.kind : kind,
        detail: { ...old?.detail, ...detail }, ...provenance });
      return key;
    }
    function link(from, to, label, detail = {}) {
      if (!from || !to || from === to || !nodes.has(from) || !nodes.has(to)) return;
      if (edges.size >= 120) { clipped = true; return; }
      const id = `${from}|${label}|${to}`;
      edges.set(id, { id, from, to, label, ...provenance, ...detail });
    }
    function walk(o, path = 'data', depth = 0) {
      if (!o || typeof o !== 'object' || depth > 12) return;
      if (Array.isArray(o)) { o.forEach((v, i) => walk(v, `${path}.${i}`, depth + 1)); return; }
      // Explicit patient bundle membership: API association, not a fabricated RDF predicate.
      if (o.patient?.patientid) {
        const p = add(`patient:${o.patient.patientid}`, `患者 ${o.patient.patientid}`, 'patient', o.patient);
        for (const f of o.assertedFacts ?? []) {
          const fId = add(f.iri, f.test || f.kind, 'fact', f);
          link(p, fId, '患者检查记录', { relationType: 'API 返回的归属关系' });
        }
      }
      if (uri(o.iri)) add(o.iri, o.label || o.code, kindOf(o.kind), o);
      if (o.iri && o.kind === 'LabResult') add(o.iri, o.test || '检验记录', 'fact', o);
      if (o.ruleId) {
        const rule = add(`rule:${o.ruleId}`, o.label || o.ruleId, 'rule', o);
        if (uri(o.iri)) link(rule, add(o.iri, o.label, 'rule', o), '对应本体节点', { relationType: 'API 标识映射' });
        if (o.basedOn?.labResultId) {
          const fact = add(o.basedOn.labResultId, '检验记录', 'fact', o.basedOn);
          link(fact, rule, '作为判定依据', { relationType: 'API basedOn' });
        }
        if (o.appliesThreshold) link(rule, add(`rule:${o.appliesThreshold}`, o.appliesThreshold, 'rule'), '使用阈值');
        for (const passage of o.citesPassages ?? []) {
          link(rule, add(`passage:${passage}`, '指南原文', 'evidence', { passageId: passage }), '引用出处');
        }
      }
      if (o.quote && o.sha256) {
        const source = add(`quote:${o.sha256}`, '指南原文', 'evidence', o);
        if (typeof o.supports === 'string' && o.supports) {
          link(add(`rule:${o.supports}`, o.supports, 'rule'), source, '有原文支持', { relationType: 'API supports' });
        }
      }
      if (uri(o.iri)) {
        const center = add(o.iri, o.label, kindOf(o.kind), o);
        for (const n of o.neighbors ?? []) {
          if (!uri(n.iri) || !n.predicate) continue;
          const neighbor = add(n.iri, n.label, 'concept', n);
          const from = o.direction === 'in' ? neighbor : center;
          const to = o.direction === 'in' ? center : neighbor;
          link(from, to, n.short || tail(n.predicate), { predicate: n.predicate, inferredOnly: n.inferredOnly });
        }
        for (const direction of ['outgoing', 'incoming']) {
          for (const n of o[direction] ?? []) {
            if (!uri(n.sample) || !n.predicate) continue;
            const neighbor = add(n.sample, n.sampleLabel, 'concept', { sample: true });
            link(direction === 'incoming' ? neighbor : center, direction === 'incoming' ? center : neighbor,
              n.short || tail(n.predicate), { predicate: n.predicate, sample: true });
          }
        }
      }
      if (Array.isArray(o.path) && o.found === true) {
        for (const edge of o.path) {
          if (!uri(edge.from) || !uri(edge.to) || !edge.predicate) continue;
          const a = add(edge.from), b = add(edge.to);
          link(edge.direction === 'in' ? b : a, edge.direction === 'in' ? a : b,
            edge.short || tail(edge.predicate), { predicate: edge.predicate });
        }
      }
      for (const field of ['brokenLinks', 'unmapped', 'monitoringGaps']) {
        if (Array.isArray(o[field]) && o[field].length) notices.add('有证据缺口，图谱并不完整，请查看回答中的限制。');
      }
      if (o.truncated || o.frontierTruncated) notices.add('工具返回了部分图数据，未展示完整本体。');
      for (const [k, v] of Object.entries(o)) {
        if (['nextHops', 'outgoing', 'incoming', 'neighbors', 'path', 'brokenLinks'].includes(k)) continue;
        if (v && typeof v === 'object') walk(v, `${path}.${k}`, depth + 1);
      }
    }
    walk(payload);
    if (scenario && nodes.size) notices.add('带“假设”标签的节点来自条件推演，不是患者已发生的事实。');
  }
  return { nodes: [...nodes.values()], edges: [...edges.values()], notices: [...notices], clipped };
}
