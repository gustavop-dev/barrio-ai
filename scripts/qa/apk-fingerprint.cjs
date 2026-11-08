// CI only, after npm ci and export:embed, BEFORE prebuild. Uses the lockfile's
// @expo/fingerprint API (0.21.x / SDK 58), without downloading a different CLI.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { createRequire } = require('node:module');

const project = path.resolve(__dirname, '../../movil');
const projectRequire = createRequire(path.join(project, 'package.json'));
const { createFingerprintAsync } = projectRequire('@expo/fingerprint');

function resourcesAt(directory, prefix = '') {
  const resources = {};
  for (const entry of fs.readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    const name = prefix + entry.name;
    const filename = path.join(directory, entry.name);
    if (entry.isDirectory()) Object.assign(resources, resourcesAt(filename, `${name}/`));
    // keep.xml is generated from the same asset list, but its ordering can change
    // when JS imports move. Android compiles it; never overlay it as plain XML.
    else if (name !== 'raw/keep.xml') resources[name] = crypto.createHash('sha256').update(fs.readFileSync(filename)).digest('hex');
  }
  return resources;
}

async function main() {
  const [resDir, reportPath] = process.argv.slice(2);
  if (!resDir || !reportPath) throw new Error('Usage: apk-fingerprint.cjs <exported res dir> <report.json>');
  const resources = resourcesAt(resDir);
  // All resources referenced by Metro participate, including dependency fonts,
  // and assets newly required by JS. New resource IDs require AAPT/Gradle.
  const extraSources = [
    { type: 'contents', id: 'qa-metro-resources', contents: JSON.stringify(resources), reasons: ['qa Android resource table'] },
    { type: 'contents', id: 'qa-build-environment', contents: JSON.stringify({
      OFFICE_QA_BUILD: process.env.OFFICE_QA_BUILD,
      EXPO_PUBLIC_API_URL: process.env.EXPO_PUBLIC_API_URL,
      NODE_ENV: process.env.NODE_ENV,
      EXPO_NO_DOTENV: process.env.EXPO_NO_DOTENV,
      architecture: 'x86_64', nodeMajor: process.versions.node.split('.')[0],
    }), reasons: ['qa build variant'] },
  ];
  for (const filePath of ['package.json', 'package-lock.json', 'app.json', 'app.config.js', 'eas.json', 'plugins']) {
    const absolute = path.join(project, filePath);
    if (fs.existsSync(absolute)) extraSources.push({
      type: fs.statSync(absolute).isDirectory() ? 'dir' : 'file', filePath, reasons: ['qa native inputs'],
    });
  }
  const fingerprint = await createFingerprintAsync(project, {
    platforms: ['android'], preset: 'strict', sourceSkips: 0, extraSources,
    // Expo normally ignores the raw config files in favour of their evaluated
    // values. Also hash the QA manifest plugin's implementation in app.config.js.
    ignorePaths: ['!app.config.js', '!app.json'],
  });
  if (!/^[a-f0-9]{40,64}$/.test(fingerprint.hash)) throw new Error('Invalid native fingerprint');
  fs.writeFileSync(reportPath, JSON.stringify({ fingerprint, resources }, null, 2) + '\n');
  fs.appendFileSync(process.env.GITHUB_OUTPUT, `hash=${fingerprint.hash}\n`);
  console.log(`Native fingerprint: ${fingerprint.hash} (${Object.keys(resources).length} Metro resources)`);
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
