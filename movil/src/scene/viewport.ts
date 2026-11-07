import { PLAN_HEIGHT, PLAN_WIDTH } from '@compartido/scene/plan';
import { officeGestures } from '@/theme/motion';

export interface Viewport { x: number; y: number; scale: number }
export function clampPan(value: number, viewport: number, content: number): number {
  'worklet';
  return content <= viewport ? Math.round((viewport - content) / 2) : Math.max(viewport - content, Math.min(0, value));
}
/** Integer physical-pixel scale, also during pinch: no blurred fractional zoom levels. */
export function zoomAt(view: Viewport, requested: number, fx: number, fy: number, width: number, height: number, base: number, density: number) {
  'worklet';
  const scale = Math.round(Math.max(base * officeGestures.minZoom, Math.min(base * officeGestures.maxZoom, requested)) * density) / density;
  const ratio = scale / view.scale;
  view.x = clampPan(fx - (fx - view.x) * ratio, width, PLAN_WIDTH * scale);
  view.y = clampPan(fy - (fy - view.y) * ratio, height, PLAN_HEIGHT * scale);
  view.scale = scale;
}
