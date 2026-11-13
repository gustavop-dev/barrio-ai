This is an Expo/React Native mobile application. Prioritize mobile-first patterns, performance, and cross-platform compatibility.

## 0ff1ce: rules for porting a screen

- The PWA (`../oficina/src/pages/*`) is the reference for design, copy and behaviour. Port, do not redesign.
- API calls, hooks, query keys, types and pure logic come from `@compartido/*` (`../compartido/src`). Never copy them into `movil/`: if something the screen needs is still in `oficina/`, move it to `compartido/` and leave a re-export in its old place (the PWA must keep passing `npm run typecheck && npm run lint && npx vitest run && npm run build`).
- Every duration, spring, easing, gesture threshold and haptic comes from `src/theme/motion.ts`; add a named token there (and a row in `MOTION.md`) instead of writing a number in a screen.
- Colours, type and spacing come from `src/theme/tokens.ts`; UI pieces from `src/components/ui`.
- Screens pad their scroll content with `useContentInsets()` (the bottom bar floats over them).
- Tests: Jest with `src/test/render.tsx` and the fake backend `src/test/server.ts` (no network, no paid calls).

## Expo has changed — do not trust your training data

Expo ships breaking changes every SDK release. APIs you remember are likely renamed, moved, or removed. Before writing any code that touches an Expo, EAS, or React Native API:

1. Read the major version of the `expo` package in `package.json`.
2. Fetch the matching versioned docs: `https://docs.expo.dev/versions/v<major>.0.0/`
3. For anything else, fetch https://docs.expo.dev/llms.txt — an index of all Expo docs with corrections to common LLM misconceptions. Follow its links to the specific page you need; never answer from memory.

## Commands

Use `bunx` instead of `npx` if the project uses bun (`bun.lock` present).

```bash
npx expo install <package>  # ALWAYS use instead of npm/yarn/pnpm/bun add — resolves SDK-compatible versions
npx expo start              # start the dev server
npx expo lint               # lint
npx tsc --noEmit            # typecheck
npx expo-doctor             # diagnose dependency and config issues
npx expo install --fix      # fix incompatible package versions
```

Run lint and typecheck before declaring any task done.

## Navigation & Routing

- Use **Expo Router** for all navigation. Routes live in `src/app/` — every file there is a screen, `_layout.tsx` files define navigators. Keep non-route code (components, hooks, utils) outside `src/app/`.
- The import aliases (`@/`, `@compartido/`) are resolved in `metro.config.js` and `jest.config.js`; Expo's automatic tsconfig paths are off (`experiments.tsconfigPaths: false`).
- Import `Link`, `router`, and `useLocalSearchParams` from `expo-router`.
- Docs: https://docs.expo.dev/router/introduction.md

## Building with EAS

Use EAS to build, sign, and submit the app in the cloud (`eas build`, `eas submit`) and to ship over-the-air updates (`eas update`) — no local Xcode or Android Studio required. Run EAS CLI as `bunx eas-cli <command>` in Bun projects, or `npx eas-cli@latest <command>` otherwise; substitute that for bare `eas` in docs examples.
Docs: https://docs.expo.dev/eas/index.md

OTA updates are on: `expo-updates`, `runtimeVersion` policy `fingerprint`, channels `preview` and `production` in `eas.json`, and `.github/workflows/eas-update.yml` publishes the `preview` branch on every push to main that touches `movil/` or `compartido/`; when the push carries backend changes the server does not run yet, it first waits for the deploy (it polls `/health`, whose `revision` is the deployed commit). A JavaScript change reaches installed APKs by itself. A native change (adding, removing or upgrading a module with native code, a new config plugin, or native fields in `app.json`) changes the fingerprint and only reaches users with a new APK: say so in the PR. Never run `eas build` or `eas update` yourself unless asked. Details: README, «Actualizaciones OTA».

## Rules

- If `ios/` and `android/` directories do not exist, they are generated (Continuous Native Generation). Never create or edit them by hand — configure native behavior in `app.json` and config plugins.
- Expo Go only includes its bundled native modules. After adding a library with native code, the app needs a development build: `npx expo run:ios|android` locally, or `eas build --profile development`.
- Prefer recommended Expo modules over third-party libraries, and check your available skills before adding dependencies. Docs: https://docs.expo.dev/versions/latest/index.md
