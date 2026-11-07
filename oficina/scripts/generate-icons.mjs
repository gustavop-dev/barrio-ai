// Generates the PWA icons from the 0ff1ce isotype (public/brand/isotipo.svg).
//
//   npm run icons
//
// Output: public/icons/{icon-192,icon-512,icon-maskable-512,apple-touch-icon,favicon-32,badge-96}.png
import { mkdir, readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const source = join(root, 'public/brand/isotipo.svg');
const out = join(root, 'public/icons');

const BRAND = '#0FF1CE';
const svg = await readFile(source, 'utf8');
// The "01" glyph group, already placed on the 512×512 artboard of the isotype.
const glyph = svg.match(/<g transform="[^"]+">[\s\S]*?<\/g>/)?.[0];
if (!glyph) throw new Error('No encuentro el glifo del isotipo');

/** The glyph centred on 512×512, scaled around the centre (the isotype draws it at scale 1). */
const centred = (scale, fill) =>
  `<g transform="translate(256 256) scale(${scale}) translate(-256 -256)">${fill ? glyph.replaceAll('#1E1E2B', fill) : glyph}</g>`;

const artboard = (body) => Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">${body}</svg>`);

async function render(file, size, input) {
  await sharp(input, { density: 384 }).resize(size, size).png({ compressionLevel: 9 }).toFile(join(out, file));
  console.log(`${file} ${size}×${size}`);
}

await mkdir(out, { recursive: true });
// "any": the isotype as drawn, rounded corners included.
await render('icon-192.png', 192, Buffer.from(svg));
await render('icon-512.png', 512, Buffer.from(svg));
await render('favicon-32.png', 32, Buffer.from(svg));
// Maskable: full-bleed brand colour with the glyph inside the 80 % safe zone.
await render('icon-maskable-512.png', 512, artboard(`<rect width="512" height="512" fill="${BRAND}"/>${centred(0.82)}`));
// iOS rounds the corners itself and shows transparency as black: full-bleed square.
await render('apple-touch-icon.png', 180, artboard(`<rect width="512" height="512" fill="${BRAND}"/>${centred(1)}`));
// Android notification badge: only the alpha channel matters, white glyph on transparent.
await render('badge-96.png', 96, artboard(centred(1.6, '#FFFFFF')));
