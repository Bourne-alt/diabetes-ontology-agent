import test from 'node:test';
import assert from 'node:assert/strict';
import { graphFromEvents } from './knowledgeGraph.js';
import { splitAnswer } from './answerSections.js';

const iri = (name) => `https://example.test/${name}`;
const evt = (data, seq=1, tool='explore_concept') => ({type:'tool_end',seq,call_id:`c${seq}`,tool,ok:true,result:{ok:true,data}});
test('only explicit relations become edges; narrative and failed tools are ignored', () => {
  const concept = evt({concepts:[{iri:iri('a'),label:'概念 A'},{iri:iri('b'),label:'概念 B'}]});
  const graph = graphFromEvents([concept, {type:'answer',text:'A 导致 B'}, {...evt({iri:iri('bad')}),ok:false}]);
  assert.equal(graph.nodes.length,2); assert.equal(graph.edges.length,0);
});
test('incoming graph edge retains direction and predicate', () => {
  const graph = graphFromEvents([evt({iri:iri('a'),direction:'in',neighbors:[{iri:iri('b'),label:'B',predicate:iri('p'),short:'p',inferredOnly:true}]})]);
  assert.equal(graph.edges[0].from,iri('b')); assert.equal(graph.edges[0].to,iri('a'));
  assert.equal(graph.edges[0].predicate,iri('p')); assert.equal(graph.edges[0].inferredOnly,true);
});
test('patient bundle connects only explicit lab and supporting rule facts', () => {
  const graph = graphFromEvents([evt({patient:{patientid:'TEST',fact_origin:'demo-cohort'},
    assertedFacts:[{iri:'lab:1',kind:'LabResult',test:'A1C',trust:'Unverified'}],
    inferredFacts:[{ruleId:'r1',basedOn:{labResultId:'lab:1'},appliesThreshold:'t1'}],
    sources:[{quote:'test quote',sha256:'testhash',supports:'t1'}]},1,'patient_evidence')]);
  assert.equal(graph.edges.length,4);
  assert.equal(graph.nodes.find(n=>n.ref==='lab:1').detail.trust,'Unverified');
  assert.ok(graph.edges.every(e=>graph.nodes.some(n=>n.id===e.from)&&graph.nodes.some(n=>n.id===e.to)));
});
test('hypotheses cannot merge into actual patient facts; replay excludes later evidence', () => {
  const data={iri:iri('a'),label:'检查'};
  const events=[evt(data,1),evt(data,2,'simulate_patient_course')];
  const graph=graphFromEvents(events);
  assert.equal(graph.nodes.length,2); assert.equal(graph.nodes.filter(n=>n.scenario).length,1);
  assert.equal(graphFromEvents(events,1).nodes.length,1);
  assert.equal(graphFromEvents(events,0).nodes.length,0);
});
test('path traversal direction and sample-only node edges stay explicit', () => {
  const graph=graphFromEvents([evt({found:true,path:[{from:iri('a'),to:iri('b'),predicate:iri('p'),direction:'in'}]}),
    evt({iri:iri('c'),outgoing:[{sample:'literal-value',predicate:iri('p')} ]},2)]);
  assert.equal(graph.edges.length,1); assert.equal(graph.edges[0].from,iri('b'));
});
test('graph rendering budget is explicit', () => {
  const graph=graphFromEvents([evt({concepts:Array.from({length:90},(_,i)=>({iri:iri(String(i))}))})]);
  assert.equal(graph.nodes.length,70);assert.equal(graph.clipped,true);
});
test('technical detail collapse never absorbs a later warning section', () => {
  const text='## 简单说\n这是演示数据。\n## 技术与证据详情\n原文和哈希\n## 还需要注意什么\n条件没有发生。';
  const parts=splitAnswer(text);
  assert.match(parts.main,/条件没有发生/);assert.match(parts.main,/演示数据/);
  assert.match(parts.technical,/原文和哈希/);assert.doesNotMatch(parts.main,/原文和哈希/);
});
