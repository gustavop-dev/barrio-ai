// Execute the installed Worklets compiler's serialized functions in a separate VM. Jest's normal
// native mocks do not catch eager-closure TDZs, captured JS functions or unshareable engine state.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { runInNewContext } from 'node:vm';
import { OfficeEngine } from '@compartido/scene/engine';
import type * as Runtime from '@compartido/scene/runtime';

type Worklet = ((...args: unknown[]) => unknown) & { __initData?: { code: string }; __closure?: unknown[] };
function loadCompiledRuntime() {
  const babel = require('@babel/core');
  const modules = new Map<string, { exports: Record<string, unknown> }>();
  const load = (path: string): Record<string, unknown> => {
    const previous = modules.get(path); if (previous) return previous.exports;
    const module = { exports: {} }; modules.set(path, module);
    const { code } = babel.transformSync(readFileSync(path, 'utf8'), { filename: path, configFile: false, babelrc: false,
      plugins: ['@babel/plugin-transform-typescript', 'react-native-worklets/plugin', '@babel/plugin-transform-modules-commonjs'] });
    runInNewContext(code, { module, exports: module.exports, global: { Error }, require: (name: string) => load(resolve(dirname(path), `${name}.ts`)) });
    return module.exports;
  };
  return load(resolve(__dirname, '../../../compartido/src/scene/runtime.ts')) as unknown as typeof Runtime;
}
function uiClone<T>(input: T, memo = new Map<unknown, unknown>()): T {
  if (input === null || typeof input !== 'object' && typeof input !== 'function') return input;
  if (memo.has(input)) return memo.get(input) as T;
  if (typeof input === 'function') {
    const worklet = input as Worklet;
    if (!worklet.__initData) throw new Error('Captured a JS function instead of a worklet');
    const context = { __closure: uiClone(worklet.__closure, memo) };
    const fn = runInNewContext(worklet.__initData.code).bind(context); memo.set(input, fn); return fn;
  }
  if (Array.isArray(input)) return input.map((v) => uiClone(v, memo)) as T;
  const object: Record<string, unknown> = {}; memo.set(input, object);
  for (const [key, value] of Object.entries(input)) object[key] = uiClone(value, memo);
  return object as T;
}
it('runs the compiled shared choreography on an isolated UI runtime with no JS class or callback', () => {
  const runtime = loadCompiledRuntime();
  const create = uiClone(runtime.createScene), ingest = uiClone(runtime.ingestScene), step = uiClone(runtime.stepScene), snapshot = uiClone(runtime.sceneSnapshot);
  const s = create();
  const js = new OfficeEngine({ wallClock: () => 0 });
  const events = [
    { id: 1, ts: '2026-11-07T15:00:00Z', tipo: 'consulta_biblioteca', rol: 'copywriter_a', destino: 'biblioteca', detalle: 'clase 03' },
    { id: 2, ts: '2026-11-07T15:00:01Z', tipo: 'entrega', rol: 'perfil', destino: 'posicionamiento', detalle: '' },
    { id: 3, ts: '2026-11-07T15:00:02Z', tipo: 'publicacion', rol: 'operador_cuenta', destino: 'linkedin', detalle: '' },
  ];
  ingest(s, events); js.ingest(events);
  for (let i = 0; i < 4000; i++) { step(s, 16); js.step(16); }
  expect(JSON.parse(JSON.stringify(s.actors))).toEqual(JSON.parse(JSON.stringify(js.actors)));
  expect(snapshot(s)).toEqual(js.getSnapshot());
  expect(s.tasks).toHaveLength(0);
});
