import test from 'node:test';
import assert from 'node:assert/strict';
import { zoomDistance, wheelZoomFactor, smoothZoomDistance } from './graphZoom.js';

test('wheel units agree and fine trackpad and pinch gestures respond', () => {
  assert.equal(wheelZoomFactor(16), wheelZoomFactor(1, 1));
  assert.equal(wheelZoomFactor(400), wheelZoomFactor(1, 2));
  assert.ok(wheelZoomFactor(-2) < 1);
  assert.ok(wheelZoomFactor(-2, 0, true) < wheelZoomFactor(-2));
  assert.ok(Math.abs(wheelZoomFactor(-100) * wheelZoomFactor(100) - 1) < 1e-12);
  assert.ok(wheelZoomFactor(100000) < 2);
});

test('repeated zoom stays bounded and can reverse immediately at a limit', () => {
  assert.equal(zoomDistance(10, .001), 2.5);
  assert.equal(zoomDistance(10, 100), 20);
  assert.ok(zoomDistance(2.5, wheelZoomFactor(20)) > 2.5);
  assert.ok(zoomDistance(20, wheelZoomFactor(-20)) < 20);
});

test('smooth zoom converges without overshoot at different frame rates', () => {
  const simulate = (fps) => {
    let distance = 10;
    for (let i = 0; i < fps / 5; i++) {
      const next = smoothZoomDistance(distance, 5, 1 / fps);
      assert.ok(next >= 5 && next < distance);
      distance = next;
    }
    return distance;
  };
  assert.ok(Math.abs(simulate(60) - simulate(120)) < 1e-10);
  assert.ok(simulate(60) < 5.1);
  assert.equal(smoothZoomDistance(5.0001, 5, 1 / 60), 5);
});
