// Jest for the native app and for compartido/ (shared with the PWA), with Expo's preset.
// The aliases mirror tsconfig.json and metro.config.js; `modulePaths` lets compartido/ (no
// node_modules of its own) resolve TanStack Query from this app.
//
// <rootDir> is the repository, not movil/: Jest only measures coverage under its rootDir, and
// compartido/ sits next to movil/. So the preset and the resolver are given by path (the repository
// root has no node_modules). jest-expo reads babel and tsconfig.json from the current directory:
// run Jest from movil/ (`npm test`).
const path = require('node:path');

module.exports = {
  rootDir: path.resolve(__dirname, '..'),
  // An absolute preset is loaded as is: point at jest-expo's preset file, not at the package.
  preset: '<rootDir>/movil/node_modules/jest-expo/jest-preset.js',
  // Reanimated (and worklets) run their web implementation under Jest.
  resolver: '<rootDir>/movil/node_modules/react-native-reanimated/jest/resolver',
  roots: ['<rootDir>/movil/src', '<rootDir>/compartido/src'],
  moduleNameMapper: {
    // jest-expo turns tsconfig paths into mappings; the TanStack one points at a .d.ts (types only).
    '^@tanstack/react-query$': '<rootDir>/movil/node_modules/@tanstack/react-query',
    '^@/(.*)$': '<rootDir>/movil/src/$1',
    '^@compartido/(.*)$': '<rootDir>/compartido/src/$1',
  },
  modulePaths: ['<rootDir>/movil/node_modules'],
  setupFilesAfterEnv: ['<rootDir>/movil/jest.setup.tsx'],
  clearMocks: true,
  restoreMocks: true,
  testTimeout: 20_000,

  // Coverage (`npm test -- --coverage`, always on in CI) is report-only: no thresholds. Babel
  // instruments only these files; V8 coverage would also count every library each test loads and
  // made the suite more than twice as slow.
  coverageProvider: 'babel',
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
  coverageDirectory: '<rootDir>/movil/coverage',
  coverageReporters: ['text-summary', 'json-summary', 'lcov'],
};
