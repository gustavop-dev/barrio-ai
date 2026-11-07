// 0ff1ce design system v1 as a typed theme: the same values as oficina/src/styles/tokens.css and the
// canvas export (diseno-0ff1ce/tokens.json). Read the rule next to a colour before using it.
import type { TextStyle } from 'react-native';

export const colors = {
  /** The name's colour. Fills only (isotype, avatar, primary button, highlighted blocks); text only on tinta. */
  brand: '#0ff1ce',
  /** Text and icons on a brand fill (11.4:1). Never white. */
  onBrand: '#1e1e2b',
  /** The readable brand colour: links, highlighted text, TRABAJANDO. Text on papel, superficie and brandLight. */
  brandDeep: '#00715e',
  /** Soft background behind tinta or brandDeep: highlights, selected row, active tab pill. */
  brandLight: '#d2fbf3',
  /** Main text; also the dark brand background. */
  ink: '#1e1e2b',
  /** Secondary text, metadata, and the borders of fields and controls. */
  inkSoft: '#565972',
  /** Page background. */
  paper: '#f7f6f0',
  /** Cards, panels, chips, bars. */
  surface: '#fffef8',
  /** Dividers and card borders, 1px. Decorative: never a control border (those are inkSoft). */
  line: '#dedfd4',
  /** Warm accent: pending, notes, highlight. Fill only, with ink text. */
  postIt: '#f8d47d',
  /** Errors, stopped machine. Text on papel/superficie, always with a word that says what happened. */
  alert: '#a54e35',
  /** White on an alert fill: critical counter and badges. */
  onAlert: '#ffffff',
  /** Info tone: text #3d5a7a on #e4ecf3. Questions, «en espera», label chips. */
  info: '#3d5a7a',
  infoLight: '#e4ecf3',
  /** The sprites' blue: dots and bars only, never text. */
  spriteBlue: '#647e99',
  /** Sheet and modal backdrop (tinta at 45 %). */
  backdrop: 'rgba(30, 30, 43, 0.45)',
  /** The pressed primary button (brand mixed 15 % with ink). */
  brandPressed: '#10d2b5',
} as const;

/** Calendar layers: fills and dots only. */
export const layers = {
  tuyo: colors.postIt,
  publicaciones: colors.brandDeep,
  red: colors.spriteBlue,
  conversaciones: colors.brand,
  sistema: colors.alert,
} as const;

export const space = {
  1: 4,
  /** Icon to text, between chips, title to subtitle. */
  2: 8,
  3: 12,
  /** Button and card padding, between paragraphs. */
  4: 16,
  /** Between blocks inside a card. */
  6: 24,
  /** Between sections. */
  10: 40,
} as const;

export const radius = {
  /** Fields, small buttons, thumbnails. */
  sm: 6,
  /** Cards, buttons, images. */
  md: 12,
  /** Sheets (top corners). */
  sheet: 16,
  /** Status chips and pill labels. */
  pill: 999,
} as const;

/** Shell sizes at mobile width (390 × 844 design screens). */
export const shell = {
  topBarHeight: 56,
  tabBarHeight: 64,
  /** Minimum touch target. */
  touch: 44,
  captureButton: 60,
  captureButtonHolding: 72,
  /** How far the capture button rises above the bar. */
  captureLift: 22,
  /** Horizontal page padding. */
  gutter: 16,
} as const;

/** Ubuntu as loaded by expo-font (@expo-google-fonts/ubuntu). Android needs one family per weight. */
export const fonts = {
  regular: 'Ubuntu_400Regular',
  bold: 'Ubuntu_700Bold',
} as const;

type TypeStyle = Pick<TextStyle, 'fontFamily' | 'fontSize' | 'lineHeight' | 'letterSpacing' | 'textTransform'>;

/** The type scale of tokens.json. letterSpacing is in points (em × size). */
export const type = {
  /** Only the live name 0ff1ce. The only bold style. */
  nombre: { fontFamily: fonts.bold, fontSize: 48, lineHeight: 52, letterSpacing: -0.96 },
  display: { fontFamily: fonts.regular, fontSize: 56, lineHeight: 60, letterSpacing: -1.12 },
  /** Section and page titles. */
  titulo: { fontFamily: fonts.regular, fontSize: 32, lineHeight: 40, letterSpacing: -0.32 },
  /** Subtitles (inkSoft) and card titles. */
  subtitulo: { fontFamily: fonts.regular, fontSize: 22, lineHeight: 30 },
  /** Running text. */
  cuerpo: { fontFamily: fonts.regular, fontSize: 16, lineHeight: 24 },
  /** Metadata, footnotes, field help (inkSoft). */
  detalle: { fontFamily: fonts.regular, fontSize: 14, lineHeight: 20 },
  /** Labels and status chips, always UPPERCASE. */
  etiqueta: { fontFamily: fonts.regular, fontSize: 12, lineHeight: 16, letterSpacing: 0.72, textTransform: 'uppercase' },
} as const satisfies Record<string, TypeStyle>;

export type TypeVariant = keyof typeof type;

/** The five tones of the vocabularies in DISENO-VISTAS.md. */
export type Tone = 'ok' | 'warn' | 'bad' | 'muted' | 'info';

export const theme = { colors, layers, space, radius, shell, fonts, type } as const;
export type Theme = typeof theme;

// Pixel-art room palette, kept identical to the PWA artwork.
export const officeRoom = {
  outside: '#4b5655',
  plaster: '#eee5cc',
  plasterLight: '#fff5dd',
  wainscot: '#9ba998',
  skirting: '#667b70',
  wall: '#536b61',
  wallLight: '#b9c5ae',
  base: '#526c61',
  kitchenEdge: '#aa987f',
  screenOff: '#33403f',
  screenOffLine: '#3f4e4c',
  screenLine: '#7fd9c9',
  white: '#ffffff',
  book: '#a54e35',
  bookSpine: '#7a3624',
  coffee: '#8a6552',
  steam: '#b9b5ad',
};

