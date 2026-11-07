// compartido/ has no tooling of its own: it is linted, typechecked and tested from movil/
// (`cd movil && npm run lint && npm run typecheck && npm test`) and typechecked again by the PWA.
module.exports = require('../movil/eslint.config.js');
