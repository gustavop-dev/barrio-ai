// Stroke icons of the 0ff1ce design screens (24×24 grid, 2px stroke), the same paths as the PWA
// (oficina/src/components/icons.tsx and src/capture/icons.tsx). Decorative: give the parent its label.
import Svg, { Circle, Path, Rect } from 'react-native-svg';
import { colors } from '@/theme/tokens';

export interface IconProps {
  size?: number;
  color?: string;
}

type Shape =
  | { kind: 'path'; d: string }
  | { kind: 'circle'; cx: number; cy: number; r: number }
  | { kind: 'rect'; x: number; y: number; width: number; height: number; rx?: number };

const p = (d: string): Shape => ({ kind: 'path', d });
const c = (cx: number, cy: number, r: number): Shape => ({ kind: 'circle', cx, cy, r });
const r = (x: number, y: number, width: number, height: number, rx?: number): Shape => ({ kind: 'rect', x, y, width, height, rx });

const SHAPES = {
  oficina: [p('M3 21h18M5 21V7l7-4 7 4v14M9 21v-6h6v6')],
  tuTurno: [p('M22 12h-6l-2 3h-4l-2-3H2'), p('M5.5 5h13L22 12v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6z')],
  calendario: [r(3, 4, 18, 17, 2), p('M16 2v4M8 2v4M3 10h18')],
  resultados: [p('M4 20V10M10 20V4M16 20v-8M22 20H2')],
  personas: [p('M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2'), c(9, 7, 4), p('M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8')],
  ajustes: [
    c(12, 12, 3),
    p(
      'M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z',
    ),
  ],
  pausa: [p('M9 5v14M15 5v14')],
  play: [p('M7 4l13 8-13 8z')],
  chevronRight: [p('M9 6l6 6-6 6')],
  chevronLeft: [p('M15 6l-6 6 6 6')],
  chevronDown: [p('M6 9l6 6 6-6')],
  chevronUp: [p('M6 15l6-6 6 6')],
  external: [p('M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5')],
  eye: [p('M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z'), c(12, 12, 3)],
  eyeOff: [p('M3 3l18 18'), p('M10.6 5.1A10 10 0 0 1 12 5c6 0 10 7 10 7a17 17 0 0 1-3.2 3.9'), p('M6.6 6.6C3.9 8.4 2 12 2 12s4 7 10 7a9.7 9.7 0 0 0 5.4-1.6'), p('M9.9 9.9a3 3 0 0 0 4.2 4.2')],
  check: [p('M5 12l5 5 9-10')],
  plus: [p('M12 5v14M5 12h14')],
  search: [c(11, 11, 7), p('M21 21l-4.3-4.3')],
  info: [c(12, 12, 9), p('M12 11v6M12 7.5v.5')],
  aviso: [p('M12 3l10 18H2z'), p('M12 10v5M12 18v.5')],
  pregunta: [c(12, 12, 9), p('M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7M12 17v.5')],
  perfil: [c(12, 8, 4), p('M4 21a8 8 0 0 1 16 0')],
  conversacion: [p('M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z')],
  cerrar: [p('M6 6l12 12M18 6L6 18')],
  microfono: [r(9, 3, 6, 11, 3), p('M5 11a7 7 0 0 0 14 0M12 18v3')],
  galeria: [r(3, 4, 18, 16, 2), c(9, 10, 2), p('M21 16l-5-5-9 9')],
  notificaciones: [p('M6 16V11a6 6 0 0 1 12 0v5l2 2H4z'), p('M10 20a2 2 0 0 0 4 0')],
  candado: [r(5, 11, 14, 10, 2), p('M8 11V8a4 4 0 0 1 8 0v3')],
  papelera: [p('M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3')],
  detener: [r(6, 6, 12, 12, 2)],
  camara: [p('M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z'), c(12, 13, 4)],
  reloj: [c(12, 12, 9), p('M12 7v5l3 2')],
} as const satisfies Record<string, readonly Shape[]>;

export type IconName = keyof typeof SHAPES;

export function Icon({ name, size = 22, color = colors.ink }: IconProps & { name: IconName }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      {(SHAPES[name] as readonly Shape[]).map((shape, index) => {
        if (shape.kind === 'path') return <Path key={index} d={shape.d} />;
        if (shape.kind === 'circle') return <Circle key={index} cx={shape.cx} cy={shape.cy} r={shape.r} />;
        return <Rect key={index} x={shape.x} y={shape.y} width={shape.width} height={shape.height} rx={shape.rx} />;
      })}
    </Svg>
  );
}
