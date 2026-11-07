# Motion design (Claude Design)

This is a copy of Gustavo's canvas «0ff1ce — Vistas móviles»: https://claude.ai/artifact/9ebjAHA228bpQJM9XP64ee. It is the source of truth for how the app moves. The values live in `../src/theme/motion.ts`, and `../MOTION.md` says where each token is used.

## What is here

- `tableros/*.dc.html`: the boards (390×844). The `Mov*` boards are the motion design; the others are the screen design.
- `canvas.json`: the canvas layout and the review notes for each phase. The `notes.movimiento*` entries explain how to play each board.
- `tokens.json`: the 0ff1ce design system (colours, type, spacing, radii).
- `assets/`: images used by the boards, named by their `/_blob/<id>` id:

  | File | What it is | Copy in the app |
  |---|---|---|
  | `9aa3da587c44b923cd4c0161de1156bc.png` | sprite atlas | `assets/brand/sprites-atlas.png` |
  | `65dfd866a8754b9feca0c6873e6ad260.png` | login office, afternoon | `assets/brand/login-oficina-tarde.png` |
  | `4479d1116e14b182306b566e8849750a.svg` | horizontal signature | PNG copy in `assets/brand/` |
  | `fdcebffddeff29a87f5018d7ec575dd5.svg` | inverse logo | PNG copy in `assets/brand/` |
  | `c3a34d0e228437f78c76b0c551d9b14f.svg` | isotype | |
  | `bc4592686e9eec0507e45c75a9c1b362.png` | still render of the whole office | `assets/brand/oficina-render.png` |

## How to read a board

Each board runs the same small motion engine in its `<script data-dc-script>`. It is a web approximation of Reanimated, and the notes say «the timings and springs are the same as the React Native code».

- **`TOK`**: `instant` 100, `fast` 180, `base` 260 and `slow` 400 ms, plus the springs `firm` `{ k: 260, c: 20 }` and `soft` `{ k: 160, c: 14 }`.
  - These are `durations`, `FIRM` and `SOFT` in `motion.ts`.
  - The springs integrate `−k·(x − target) − c·v` with mass 1, the same model as Reanimated. So `k` is `stiffness` and `c` is `damping`.
- **Curves:** `EASE_OUT = bezier(0.2, 0, 0, 1)` is used for what enters, and `EASE_IN = bezier(0.3, 0, 1, 1)` for what leaves. They are `easings.enter` and `easings.exit` in `motion.ts`.
- **`rubber(x, lim)`:** past the limit only 35 % of the drag is kept. It is `rubberBand` and `RUBBER` in `motion.ts`.
- **`Spring` and `Tween` objects** hold each animated value. The board's state (`M = { … }`) lists them; its step and handlers say when each one moves, to what, and with which token. Staggers are delays added per item.
- **Haptics:** a «HÁPTICO» label marks where the phone would vibrate, and the code names the kind.
- **Reduced motion:** the «menos movimiento» control shows the accessible version of every board. The «velocidad» control only slows the preview.

The `Mov*` boards are:
- **Phase 1:** Captura, Navegación and Hojas.
- **Phase 2:** Tu turno, Notificaciones and Oficina.
- **Phase 3:** Entrada (from login to the Oficina), Calendario, Resultados, Detalle (shared element from a list to a detail) and Micro (buttons, switch, chips, copy, text field, loading).
