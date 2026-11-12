/** Choreography defaults shared by the PWA and native app. Native overrides enter through theme/motion.ts. */
export const SCENE_MOTION = {
  walkSpeed: 40, startGap: 1800, summaryHold: 2600,
  fadeMs: 500, questionMs: 1800, bookMs: 2200, readMs: 1600, searchMs: 1400,
  librarianBookMs: 1200, handBookMs: 900, sheetMs: 2200, handSheetMs: 900,
  conversationMs: 1800, deliveryMs: 1500, outsideMs: 1300, doneMs: 2000,
  returnMs: 800,
  runFrameMs: 110, idleFrameMs: 220, lightMs: 700, bubbleFrameMs: 300,
  /** MovOficina: integer-pixel selection feedback, never a scaled/springy sprite. */
  hopPx: 2, hopSettlePx: 1, hopStepMs: 90, hopEndMs: 180,
  bracketPx: 7, bracketMs: 120,
  /** MovOficina: the envelope accelerates by 0.9 px every 16 ms, then waits for Operación. */
  mailX: 98, mailStartY: -6, mailLandingY: 68, mailAcceleration: 0.9, mailStepMs: 16,
  captureQuestionMs: 700, captureSheetMs: 1600, capturePickupMs: 500, captureHandoffMs: 1800,
  captureFreePollMs: 300,
  /** The game room: how often the free agents are looked at, how long they stay at a pastime, how they talk. */
  lifeTickMs: 250, restLeaveMinMs: 1200, restLeaveMaxMs: 6000, stayMinMs: 16000, stayMaxMs: 42000,
  emoteGapMinMs: 3500, emoteGapMaxMs: 9000, emoteMs: 1900, replyMs: 900,
  /** An agent stays at its seat this long after its work; a called one comes for this long; the work before a delivery. */
  dutyMs: 15000, callMs: 30000, workMs: 2200, awaitSeatMs: 16000, hurryFactor: 1.6,
  /** Lights fade in and out; a party now and then; the dance, the disco floor, the string lights and the screens. */
  lightFadeMs: 900, partyMs: 30000, partyFirstMs: 60000, partyGapMinMs: 180000, partyGapMaxMs: 420000,
  danceStepMs: 380, discoMs: 420, bulbMs: 600, screenFrameMs: 160,
} as const;
export type SceneMotion = { [K in keyof typeof SCENE_MOTION]: number };
