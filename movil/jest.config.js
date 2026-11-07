// Jest for the native app and for compartido/ (shared with the PWA), with Expo's preset.
// The aliases mirror tsconfig.json and metro.config.js; `modulePaths` lets compartido/ (no
// node_modules of its own) resolve TanStack Query from this app.
module.exports = {
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
  testTimeout: 20_000,
};
