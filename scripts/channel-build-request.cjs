// Pure CJS helper for channel build requests.
// Kept in CJS to avoid ESM/CJS require cycle with product-identity.cjs.

const { execFileSync } = require('node:child_process')
const path = require('node:path')

/**
 * Build-only structured bridge; never read by the installed runtime.
 * @param {NodeJS.ProcessEnv} [env]
 * @returns {any}
 */
function channelBuildRequest(env = process.env) {
  if (!env._MOOR_CHANNEL_REQUEST_JSON) return null
  const value = JSON.parse(env._MOOR_CHANNEL_REQUEST_JSON)
  if (env.MOOR_DESKTOP_VARIANT !== 'bundled') throw new Error('Channel builds support only bundled packaging')
  if (env.MOOR_BUILD_COMMIT || env.MOOR_PAYLOAD_TAG) throw new Error('Channel request conflicts with commit or tag identity')
  // The bundled toolchain already supplies Python. Reuse the authoritative
  // validator rather than maintaining a third protocol decoder for packaging.
  const validator = [
    'import sys',
    'sys.path.insert(0, sys.argv[1])',
    'from moor_cli.release_channels import decode_json',
    'from scripts.bundles.desktop_prepare import validate_channel_request',
    'validate_channel_request(decode_json(sys.stdin.buffer.read()))'
  ].join('; ')
  execFileSync(env.MOOR_PYTHON || 'python', ['-I', '-S', '-c', validator, path.resolve(__dirname, '..')], {
    env, input: env._MOOR_CHANNEL_REQUEST_JSON, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'], timeout: 30_000
  })
  if (env.MOOR_PAYLOAD_VERSION && env.MOOR_PAYLOAD_VERSION !== value.version) throw new Error('Channel package version conflicts with prepared request')
  Object.freeze(value.identity)
  Object.freeze(value.bundleEnv)
  return Object.freeze(value)
}

module.exports = {
  channelBuildRequest
}
