// Generates the native app icon, adaptive icon layers, splash image, the top-bar signature and the
// pixel portraits from the 0ff1ce brand files of the PWA (oficina/public/brand). Run from movil/:
//
//   node scripts/generate-icons.mjs
//
// It needs `sharp`: it uses the PWA's copy (oficina/node_modules, after `npm ci` there).
import { copyFile, mkdir, readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const brand = join(root, '../oficina/public/brand');
const out = join(root, 'assets');
const require = createRequire(join(root, '../oficina/package.json'));
const sharp = require('sharp');

const BRAND = '#0FF1CE';
const isotipo = await readFile(join(brand, 'isotipo.svg'), 'utf8');
const glyph = isotipo.match(/<g transform="[^"]+">[\s\S]*?<\/g>/)?.[0];
if (!glyph) throw new Error('No encuentro el glifo del isotipo');

const centred = (scale, fill) =>
  `<g transform="translate(256 256) scale(${scale}) translate(-256 -256)">${fill ? glyph.replaceAll('#1E1E2B', fill) : glyph}</g>`;
const artboard = (body) => Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">${body}</svg>`);

async function render(file, width, height, input) {
  await sharp(input, { density: 600 }).resize(width, height).png({ compressionLevel: 9 }).toFile(join(out, file));
  console.log(`${file} ${width}×${height}`);
}

await mkdir(join(out, 'brand'), { recursive: true });
// iOS and the store listing: full-bleed brand square (the system rounds the corners).
await render('icon.png', 1024, 1024, artboard(`<rect width="512" height="512" fill="${BRAND}"/>${centred(1)}`));
// Android adaptive icon: the glyph inside the 66 % safe zone over the brand colour (app.json backgroundColor).
await render('android-icon-foreground.png', 1024, 1024, artboard(centred(0.62)));
// Android 13 themed icon: only the alpha channel counts.
await render('android-icon-monochrome.png', 1024, 1024, artboard(centred(0.62, '#FFFFFF')));
// Splash: the isotype as drawn (rounded corners) on papel.
await render('splash-icon.png', 512, 512, Buffer.from(isotipo));
// Android notification icon: white glyph on transparent.
await render('notification-icon.png', 96, 96, artboard(centred(1.6, '#FFFFFF')));
// Top bar signature, 28 px tall at 3×.
await render('brand/firma-horizontal.png', 273, 84, await readFile(join(brand, 'firma-horizontal.svg')));
// The inverse logo over the login hero, 34 px tall at 3×.
await render('brand/logo-inverso.png', 360, 102, await readFile(join(brand, 'logo-inverso.svg')));
// Login illustration, as in the PWA.
await copyFile(join(brand, 'login-oficina-tarde.png'), join(out, 'brand/login-oficina-tarde.png'));
await copyFile(join(brand, 'CREDITS.txt'), join(out, 'brand/CREDITS.txt'));

// Pixel portraits and the librarian's idle frames, scaled with nearest neighbour (React Native has no
// `image-rendering: pixelated`). Coordinates come from compartido/src/logic/atlas.ts.
const atlasTs = await readFile(join(root, '../compartido/src/logic/atlas.ts'), 'utf8');
const table = (name) => {
  const body = atlasTs.match(new RegExp(`const ${name}[^=]*=\\s*\\[([\\s\\S]*?)\\];`))?.[1];
  if (!body) throw new Error(`No encuentro ${name} en atlas.ts`);
  return body;
};
const portraits = [...table('PORTRAIT').matchAll(/\[(\d+),\s*(\d+)\]/g)].map((m) => [Number(m[1]), Number(m[2])]);
const idleRows = table('IDLE_ROW').split(',').map((v) => Number(v.trim())).filter((v) => Number.isFinite(v));
const CROP_TOP = 9;
const W = 16;
const H = 20;
const SCALE = 4;
const atlas = join(brand, 'sprites-atlas.png');
const crop = (x, y) => sharp(atlas).extract({ left: x, top: y + CROP_TOP, width: W, height: H }).resize(W * SCALE, H * SCALE, { kernel: 'nearest' }).png().toBuffer();

async function strip(file, frames) {
  const tiles = await Promise.all(frames.map(([x, y]) => crop(x, y)));
  await sharp({ create: { width: W * SCALE * tiles.length, height: H * SCALE, channels: 4, background: { r: 0, g: 0, b: 0, alpha: 0 } } })
    .composite(tiles.map((input, index) => ({ input, left: index * W * SCALE, top: 0 })))
    .png({ compressionLevel: 9 })
    .toFile(join(out, file));
  console.log(`${file} ${tiles.length} × ${W * SCALE}×${H * SCALE}`);
}

// One portrait per character sheet (p0–p13), in sheet order.
await strip('brand/retratos.png', portraits);
// The librarian (p13) facing the viewer: direction 3 starts at frame 18 of the idle row, 6 frames.
const librarianRow = idleRows[13];
await strip('brand/bibliotecario-reposo.png', Array.from({ length: 6 }, (_, f) => [(18 + f) * W, librarianRow]));
