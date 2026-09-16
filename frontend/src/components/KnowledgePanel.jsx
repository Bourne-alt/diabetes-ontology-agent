import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { graphFromEvents, KIND } from '../lib/knowledgeGraph.js';
import { groupCalls } from '../lib/groupCalls.js';
const GraphScene = lazy(() => import('./GraphScene.jsx'));

export default function KnowledgePanel({ run }) {
  const [paused, setPaused] = useState(false);
  const [selected, setSelected] = useState(null);
  const [replay, setReplay] = useState(null);
  const [expanded, setExpanded] = useState(false);
  const dialog = useRef(null);
  const expandButton = useRef(null);
  useEffect(() => {
    if (expanded) dialog.current?.showModal();
    else if (dialog.current?.open) dialog.current.close();
  }, [expanded]);
  function closeExpanded() {
    setExpanded(false);
    requestAnimationFrame(() => expandButton.current?.focus());
  }
  function selectNode(id) {
    setSelected(id);
    setPaused(true);
  }
  const liveGraph = useMemo(() => graphFromEvents(run.events), [run.events]);
  const graph = useMemo(() => replay === null ? liveGraph : graphFromEvents(run.events, replay), [run.events, replay, liveGraph]);
  const calls = useMemo(() => groupCalls(run.events), [run.events]);
  const lastSeq = run.events.at(-1)?.seq ?? 0;
  const current = calls.at(-1);
  const stage = run.answer !== null ? 3 : !current ? 0
    : /rule|passage|path|simulat|evidence/.test(current.tool) ? 2
    : /concept|term/.test(current.tool) ? 1 : 0;
  const hasGraph = graph.nodes.length > 0;
  // Keep the panel mounted when replaying an earlier point with no nodes.
  // A new run remounts this component, so it stays hidden until that run has evidence.
  if (liveGraph.nodes.length === 0) return null;

  const graphCard = !hasGraph ? <div className="graph-placeholder" role="status">
    <p>当前回放位置暂无图谱节点。</p>
    {expanded && <button onClick={closeExpanded}>关闭大图</button>}
  </div> : <div className="graph-card">
    <div className="graph-topline"><strong id="graph-title">{`${graph.nodes.length} 个节点 · ${graph.edges.length} 条关系`}</strong>
      <div className="graph-actions"><button onClick={()=>setPaused(!paused)}>{paused?'继续动画':'暂停动画'}</button>
        <button ref={expanded ? undefined : expandButton} onClick={()=>expanded ? closeExpanded() : setExpanded(true)}>{expanded?'关闭大图':'展开大图'}</button></div>
    </div>
    <Suspense fallback={<div className="graph-loading">正在准备三维视图…</div>}><GraphScene graph={graph} paused={paused} selected={selected} onSelect={selectNode} onClose={()=>setSelected(null)}/></Suspense>
    <div className="graph-legend">{Object.entries(KIND).map(([k,v])=><span key={k}><i style={{background:v.color}}/>{v.label}</span>)}</div>
    <p className="graph-help">拖动自由旋转（可上下翻转） · 滚轮或按钮缩放 · 点击节点查看详情<br/><b>离地高度＝推导层级</b>：贴近地面的是这位患者的实测数据，越高越接近判断所依据的指南原文。颜色区分资料类型，水平位置无含义。</p>
    <div className="graph-node-list" aria-label="选择证据节点">{graph.nodes.map(n=><button key={n.id} aria-pressed={n.id===selected} onClick={()=>selectNode(n.id)} style={{'--node-color':KIND[n.kind].color}}>{n.scenario?'假设 · ':''}{n.label}</button>)}</div>
  </div>;
  return <aside className="knowledge-panel">
    <dialog ref={dialog} className="graph-dialog" aria-label="知识图谱大图" onCancel={closeExpanded} onClose={()=>setExpanded(false)}>
      {expanded && graphCard}
    </dialog>
    <header className="knowledge-title"><h2>知识图谱</h2></header>
    <div className="knowledge-content scroll">
      {hasGraph && <ol className="reasoning-stages">{['查看资料','连接知识','核对依据','解释结果'].map((label,i)=><li key={label} aria-current={stage===i?'step':undefined}><span>{i+1}</span>{label}</li>)}</ol>}
      {!expanded && graphCard}
      {(graph.nodes.length>0 || replay!==null) && <>
        <div className="graph-replay"><label htmlFor="graph-replay">回看查询过程</label><input id="graph-replay" type="range" min="0" max={lastSeq} value={replay ?? lastSeq} onChange={e=>setReplay(Number(e.target.value))}/><button onClick={()=>setReplay(null)}>{replay===null?'实时':'回到实时'}</button></div>
      </>}
      {graph.notices.map(n=><p className="graph-notice" key={n}>{n}</p>)}
      {graph.clipped && <p className="graph-notice">为保证流畅，仅展示最多 70 个节点和 120 条关系；其余结果保留在聊天中的工具调用记录中。</p>}

    </div>
  </aside>;
}
