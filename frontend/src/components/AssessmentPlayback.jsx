import { useEffect, useState } from 'react';
import Citations from './Citations.jsx';
import { createBag, harvest } from '../lib/evidence.js';

const DOMAIN = {glycemic:'糖代谢',renal:'肾脏',cardiovascular:'心血管',hepatic:'肝脏',safety:'治疗安全',lifestyle:'生活方式'};

function RecordDetails({ details }) {
  const { claims, gaps, events, selected_measurements, entities, ...rest } = details;
  const records = events || selected_measurements;
  return <div className="assessment-step-details">
    {records && <><h4>输入记录 · {records.length} 条</h4><div className="assessment-table-scroll"><table><thead><tr><th>记录</th><th>数值 / 内容</th><th>可信度</th><th>发生时间</th></tr></thead><tbody>{records.map(e=><tr key={e.event_id}><td>{e.metric||e.concept_code||e.source}<small>{e.event_id}</small></td><td>{e.value??e.text??'未提供'} {e.unit||''}</td><td>{e.value_trust==='verified'?'已核验':'未核验'}</td><td>{e.event_time_known===false?'未知':e.event_time}</td></tr>)}</tbody></table></div></>}
    {(claims||gaps)?.map(c=><article className={`assessment-claim ${c.kind==='data_gap'?'is-gap':''}`} key={c.claim_id}><small>{DOMAIN[c.domain]||c.domain} · {c.kind==='data_gap'?'资料缺口':c.kind==='rule_conclusion'?'规则结果':'事实 / 条件提示'}</small><p>{c.statement}</p><details><summary>查看此项的规则和证据编号</summary><pre>{JSON.stringify({claim_id:c.claim_id,rule_id:c.rule_id,evidence_ids:c.evidence_ids,missing:c.missing_premises,data:c.data},null,2)}</pre></details></article>)}
    {entities && <><h4>本体实体 · {entities.length} 个</h4>{entities.map(e=><div className="assessment-entity" key={e.evidence_id}><strong>{e.evidence_id}</strong><span>→ {e.class_iri.split('/').at(-1)}</span><details><summary>实体属性</summary><pre>{JSON.stringify(e.entity,null,2)}</pre></details></div>)}</>}
    {Object.entries(rest).map(([key,value])=><div className="assessment-property" key={key}><strong>{key}</strong>{typeof value==='object'?<pre>{JSON.stringify(value,null,2)}</pre>:<span>{String(value)}</span>}</div>)}
  </div>;
}

function PredictionChart({ report, step }) {
  if (!report.predictions?.length) return null;
  const shown = report.predictions.filter(p => step.key==='demo_result' || (step.key.startsWith('horizon_') && p.horizon_days<=Number(step.key.slice(8))));
  const base=report.baseline.value;
  const values=[base,...report.predictions.map(p=>p.simulated_value)];
  const min=Math.min(...values)-.15,max=Math.max(...values)+.15;
  const x=day=>45+day/28*430,y=value=>140-(value-min)/(max-min)*110;
  const points=[[0,base],...shown.map(p=>[p.horizon_days,p.simulated_value])];
  return <figure className="prediction-chart"><figcaption>机器学习模型数值推演 · FPG（mmol/L）</figcaption><svg viewBox="0 0 520 180" role="img" aria-label="仅用于流程验证的数值曲线，不代表疗效">
    <line x1="45" y1={y(base)} x2="475" y2={y(base)} stroke="#9bb1b6" strokeDasharray="5 5"/>
    <polyline points={points.map(([d,v])=>`${x(d)},${y(v)}`).join(' ')} fill="none" stroke="#588c92" strokeWidth="3"/>
    {points.map(([d,v])=><g key={d}><circle cx={x(d)} cy={y(v)} r="5" fill="#588c92"/><text x={x(d)} y={y(v)-12} textAnchor="middle">{v.toFixed(3)}</text></g>)}
    {[0,7,14,28].map(d=><text key={d} x={x(d)} y="166" textAnchor="middle">{d} 天</text>)}
  </svg><p>虚线为基线对照；纵轴按模拟数值范围缩放，无预测区间，不作治疗效果估计。</p></figure>;
}

export default function AssessmentPlayback({ report }) {
  const steps = report.execution_trace?.steps || [];
  const [index,setIndex]=useState(0);
  const [playing,setPlaying]=useState(false);
  const [speed,setSpeed]=useState(1);
  useEffect(()=>{
    if (!playing || index>=steps.length-1) return;
    const timer=setTimeout(()=>setIndex(i=>i+1),1800/speed);
    return ()=>clearTimeout(timer);
  },[playing,index,steps.length,speed]);
  const step=steps[index];
  if (!step) return <p>此报告未包含执行记录，请重新运行评估。</p>;
  function go(i){setPlaying(false);setIndex(i);}
  return <section className="assessment-playback" aria-label="评估步骤回放">
    <div className="assessment-replay-heading"><span className="eyebrow">真实执行记录 · 动画回放</span><span>{index+1} / {steps.length}</span></div>
    <p className="assessment-disclaimer">{report.prediction_kind==='untrained_demo'?report.disclaimer:report.execution_trace.notice}</p>
    <div className="assessment-controls"><button onClick={()=>{if(index===steps.length-1)setIndex(0);setPlaying(!playing||index===steps.length-1);}}>{playing&&index<steps.length-1?'暂停回放':'播放步骤'}</button><button disabled={index===0} onClick={()=>go(index-1)}>上一步</button><button disabled={index===steps.length-1} onClick={()=>go(index+1)}>下一步</button><label>速度 <select value={speed} onChange={e=>setSpeed(Number(e.target.value))}><option value={.5}>0.5×</option><option value={1}>1×</option><option value={2}>2×</option></select></label></div>
    <input className="assessment-timeline" aria-label="回放步骤" type="range" min="0" max={steps.length-1} value={index} onChange={e=>go(Number(e.target.value))}/>
    <ol className="assessment-flow">{steps.map((s,i)=><li key={s.key} className={i<index?'is-complete':i===index?'is-current':''}><button aria-current={i===index?'step':undefined} onClick={()=>go(i)}><span>{i<index?'✓':i+1}</span>{s.title}</button></li>)}</ol>
    <div className="assessment-active" key={step.key}><div className="assessment-replay-heading"><h3>{step.title}</h3><small>实际耗时 {step.duration_ms} ms</small></div><p>{step.summary}</p>
      {report.prediction_kind==='untrained_demo' && <PredictionChart report={report} step={step}/>}
      <RecordDetails details={step.details}/>
    </div>
    {report.rendered_markdown && <details className="assessment-report"><summary>查看完整评估报告</summary><pre>{report.rendered_markdown}</pre></details>}
    {report.report_id && <Citations quotes={harvest(report, 'assess_patient_treatment', createBag()).quotes}/>}
  </section>;
}
