// Dynamic config over app.json. It changes nothing unless OFFICE_QA_BUILD=1, which only the QA workflow
// (.github/workflows/qa-movil.yml) sets: that build talks to a demo backend on the CI runner over plain HTTP
// (http://10.0.2.2:8787, the host as the Android emulator sees it), and release builds block cleartext traffic.
// EAS profiles never set it, so the APK and the AAB keep Android's default (HTTPS only).
const { withAndroidManifest } = require('expo/config-plugins');

/** QA build only: allow cleartext HTTP in the release manifest (the debug manifest already does). */
function withQaCleartext(config) {
  return withAndroidManifest(config, (mod) => {
    const application = mod.modResults.manifest.application?.[0];
    if (application) application.$['android:usesCleartextTraffic'] = 'true';
    return mod;
  });
}

module.exports = ({ config }) => {
  if (process.env.OFFICE_QA_BUILD !== '1') return config;
  return withQaCleartext(config);
};
