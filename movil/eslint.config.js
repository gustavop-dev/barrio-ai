// Same rules as the PWA (oficina/eslint.config.js), for React Native. `npm run lint` also lints
// ../compartido, whose own eslint.config.js reuses this file.
const js = require('@eslint/js');
const globals = require('globals');
const reactHooks = require('eslint-plugin-react-hooks');
const tseslint = require('typescript-eslint');

module.exports = tseslint.config(
  { ignores: ['node_modules', 'dist', '.expo', 'android', 'ios', 'coverage', 'expo-env.d.ts'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended, reactHooks.configs.flat.recommended],
    languageOptions: { ecmaVersion: 2023, globals: { ...globals.browser } },
    rules: {
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    },
  },
  {
    files: ['**/*.test.{ts,tsx}', 'jest.setup.tsx', 'src/test/**'],
    languageOptions: { globals: { ...globals.jest, ...globals.node } },
    // jest.mock factories load modules with require().
    rules: { '@typescript-eslint/no-require-imports': 'off' },
  },
  {
    files: ['*.config.js', 'scripts/**/*.{js,mjs}'],
    extends: [js.configs.recommended],
    languageOptions: { sourceType: 'commonjs', globals: { ...globals.node } },
  },
  {
    files: ['scripts/**/*.mjs'],
    languageOptions: { sourceType: 'module' },
  },
);
