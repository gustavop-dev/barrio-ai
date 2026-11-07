// Metro for the native app. Two things beyond Expo's defaults:
// 1. compartido/ (API types, endpoints, hooks and logic shared with the PWA) lives next to this app,
//    outside its root: watch it, and resolve its bare imports (TanStack Query) from this app's
//    node_modules so both use the same copy.
// 2. The import aliases of tsconfig.json (`@/` → src/, `@compartido/` → ../compartido/src/). Expo's
//    automatic tsconfig paths are off in app.json because tsconfig maps TanStack to a .d.ts for types.
const path = require('node:path');
const { getDefaultConfig } = require('expo/metro-config');

const projectRoot = __dirname;
const compartido = path.resolve(projectRoot, '../compartido');

const config = getDefaultConfig(projectRoot);

config.watchFolders = [...(config.watchFolders ?? []), compartido];
config.resolver.nodeModulesPaths = [path.resolve(projectRoot, 'node_modules')];

const ALIASES = [
  ['@compartido/', path.join(compartido, 'src') + path.sep],
  ['@/', path.join(projectRoot, 'src') + path.sep],
];

const upstream = config.resolver.resolveRequest;
config.resolver.resolveRequest = (context, moduleName, platform) => {
  const resolve = upstream ?? context.resolveRequest;
  for (const [prefix, target] of ALIASES) {
    if (moduleName.startsWith(prefix)) return resolve(context, target + moduleName.slice(prefix.length), platform);
  }
  return resolve(context, moduleName, platform);
};

module.exports = config;
