import { PLAN_HEIGHT, PLAN_WIDTH } from '@compartido/scene/plan';
import { officeGestures } from '@/theme/motion';

export interface Viewport { x: number; y: number; scale: number }
export function clampPan(value: number, viewport: number, content: number): number {
  'worklet';
  return content <= viewport ? Math.round((viewport - content) / 2) : Math.max(viewport - content, Math.min(0, value));
}
/**
 * The opening scale fills the screen's width, whatever fraction of a pixel that takes; zoomed in, the pinch snaps to whole
 * physical pixels (no blurred in-between levels) and never goes below the opening scale.
 */
export function zoomAt(view: Viewport, requested: number, fx: number, fy: number, width: number, height: number, base: number, density: number) {
  'worklet';
  const snapped = Math.round(Math.max(base * officeGestures.minZoom, Math.min(base * officeGestures.maxZoom, requested)) * density) / density;
  const scale = snapped <= base ? base : snapped;
  const ratio = scale / view.scale;
  view.x = clampPan(fx - (fx - view.x) * ratio, width, PLAN_WIDTH * scale);
  view.y = clampPan(fy - (fy - view.y) * ratio, height, PLAN_HEIGHT * scale);
  view.scale = scale;
}
