export const MIN_GRAPH_DISTANCE = 2.5;
export const MAX_GRAPH_DISTANCE = 20;

export function zoomDistance(distance, factor) {
  return Math.max(MIN_GRAPH_DISTANCE, Math.min(MAX_GRAPH_DISTANCE, distance * factor));
}

export function wheelZoomFactor(deltaY, deltaMode = 0, pinch = false) {
  const pixels = deltaY * (deltaMode === 1 ? 16 : deltaMode === 2 ? 400 : 1);
  // Exponential scaling keeps small trackpad deltas useful and limits wheel spikes.
  return Math.exp(Math.max(-.5, Math.min(.5, pixels * (pinch ? .012 : .002))));
}

export function smoothZoomDistance(current, target, seconds) {
  const next = current + (target - current) * (1 - Math.exp(-20 * seconds));
  return Math.abs(next - target) < .001 ? target : next;
}
