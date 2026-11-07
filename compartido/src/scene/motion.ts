/** Choreography defaults shared by the PWA and native app. Native overrides enter through theme/motion.ts. */
export const SCENE_MOTION = {
  walkSpeed: 40, startGap: 1800, summaryHold: 2600, ambientFirst: 9000, ambientEvery: 20000,
  fadeMs: 500, questionMs: 1800, bookMs: 2200, readMs: 1600, searchMs: 1400,
  librarianBookMs: 1200, handBookMs: 900, sheetMs: 2200, handSheetMs: 900,
  conversationMs: 1800, deliveryMs: 1500, outsideMs: 1300, doneMs: 2000,
  returnMs: 800, coffeeMs: 2600, chatMs: 2000, chatReplyMs: 2200,
  runFrameMs: 110, idleFrameMs: 220, lightMs: 700, bubbleFrameMs: 300,
} as const;
export type SceneMotion = { [K in keyof typeof SCENE_MOTION]: number };
