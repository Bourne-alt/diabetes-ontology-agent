import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DObject, CSS2DRenderer } from 'three/addons/renderers/CSS2DRenderer.js';
import { KIND } from '../lib/knowledgeGraph.js';
import { toolLabel } from '../lib/toolLabels.js';
import { GROUND_Y, position, layerRanks } from '../lib/graphLayout.js';

function NodeSummary({ node, onClose, cardRef }) {
  const d = node.detail || {};
  const value = d.value ?? d.result_value ?? d.data?.value;
  const unit = d.unit ?? d.result_unit ?? d.data?.unit;
  const units = {percent:'%', 'mg-per-dL':'mg/dL', 'mmol-per-L':'mmol/L', 'mg-per-g':'mg/g'};
  const date = d.event_time ?? d.collected_at ?? d.data?.event_time;
  const summary = d.statement || d.description || d.definition || d.text || d.quote || d.exact_quote;
  const names = {A1C:'糖化血红蛋白', FPG:'空腹血糖', UACR:'尿白蛋白／肌酐比', EGFR:'估算肾小球滤过率', ALT:'谷丙转氨酶', CHOL:'总胆固醇', BMI:'身体质量指数'};
  const title = names[node.label] ? `${names[node.label]}（${node.label}）`
    : node.kind==='rule' && d.rule_id===node.label ? (d.kind==='data_gap'?'需要补充的资料':'评估结论') : node.label;
  const unverified = [d.trust,d.trust_level,d.value_trust].some(v=>['Unverified','unverified'].includes(v));
  return <section ref={cardRef} className="graph-node-popover" aria-label="节点详情" aria-live="polite" style={{'--node-accent':KIND[node.kind]?.color}}>
    <header><span>{KIND[node.kind]?.label}</span><button type="button" onClick={onClose} aria-label="关闭节点详情">×</button></header>
    <h3>{title}</h3>
    {value !== undefined && value !== null && <p className="graph-node-value">{String(value)} <small>{units[unit] || unit || ''}</small></p>}
    {summary && <p className="graph-node-summary">{String(summary)}</p>}
    {date && <p className="graph-node-meta">记录时间：{String(date).slice(0,10)}</p>}
    {(d.fact_origin==='demo-cohort'||d.origin==='demo-cohort') && <span className="graph-node-tag">合成数据</span>}
    {node.scenario && <p className="graph-node-warning">假设情景，尚未实际发生</p>}
    {unverified && <p className="graph-node-warning">结果尚未核实，不能据此判断</p>}
    {d.kind==='data_gap' && <p className="graph-node-warning">资料不足，需要补充后再判断</p>}
    {!summary && value == null && <p className="graph-node-meta">{node.kind==='patient'?'此节点汇集该患者的检查与记录。':'本次返回未提供更多说明。'}</p>}
    <footer>来源：{d.source_file?.split('/').at(-1) || toolLabel(node.tool)}</footer>
  </section>;
}

export default function GraphScene({ graph, paused, selected, onSelect, onClose }) {
  const host = useRef(null), runtime = useRef(null), callback = useRef(onSelect);
  const card = useRef(null), connector = useRef(null);
  const node = graph.nodes.find(n => n.id === selected);
  const [unavailable, setUnavailable] = useState(false);
  useEffect(() => { callback.current = onSelect; }, [onSelect]);
  useEffect(() => {
    const el = host.current;
    let renderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }); }
    catch { setUnavailable(true); return; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0xeaecf4, 0);  // alpha 0：底色由 .graph-stage 的 --win 给
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, .1, 80);
    camera.position.set(0, 1.7, 10.8);
    const labels = new CSS2DRenderer();
    labels.domElement.className = 'graph-labels';
    labels.domElement.style.pointerEvents = 'none';
    el.append(renderer.domElement, labels.domElement);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; controls.enablePan = false;
    controls.minDistance = 5; controls.maxDistance = 16;
    controls.autoRotateSpeed = .5;
    scene.add(new THREE.HemisphereLight(0xffffff, 0xc8cdda, 1.7));
    const light = new THREE.DirectionalLight(0xffffff, 1.9); light.position.set(3, 5, 4); scene.add(light);
    const group = new THREE.Group(); scene.add(group);
    // 地面网格给出高度基准面。没有它，节点的地面光斑会被读成「另一个节点」。
    const ground = new THREE.GridHelper(9.5, 14, 0xb9c0d2, 0xd2d7e4);
    ground.position.y = GROUND_Y;
    ground.material.transparent = true; ground.material.opacity = .6;
    scene.add(ground);
    const ray = new THREE.Raycaster();
    let pointerStart = null;
    const down = (event) => { pointerStart = [event.clientX, event.clientY]; };
    const click = (event) => {
      if (!pointerStart || Math.hypot(event.clientX-pointerStart[0], event.clientY-pointerStart[1]) > 5) return;
      const rect = renderer.domElement.getBoundingClientRect();
      ray.setFromCamera(new THREE.Vector2(2*(event.clientX-rect.left)/rect.width-1, 1-2*(event.clientY-rect.top)/rect.height), camera);
      const hit = ray.intersectObjects(group.children, false).find(h => h.object.userData.nodeId);
      if (hit) callback.current(hit.object.userData.nodeId);
    };
    renderer.domElement.addEventListener('pointerdown', down);
    renderer.domElement.addEventListener('pointerup', click);
    const resize = () => {
      const width = Math.max(el.clientWidth, 1), height = Math.max(el.clientHeight, 1);
      renderer.setSize(width, height); labels.setSize(width, height);
      camera.aspect = width/height; camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize); observer.observe(el); resize();
    const instance = { scene, group, camera, controls, renderer, particles: [], paused: false, visible: true, selection: null };
    runtime.current = instance;
    const intersection = new IntersectionObserver(([entry]) => { instance.visible = entry.isIntersecting; });
    intersection.observe(el);
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
    const tick = (time) => {
      if (!instance.visible || document.hidden) return;
      const animate = !instance.paused && !reduce.matches;
      controls.autoRotate = animate; controls.update();
      for (const child of group.children) {
        if (child.userData.nodeId) {
          const active = child.userData.nodeId === instance.selection;
          child.scale.setScalar(active ? 1.35 : 1);
          // 浅底上发光等于把节点变淡、反而后退，所以静息态自发光为 0。
          if (child.material.emissiveIntensity !== undefined) {
            child.material.emissiveIntensity = active ? .28 : 0;
          }
          if (child.userData.label) {
            child.userData.label.style.opacity = active || child.userData.prominent ? '1' : '0';
          }
        }
      }
      for (const particle of instance.particles) {
        particle.mesh.visible = animate;
        if (animate) particle.mesh.position.lerpVectors(particle.from, particle.to, (time*.00018+particle.offset)%1);
      }
      const activeMesh = group.children.find(child => child.userData.nodeId === instance.selection);
      if (card.current && activeMesh) {
        const point = activeMesh.getWorldPosition(new THREE.Vector3()).project(camera);
        const width = el.clientWidth, height = el.clientHeight;
        const x = (point.x+1)*width/2, y = (1-point.y)*height/2;
        const visible = point.z>=-1 && point.z<=1 && x>=0 && x<=width && y>=0 && y<=height;
        card.current.style.visibility = visible ? 'visible' : 'hidden';
        const w = card.current.offsetWidth, h = card.current.offsetHeight;
        const left = Math.max(8, Math.min(width-w-8, x+w+24<width ? x+24 : x-w-24));
        const top = Math.max(8, Math.min(height-h-54, y-h/2));
        card.current.style.transform = `translate(${left}px, ${top}px)`;
        if (connector.current) {
          connector.current.style.visibility = visible ? 'visible' : 'hidden';
          connector.current.setAttribute('x1',x); connector.current.setAttribute('y1',y);
          connector.current.setAttribute('x2',Math.max(left,Math.min(left+w,x)));
          connector.current.setAttribute('y2',Math.max(top+8,Math.min(top+h-8,y)));
        }
      }
      renderer.render(scene, camera); labels.render(scene, camera);
    };
    renderer.setAnimationLoop(tick);
    const lost = (e) => { e.preventDefault(); setUnavailable(true); renderer.setAnimationLoop(null); };
    renderer.domElement.addEventListener('webglcontextlost', lost);
    return () => {
      renderer.setAnimationLoop(null); observer.disconnect(); intersection.disconnect(); controls.dispose();
      scene.traverse(o => { o.geometry?.dispose(); if (o.material) o.material.dispose(); });
      renderer.dispose(); runtime.current = null; el.replaceChildren();
    };
  }, []);
  useEffect(() => {
    const r = runtime.current;
    if (!r) return;
    for (const child of [...r.group.children]) {
      child.traverse(o => {
        // CSS2DObject is nested under a mesh. Removing the mesh does not emit
        // the label's own `removed` event, so CSS2DRenderer would keep the old
        // HTML element and the next SSE update would paint another label over it.
        if (o.isCSS2DObject) o.element.remove();
        o.geometry?.dispose();
        o.material?.dispose();
      });
      r.group.remove(child);
    }
    r.particles = [];
    const positions = new Map();
    layerRanks(graph.nodes).forEach(({ node, rank, countInLayer }, i) => {
      const at = position(rank, countInLayer, node.kind); positions.set(node.id, at);
      const color = KIND[node.kind]?.color || KIND.concept.color;
      const radius = node.kind === 'patient' ? .31 : .20;
      const mesh = new THREE.Mesh(new THREE.SphereGeometry(radius, 24, 18),
        new THREE.MeshPhysicalMaterial({ color, metalness: .05, roughness: .42, clearcoat: .6, clearcoatRoughness: .3, emissive: color, emissiveIntensity: 0 }));
      mesh.position.copy(at); mesh.userData.nodeId = node.id;

      // 地面光斑与高度虚线：浅底上的深度线索，同时让「悬得多高」可量。
      const spot = new THREE.Mesh(new THREE.CircleGeometry(radius * 1.35, 20),
        new THREE.MeshBasicMaterial({ color: 0x1c1a17, transparent: true, opacity: .14, depthWrite: false }));
      spot.rotation.x = -Math.PI / 2;
      spot.position.set(at.x, GROUND_Y + .012, at.z);
      r.group.add(spot);

      const stem = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([at, new THREE.Vector3(at.x, GROUND_Y, at.z)]),
        new THREE.LineDashedMaterial({ color: 0x1c1a17, transparent: true, opacity: .18, dashSize: .09, gapSize: .07 }));
      stem.computeLineDistances();
      r.group.add(stem);
      const label = document.createElement('span'); label.className = 'graph-node-label';
      label.textContent = `${node.scenario ? '假设 · ' : ''}${node.label.length > 20 ? node.label.slice(0,18)+'…' : node.label}`;
      label.setAttribute('aria-hidden', 'true');
      const prominent = i < 5 || node.kind === 'patient' || node.kind === 'rule' || node.scenario;
      label.style.opacity = prominent ? '1' : '0';
      mesh.userData.label = label;
      mesh.userData.prominent = prominent;
      const object = new CSS2DObject(label); object.position.set(0, -.35, 0); mesh.add(object);
      r.group.add(mesh);
    });
    graph.edges.forEach((edge, i) => {
      const from = positions.get(edge.from), to = positions.get(edge.to);
      if (!from || !to) return;
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([from, to]),
        new THREE.LineBasicMaterial({ color: edge.scenario ? 0x6e4a6b : 0x555047, transparent: true, opacity: .3 }));
      r.group.add(line);
      // Small arrow gives direction; particles show traversal, not causal strength.
      const direction = new THREE.Vector3().subVectors(to, from).normalize();
      const arrow = new THREE.Mesh(new THREE.ConeGeometry(.045, .13, 8), new THREE.MeshBasicMaterial({ color: 0x6e6759 }));
      arrow.position.lerpVectors(from, to, .7); arrow.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),direction); r.group.add(arrow);
      const particle = new THREE.Mesh(new THREE.SphereGeometry(.045, 8, 6), new THREE.MeshBasicMaterial({ color: 0x34477a }));
      r.group.add(particle); r.particles.push({ mesh: particle, from, to, offset: (i*.17)%1 });
    });
  }, [graph]);
  useEffect(() => { if (runtime.current) runtime.current.paused = paused; }, [paused]);
  useEffect(() => { if (runtime.current) runtime.current.selection = selected; }, [selected]);
  function zoom(factor) {
    const r = runtime.current;
    if (!r) return;
    const offset = r.camera.position.clone().sub(r.controls.target);
    offset.setLength(THREE.MathUtils.clamp(offset.length() * factor, r.controls.minDistance, r.controls.maxDistance));
    r.camera.position.copy(r.controls.target).add(offset);
    r.controls.update();
  }
  function resetView() {
    const r = runtime.current;
    if (!r) return;
    r.controls.target.set(0, 0, 0);
    r.camera.position.set(0, 1.7, 10.8);
    r.controls.update();
  }
  return <div className="graph-viewport">
    <div className="graph-stage" ref={host} role="img" aria-label={`三维证据图，${graph.nodes.length}个节点，${graph.edges.length}条关系。节点按推导层级分层：底层为该患者的实测数据，顶层为依据的指南原文。可在下方按钮中选择节点。`} />
    <div className="graph-view-controls" role="group" aria-label="图谱视图控制">
      <button type="button" aria-label="放大图谱" title="放大" disabled={unavailable} onClick={() => zoom(.8)}>＋</button>
      <button type="button" aria-label="缩小图谱" title="缩小" disabled={unavailable} onClick={() => zoom(1.25)}>−</button>
      <button type="button" disabled={unavailable} onClick={resetView}>重置视角</button>
    </div>
    {node && <><svg className="graph-popover-connector" aria-hidden="true"><line ref={connector}/></svg><NodeSummary node={node} cardRef={card} onClose={onClose}/></>}
    {unavailable && <div className="graph-fallback">此浏览器暂不支持 3D，请使用下方节点列表查看相同证据。</div>}
  </div>;
}
