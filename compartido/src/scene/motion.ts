/** Choreography defaults shared by the PWA and native app. Native overrides enter through theme/motion.ts. */
export const SCENE_MOTION = {
  walkSpeed: 40, startGap: 1800, summaryHold: 2600, ambientFirst: 9000, ambientEvery: 11000,
  fadeMs: 500, questionMs: 1800, bookMs: 2200, readMs: 1600, searchMs: 1400,
  librarianBookMs: 1200, handBookMs: 900, sheetMs: 2200, handSheetMs: 900,
  conversationMs: 1800, deliveryMs: 1500, outsideMs: 1300, doneMs: 2000,
  returnMs: 800, coffeeMs: 2600, chatMs: 2000, chatReplyMs: 2200,
  runFrameMs: 110, idleFrameMs: 220, lightMs: 700, bubbleFrameMs: 300,
  /** MovOficina: integer-pixel selection feedback, never a scaled/springy sprite. */
  hopPx: 2, hopSettlePx: 1, hopStepMs: 90, hopEndMs: 180,
  bracketPx: 7, bracketMs: 120,
  /** MovOficina: the envelope accelerates by 0.9 px every 16 ms, then waits for Operación. */
  mailX: 98, mailStartY: -6, mailLandingY: 68, mailAcceleration: 0.9, mailStepMs: 16,
  captureQuestionMs: 700, captureSheetMs: 1600, capturePickupMs: 500, captureHandoffMs: 1800,
  captureFreePollMs: 300,
} as const;
export type SceneMotion = { [K in keyof typeof SCENE_MOTION]: number };
