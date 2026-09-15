import test from 'node:test';
import assert from 'node:assert/strict';
import {createBag, harvest} from './evidence.js';
import {initialRun, runReducer} from './runReducer.js';

test('full assessment stream event makes citations available in chat',()=>{
  const state=runReducer(initialRun(),{type:'event',at:10,evt:{type:'assessment_report',seq:1,
    report:{report_id:'TA1',claims:[{statement:'结论',evidence_ids:['K1']}],evidence:[{
      kind:'knowledge',evidence_id:'K1',source_file:'source.txt',exact_quote:'逐字依据',content_hash:'h',
    }]}}});
  assert.equal(state.bag.quotes[0].document,'source.txt');
  assert.equal(state.bag.quotes[0].quote,'逐字依据');
});

test('assessment citations preserve document and exact quote, exclude unused and replay copies',()=>{
  const report={report_id:'TA1',claims:[{statement:'检查结论',evidence_ids:['K1']}],
    evidence:[{kind:'knowledge',evidence_id:'K1',source_file:'ontology/knowledges/source.txt',exact_quote:'原文\n第二行',content_hash:'hash'},
      {kind:'knowledge',evidence_id:'K2',exact_quote:'没有引用的内容'}],
    execution_trace:{steps:[{quote:'过程内重复内容',sha256:'other'}]}};
  const bag=harvest(report,'assessment',createBag());
  assert.equal(bag.quotes.length,1);
  assert.equal(bag.quotes[0].document,'ontology/knowledges/source.txt');
  assert.equal(bag.quotes[0].quote,'原文\n第二行');
  assert.equal(bag.quotes[0].supports,'检查结论');
  const compact={...report,evidence_defaults_by_kind:{knowledge:{source_file:'ontology/knowledges/source.txt'}},
    evidence:[{kind:'knowledge',evidence_id:'K1',exact_quote:'原文\n第二行',content_hash:'hash'}]};
  harvest(compact,'assessment',bag);
  assert.equal(bag.quotes.length,1);
});

test('legacy quotes keep distinct documents even with equal hashes and tolerate missing names',()=>{
  const bag=harvest({sources:[{quote:'原文',sha256:'hash',localFile:'a.txt'},
    {quote:'原文',sha256:'hash',localFile:'b.txt'},{quote:'无文件名',sha256:null}]},'patient_evidence',createBag());
  assert.equal(bag.quotes.length,3);
  assert.equal(bag.quotes[2].document,'');
});
