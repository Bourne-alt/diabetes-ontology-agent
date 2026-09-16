import { useEffect, useRef, useState } from 'react';
import AssessmentPlayback from './AssessmentPlayback.jsx';

export default function AssessmentDemo({ agentReport }) {
  const [scenarios,setScenarios]=useState([]);
  const [pid,setPid]=useState('P91001');
  const [report,setReport]=useState(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const request=useRef(null);
  useEffect(()=>{
    const controller=new AbortController();
    fetch('/demo/treatment-scenarios',{signal:controller.signal}).then(async r=>{
      if(!r.ok)throw new Error('评估场景列表加载失败，请检查后端服务。');
      return r.json();
    }).then(data=>setScenarios(data.scenarios)).catch(e=>{if(e.name!=='AbortError')setError(e.message);});
    return ()=>{controller.abort();request.current?.abort();};
  },[]);
  useEffect(()=>{if(agentReport){request.current?.abort();setReport(agentReport);setError('');setBusy(false);}},[agentReport]);
  async function run(kind){
    request.current?.abort();
    const controller=new AbortController();request.current=controller;
    setBusy(true);setError('');setReport(null);
    try {
      const response=await fetch(`/patients/${encodeURIComponent(pid)}/${kind}`,{method:'POST',signal:controller.signal});
      const data=await response.json();
      if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:`请求失败（${response.status}）`);
      if(!controller.signal.aborted)setReport(data);
    }catch(e){if(e.name!=='AbortError')setError(e.message);}
    finally{if(request.current===controller)setBusy(false);}
  }
  const scenario=scenarios.find(s=>s.pid===pid);
  return <div className="assessment-demo scroll">
    <header><span className="eyebrow">合成患者 · 场景分析</span><h3>看见评估中的每一步</h3><p>选择场景执行接口，再按真实记录播放。评估与数值推演分别运行。</p></header>
    <label className="assessment-scenario-label">合成患者<select value={pid} disabled={busy} onChange={e=>{setPid(e.target.value);setReport(null);setError('');}}>{scenarios.map(s=><option key={s.pid} value={s.pid}>{s.pid} · {s.title}</option>)}</select></label>
    {scenario && <div className="assessment-scenario"><p>{scenario.focus}</p><small>设计观察点：{scenario.expected}</small></div>}
    <div className="assessment-controls"><button disabled={busy||!scenarios.length} onClick={()=>run('treatment-assessments')}>运行患者评估</button><button disabled={busy||!scenarios.length} onClick={()=>run('prediction-demo')}>运行预测演示</button>{busy&&<button onClick={()=>{request.current?.abort();setBusy(false);}}>取消等待</button>}</div>
    {busy&&<p role="status" className="assessment-running">正在执行接口，完成后展示实际中间结果…</p>}
    {error&&<p role="alert" className="node-caution">{error}</p>}
    {report&&<><div className="assessment-result-meta"><strong>{report.snapshot_refs?.baseline?.patient_context?.patient_id||pid}</strong><span>{report.prediction_kind==='untrained_demo'?'模型数值推演':'规则与证据评估'}</span><span>{report.status==='partial'?'存在资料缺口':report.status}</span></div><AssessmentPlayback key={report.report_id||report.run_hash} report={report}/></>}
  </div>;
}
