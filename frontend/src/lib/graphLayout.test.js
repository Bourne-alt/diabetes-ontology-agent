import test from 'node:test';
import assert from 'node:assert/strict';
import { position, layerRanks, LAYER_Y, GROUND_Y } from './graphLayout.js';

const NODES = [
  { id:'p',  kind:'patient' },
  { id:'f1', kind:'fact' }, { id:'f2', kind:'fact' }, { id:'f3', kind:'fact' },
  { id:'c1', kind:'concept' }, { id:'c2', kind:'concept' },
  { id:'r1', kind:'rule' },
  { id:'e1', kind:'evidence' }, { id:'e2', kind:'evidence' },
];

test('layer order encodes derivation depth: patient lowest, guideline highest', () => {
  const order = ['patient', 'fact', 'concept', 'rule', 'evidence'];
  for (let i = 1; i < order.length; i++) {
    assert.ok(LAYER_Y[order[i]] > LAYER_Y[order[i - 1]],
      `${order[i]} must sit above ${order[i - 1]}`);
  }
});

test('every node floats above the ground plane', () => {
  for (const { node, rank, countInLayer } of layerRanks(NODES)) {
    const at = position(rank, countInLayer, node.kind);
    assert.ok(at.y > GROUND_Y, `${node.id} (${node.kind}) fell through the floor`);
  }
});

test('nodes of one kind share a height and never collide', () => {
  const placed = layerRanks(NODES).map(({ node, rank, countInLayer }) =>
    ({ id: node.id, kind: node.kind, at: position(rank, countInLayer, node.kind) }));
  for (const kind of ['fact', 'concept', 'evidence']) {
    const same = placed.filter(p => p.kind === kind);
    assert.ok(same.every(p => p.at.y === same[0].at.y), `${kind} nodes must share one height`);
    for (let i = 0; i < same.length; i++)
      for (let j = i + 1; j < same.length; j++)
        assert.ok(same[i].at.distanceTo(same[j].at) > 0.4,
          `${same[i].id} and ${same[j].id} overlap`);
  }
});

test('a lone patient anchors the centre', () => {
  const at = position(0, 1, 'patient');
  assert.equal(at.x, 0); assert.equal(at.z, 0);
  assert.equal(at.y, LAYER_Y.patient);
});

test('layout is deterministic — same input, same coordinates', () => {
  const a = layerRanks(NODES).map(x => position(x.rank, x.countInLayer, x.node.kind).toArray().join());
  const b = layerRanks(NODES).map(x => position(x.rank, x.countInLayer, x.node.kind).toArray().join());
  assert.deepEqual(a, b);
});

test('rank is per-layer, not a global index', () => {
  const ranks = layerRanks(NODES);
  assert.deepEqual(ranks.filter(r => r.node.kind === 'fact').map(r => r.rank), [0, 1, 2]);
  assert.deepEqual(ranks.filter(r => r.node.kind === 'evidence').map(r => r.rank), [0, 1]);
});
