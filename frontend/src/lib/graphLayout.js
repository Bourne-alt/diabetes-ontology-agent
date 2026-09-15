import * as THREE from 'three';

// 离地高度＝推导层级。贴近地面的是这位患者的实测数据，越高越接近判断所依据的
// 指南原文；同层节点在水平圆周上散开，水平位置无临床含义。
// （此前 position() 按数组下标排斐波那契球面，坐标不承载任何信息，
//  所以界面上只能声明「位置和动画不代表风险高低」。）
export const GROUND_Y = -2.75;
export const LAYER_Y = { patient: -1.85, fact: -0.9, concept: 0.05, rule: 1, evidence: 1.95 };
export const LAYER_R = { patient: .5, fact: 1.6, concept: 2.15, rule: 1.7, evidence: 2.3 };

/** @param rank 该节点在自己那一层里的序号 @param countInLayer 该层节点总数 */
export function position(rank, countInLayer, kind) {
  const y = LAYER_Y[kind] ?? 0;
  if (kind === 'patient' && countInLayer === 1) return new THREE.Vector3(0, y, 0);
  const r = LAYER_R[kind] ?? 2;
  const theta = (rank / Math.max(countInLayer, 1)) * Math.PI * 2 + (kind === 'fact' ? .4 : 0);
  return new THREE.Vector3(Math.cos(theta) * r, y, Math.sin(theta) * r);
}

/** 按 kind 统计每层节点数与层内序号——同层要均匀铺在各自圆周上，必须先数清楚。 */
export function layerRanks(nodes) {
  const perLayer = {};
  for (const n of nodes) perLayer[n.kind] = (perLayer[n.kind] ?? 0) + 1;
  const seen = {};
  return nodes.map((n) => ({
    node: n,
    rank: (seen[n.kind] = (seen[n.kind] ?? -1) + 1),
    countInLayer: perLayer[n.kind],
  }));
}
