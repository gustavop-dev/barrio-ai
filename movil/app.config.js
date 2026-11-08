// Dynamic config over app.json. It changes nothing unless OFFICE_QA_BUILD=1, which only the QA workflow
// (.github/workflows/qa-movil.yml) sets. That build talks to a demo backend on the CI runner over plain HTTP
// (http://10.0.2.2:8787, the host as the Android emulator sees it), and release builds block cleartext traffic;
// it must also never ask Expo's update server for an OTA at launch. EAS profiles never set the variable, so the
// APK and the AAB keep Android's default (HTTPS only), their updates and the same native fingerprint.
const { withAndroidManifest } = require('expo/config-plugins');

/** QA build only: allow cleartext HTTP in the release manifest (the debug manifest already does). */
function withQaCleartext(config) {
  return withAndroidManifest(config, (mod) => {
    const application = mod.modResults.manifest.application?.[0];
    if (application) application.$['android:usesCleartextTraffic'] = 'true';
    return mod;
  });
}

/**
 * QA build only: the development client's menu stays out of the way of Maestro (qa-sesion). Its floating «Tools»
 * button sits over the top bar's Ajustes gear, and the menu opens by itself at launch and after clearState. These
 * manifest keys are the defaults expo-dev-menu reads (DevMenuPreferences); release builds don't include the menu.
 */
const QA_DEV_MENU = {
  EXDevMenuShowFloatingActionButton: 'false',
  EXDevMenuShowsAtLaunch: 'false',
  EXDevMenuIsOnboardingFinished: 'true',
};

function withQaDevMenu(config) {
  return withAndroidManifest(config, (mod) => {
    const application = mod.modResults.manifest.application?.[0];
    if (!application) return mod;
    const meta = (application['meta-data'] = application['meta-data'] ?? []);
    for (const [name, value] of Object.entries(QA_DEV_MENU)) {
      const existing = meta.find((item) => item.$['android:name'] === name);
      if (existing) existing.$['android:value'] = value;
      else meta.push({ $: { 'android:name': name, 'android:value': value } });
    }
    return mod;
  });
}

module.exports = ({ config }) => {
  if (process.env.OFFICE_QA_BUILD !== '1') return config;
  // The emulator runs the JS bundled in the APK: no OTA check against u.expo.dev.
  return withQaDevMenu(withQaCleartext({ ...config, updates: { ...config.updates, enabled: false } }));
};
