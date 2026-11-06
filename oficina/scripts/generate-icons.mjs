// Generates the PWA icons from a character of the LimeZu pack already in
// public/assets, scaled with nearest-neighbour so the pixels stay crisp.
//
//   npm run icons
//
// Source: person0-idle_anim.png, frame facing the viewer (direction 3, frame 0).
// Output: public/icons/{icon-192,icon-512,icon-maskable-512,apple-touch-icon,favicon-32,badge-96}.png
import { mkdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const source = join(root, 'public/assets/person0-idle_anim.png');
const out = join(root, 'public/icons');

const FRAME = { left: 18 * 16, top: 0, width: 16, height: 32 };
const BACKGROUND = { r: 0x26, g: 0x3c, b: 0x33, alpha: 1 }; // rail green of the office
const FLOOR = { r: 0xf8, g: 0xd4, b: 0x7d, alpha: 1 }; // brass

/** The frame has empty rows above the head: crop to the visible pixels first. */
async function trimmed() {
  const frame = await sharp(source).extract(FRAME).png().toBuffer();
  const { data, info } = await sharp(frame).trim().png().toBuffer({ resolveWithObject: true });
  return { data, width: info.width, height: info.height };
}

async function character(scale) {
  const sprite = await trimmed();
  return {
    input: await sharp(sprite.data)
      .resize(sprite.width * scale, sprite.height * scale, { kernel: sharp.kernel.nearest })
      .png()
      .toBuffer(),
    width: sprite.width * scale,
    height: sprite.height * scale,
  };
}

/**
 * Square icon: character centred on the office green, standing on a brass rug.
 * `safe` is the fraction of the side the character may occupy (maskable ≤ 0.8).
 */
async function icon(size, file, { safe = 0.72, rounded = false, rug = true } = {}) {
  const sprite = await trimmed();
  const scale = Math.max(1, Math.floor((size * safe) / Math.max(sprite.width, sprite.height)));
  const person = await character(scale);
  const left = Math.round((size - person.width) / 2);
  const top = Math.round((size - person.height) / 2);
  const layers = [];
  if (rug) {
    const rugH = Math.max(2, scale * 2);
    const rugW = Math.round(person.width * 1.4);
    const floor = await sharp({ create: { width: rugW, height: rugH, channels: 4, background: FLOOR } }).png().toBuffer();
    layers.push({ input: floor, left: Math.round((size - rugW) / 2), top: top + person.height - Math.round(rugH * 0.75) });
  }
  layers.push({ input: person.input, left, top });
  let image = sharp({ create: { width: size, height: size, channels: 4, background: BACKGROUND } }).composite(layers);
  if (rounded) {
    const radius = Math.round(size * 0.18);
    const mask = Buffer.from(`<svg width="${size}" height="${size}"><rect width="${size}" height="${size}" rx="${radius}" ry="${radius}"/></svg>`);
    image = sharp(await image.png().toBuffer()).composite([{ input: mask, blend: 'dest-in' }]);
  }
  await image.png({ compressionLevel: 9 }).toFile(join(out, file));
  console.log(`${file} ${size}×${size} (escala ×${scale})`);
}

/** Monochrome silhouette for the Android notification badge (alpha only matters). */
async function badge(size, file) {
  const sprite = await trimmed();
  const scale = Math.floor((size * 0.85) / Math.max(sprite.width, sprite.height));
  const person = await character(scale);
  const { data, info } = await sharp(person.input).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  for (let i = 0; i < data.length; i += 4) {
    data[i] = 255;
    data[i + 1] = 255;
    data[i + 2] = 255;
  }
  const white = await sharp(data, { raw: { width: info.width, height: info.height, channels: 4 } }).png().toBuffer();
  await sharp({ create: { width: size, height: size, channels: 4, background: { r: 0, g: 0, b: 0, alpha: 0 } } })
    .composite([{ input: white, left: Math.round((size - info.width) / 2), top: Math.round((size - info.height) / 2) }])
    .png({ compressionLevel: 9 })
    .toFile(join(out, file));
  console.log(`${file} ${size}×${size} (silueta)`);
}

await mkdir(out, { recursive: true });
await icon(192, 'icon-192.png', { rounded: true });
await icon(512, 'icon-512.png', { rounded: true });
await icon(512, 'icon-maskable-512.png', { safe: 0.55 });
await icon(180, 'apple-touch-icon.png');
await icon(32, 'favicon-32.png', { safe: 0.95, rug: false });
await badge(96, 'badge-96.png');
