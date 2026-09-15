import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DObject, CSS2DRenderer } from 'three/addons/renderers/CSS2DRenderer.js';
import { KIND } from '../lib/knowledgeGraph.js';

// Local deterministic layout. Coordinates carry no clinical meaning.
function position(index, count, kind) {
  if (kind === 'patient' && index === 0) return new THREE.Vector3(0, 0, 0);
  const y = 1 - 2 * (index + .5) / Math.max(count, 1);
  const r = Math.sqrt(1 - y * y);
  const theta = index * Math.PI * (3 - Math.sqrt(5));
  return new THREE.Vector3(Math.cos(theta) * r * 2.75, y * 2.15, Math.sin(theta) * r * 2.4);
}
export default function GraphScene({ graph, paused, selected, onSelect }) {
  const host = useRef(null), runtime = useRef(null), callback = useRef(onSelect);
  const [unavailable, setUnavailable] = useState(false);
  useEffect(() => { callback.current = onSelect; }, [onSelect]);
  useEffect(() => {
    const el = host.current;
    let renderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }); }
    catch { setUnavailable(true); return; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0xf7fbfd, 0);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, .1, 80);
    camera.position.set(0, 1, 10.5);
    const labels = new CSS2DRenderer();
    labels.domElement.className = 'graph-labels';
    labels.domElement.style.pointerEvents = 'none';
    el.append(renderer.domElement, labels.domElement);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; controls.enablePan = false;
    controls.minDistance = 5; controls.maxDistance = 16;
    controls.autoRotateSpeed = .5;
    scene.add(new THREE.HemisphereLight(0xffffff, 0x8b9eb5, 3));
    const light = new THREE.DirectionalLight(0xffffff, 4); light.position.set(3, 5, 4); scene.add(light);
    const group = new THREE.Group(); scene.add(group);
    const rings = new THREE.Group(); scene.add(rings);
    for (let i = 0; i < 3; i++) {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(3.35, .006, 6, 100),
        new THREE.MeshBasicMaterial({ color: 0xbccfda, transparent: true, opacity: .22 }));
      ring.rotation.set(i * .7, i * .8, .2); rings.add(ring);
    }
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
    const instance = { scene, group, controls, renderer, particles: [], paused: false, visible: true, selection: null };
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
          child.material.emissiveIntensity = active ? .5 : .1;
          if (child.userData.label) {
            child.userData.label.style.opacity = active || child.userData.prominent ? '1' : '0';
          }
        }
      }
      for (const particle of instance.particles) {
        particle.mesh.visible = animate;
        if (animate) particle.mesh.position.lerpVectors(particle.from, particle.to, (time*.00018+particle.offset)%1);
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
    graph.nodes.forEach((node, i) => {
      const at = position(i, graph.nodes.length, node.kind); positions.set(node.id, at);
      const color = KIND[node.kind]?.color || KIND.concept.color;
      const mesh = new THREE.Mesh(new THREE.SphereGeometry(node.kind === 'patient' ? .31 : .20, 24, 18),
        new THREE.MeshPhysicalMaterial({ color, metalness: .12, roughness: .25, clearcoat: .9, emissive: color, emissiveIntensity: .1 }));
      mesh.position.copy(at); mesh.userData.nodeId = node.id;
      const label = document.createElement('span'); label.className = 'graph-node-label';
      label.textContent = `${node.scenario ? '假设 · ' : ''}${node.label.length > 20 ? node.label.slice(0,18)+'…' : node.label}`;
      label.setAttribute('aria-hidden', 'true');
      const prominent = i < 4 || node.kind === 'patient' || node.kind === 'rule' || node.scenario;
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
        new THREE.LineBasicMaterial({ color: edge.scenario ? 0xb5a2cd : 0x9abcc9, transparent: true, opacity: .55 }));
      r.group.add(line);
      // Small arrow gives direction; particles show traversal, not causal strength.
      const direction = new THREE.Vector3().subVectors(to, from).normalize();
      const arrow = new THREE.Mesh(new THREE.ConeGeometry(.045, .13, 8), new THREE.MeshBasicMaterial({ color: 0x8faaba }));
      arrow.position.lerpVectors(from, to, .7); arrow.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),direction); r.group.add(arrow);
      const particle = new THREE.Mesh(new THREE.SphereGeometry(.045, 8, 6), new THREE.MeshBasicMaterial({ color: 0x69b9cc }));
      r.group.add(particle); r.particles.push({ mesh: particle, from, to, offset: (i*.17)%1 });
    });
  }, [graph]);
  useEffect(() => { if (runtime.current) runtime.current.paused = paused; }, [paused]);
  useEffect(() => { if (runtime.current) runtime.current.selection = selected; }, [selected]);
  return <div className="graph-stage" ref={host} role="img" aria-label={`三维证据图，${graph.nodes.length}个节点，${graph.edges.length}条关系。可在下方按钮中选择节点。`}>
    {unavailable && <div className="graph-fallback">此浏览器暂不支持 3D，请使用下方节点列表查看相同证据。</div>}
  </div>;
}
