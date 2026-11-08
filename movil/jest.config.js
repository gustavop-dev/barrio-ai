// Jest for the native app and for compartido/ (shared with the PWA), with Expo's preset.
// The aliases mirror tsconfig.json and metro.config.js; `modulePaths` lets compartido/ (no
// node_modules of its own) resolve TanStack Query from this app.
const path = require('node:path');

const app = {
  rootDir: __dirname,
  preset: 'jest-expo',
  // Reanimated (and worklets) run their web implementation under Jest.
  resolver: 'react-native-reanimated/jest/resolver',
  roots: ['<rootDir>/src', '<rootDir>/../compartido/src'],
  moduleNameMapper: {
    // jest-expo turns tsconfig paths into mappings; the TanStack one points at a .d.ts (types only).
    '^@tanstack/react-query$': '<rootDir>/node_modules/@tanstack/react-query',
    '^@/(.*)$': '<rootDir>/src/$1',
    '^@compartido/(.*)$': '<rootDir>/../compartido/src/$1',
  },
  modulePaths: ['<rootDir>/node_modules'],
  setupFilesAfterEnv: ['<rootDir>/jest.setup.tsx'],
  clearMocks: true,
  restoreMocks: true,
};

// Coverage (`npm run test:cobertura`, always in CI) is report-only: no thresholds.
// compartido/ sits next to movil/, and Jest only measures files under the root config's rootDir:
// the root is the repository and this app is its only project (same tests, same settings).
// Babel's instrumenter (babel-jest) also skips files outside the directory Jest runs from, so
// `test:cobertura` runs Jest from the repository root, with EXPO_PROJECT_ROOT so Expo's Babel preset
// still treats movil/ as the project. (V8 coverage avoids that but counts every source line, types
// and comments included, and made the suite up to twice as slow.)
module.exports = {
  rootDir: path.resolve(__dirname, '..'),
  projects: [app],
  testTimeout: 20_000,
  coverageProvider: 'babel',
  // Relative to the repository: movil/src and compartido/src, without tests, fixtures or helpers.
  collectCoverageFrom: [
    'movil/src/**/*.{ts,tsx}',
    'compartido/src/**/*.{ts,tsx}',
    '!**/*.test.{ts,tsx}',
    '!**/*.suite.ts',
    '!**/*.d.ts',
    '!movil/src/test/**',
    '!compartido/src/fixtures/**',
    '!compartido/src/scene/testAPI.ts',
    '!**/diseno-movimiento/**',
  ],
  coverageDirectory: path.join(__dirname, 'coverage'),
  coverageReporters: ['text-summary', 'json-summary', 'lcov'],
};
