import { lazy, Suspense, useMemo, useState } from 'react';
import { graphFromEvents, KIND } from '../lib/knowledgeGraph.js';
import { groupCalls } from '../lib/groupCalls.js';
import { toolLabel } from '../lib/toolLabels.js';
import Trace from './Trace.jsx';
const GraphScene = lazy(() => import('./GraphScene.jsx'));

export default function KnowledgePanel({ run }) {
  const [tab, setTab] = useState('graph');
  const [paused, setPaused] = useState(false);
  const [selected, setSelected] = useState(null);
  const [replay, setReplay] = useState(null);
  const through = replay ?? Infinity;
  const graph = useMemo(() => graphFromEvents(run.events, through), [run.events, through]);
  const calls = useMemo(() => groupCalls(run.events), [run.events]);
  const node = graph.nodes.find(n => n.id === selected);
  const lastSeq = run.events.at(-1)?.seq ?? 0;
  const current = calls.at(-1);
  const stage = run.answer !== null ? 3 : !current ? 0
    : /rule|passage|path|simulat|evidence/.test(current.tool) ? 2
    : /concept|term/.test(current.tool) ? 1 : 0;
  return <aside className="knowledge-panel">
    <header className="knowledge-head"><div><span className="eyebrow">让依据看得见</span><h2>这次回答，如何得出？</h2></div><span className="live-badge">{run.phase === 'running' ? '实时查询中' : '本轮证据'}</span></header>
    <div className="knowledge-tabs" role="tablist" aria-label="过程展示">
      <button role="tab" aria-selected={tab==='graph'} onClick={()=>setTab('graph')}>知识图谱</button>
      <button role="tab" aria-selected={tab==='log'} onClick={()=>setTab('log')}>技术日志</button>
    </div>
    {tab === 'log' ? <Trace events={run.events}/> : <div className="knowledge-content scroll">
      <ol className="reasoning-stages">{['查看资料','连接知识','核对依据','解释结果'].map((label,i)=><li key={label} aria-current={stage===i?'step':undefined}><span>{i+1}</span>{label}</li>)}</ol>
      <div className="graph-card">
        <div className="graph-topline"><strong>{graph.nodes.length ? `${graph.nodes.length} 个节点 · ${graph.edges.length} 条关系` : '等待证据进入图谱'}</strong><button onClick={()=>setPaused(!paused)}>{paused?'继续动画':'暂停动画'}</button></div>
        <Suspense fallback={<div className="graph-loading">正在准备三维视图…</div>}><GraphScene graph={graph} paused={paused} selected={selected} onSelect={setSelected}/></Suspense>
        {!graph.nodes.length && <p className="graph-empty">查询返回概念、规则或记录后，节点会在这里出现。<br/>没有查到的关系不会被补画。</p>}
        <div className="graph-legend">{Object.entries(KIND).map(([k,v])=><span key={k}><i style={{background:v.color}}/>{v.label}</span>)}</div>
        <p className="graph-help">拖动旋转 · 滚轮缩放 · 点击节点查看出处<br/>颜色区分资料类型；位置和动画不代表风险高低。</p>
      </div>
      {(graph.nodes.length>0 || replay!==null) && <>
        <div className="graph-replay"><label htmlFor="graph-replay">回看查询过程</label><input id="graph-replay" type="range" min="0" max={lastSeq} value={replay ?? lastSeq} onChange={e=>setReplay(Number(e.target.value))}/><button onClick={()=>setReplay(null)}>{replay===null?'实时':'回到实时'}</button></div>
        <div className="graph-node-list" aria-label="选择证据节点">{graph.nodes.map(n=><button key={n.id} aria-pressed={n.id===selected} onClick={()=>setSelected(n.id)} style={{'--node-color':KIND[n.kind].color}}>{n.scenario?'假设 · ':''}{n.label}</button>)}</div>
      </>}
      {node && <section className="node-inspector"><span className="eyebrow">{KIND[node.kind].label}{node.scenario?' · 条件推演':''}</span><h3>{node.label}</h3>
        <p>来自“{toolLabel(node.tool)}”的真实返回。</p>
        {(node.detail.origin==='demo-cohort'||node.detail.fact_origin==='demo-cohort') && <p className="node-caution">这是演示数据。</p>}
        {node.scenario && <p className="node-caution">这是“如果…那么…”的假设结果，不是已经发生的事实。</p>}
        {(node.detail.trust==='Unverified'||node.detail.trust_level==='Unverified') && <p className="node-caution">这条数据尚未核实，不能据此判断病情。</p>}
        {node.detail.quote && <blockquote>{node.detail.quote}</blockquote>}
        <ul>{graph.edges.filter(e=>e.from===node.id||e.to===node.id).map(e=><li key={e.id}>{graph.nodes.find(n=>n.id===e.from)?.label} → {e.label} → {graph.nodes.find(n=>n.id===e.to)?.label}{e.inferredOnly?'（本体推导关系）':''}{e.sample?'（邻接样本）':''}</li>)}</ul>
        <details><summary>查看原始标识与证据字段</summary><pre>{JSON.stringify({identifier:node.ref, tool:node.tool, call_id:node.callId, ...node.detail}, null, 2)}</pre></details>
      </section>}
      {graph.notices.map(n=><p className="graph-notice" key={n}>{n}</p>)}
      {graph.clipped && <p className="graph-notice">为保证流畅，仅展示最多 70 个节点和 120 条关系；其余结果保留在技术日志中。</p>}
      <section className="human-progress"><h3>正在做什么</h3>
        {!calls.length && <p>先提出一个问题，我们会展示查阅了哪些资料。</p>}
        {calls.slice(-6).map((c,i)=><div className="human-step" key={c.callId??i}><span className={`step-dot ${c.done?(c.ok?'ok':'failed'):'working'}`}/><div><strong>{toolLabel(c.tool)}</strong><p>{c.done?(c.ok?'已返回结果，可展开技术日志核查。':'这一步未完成，不能当作“没有问题”。'):(['failed','stopped','done'].includes(run.phase)?'未收到完整结果。':'正在等待资料返回…')}</p></div></div>)}
      </section>
    </div>}
  </aside>;
}
