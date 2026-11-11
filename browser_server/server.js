// Optional private worker. Public Playwright protocol; never CDP or a personal profile.
const { chromium } = require('playwright');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

async function main() {
  const port = Number(process.argv[2] ?? 9777);
  if (!Number.isInteger(port) || (port !== 0 && (port < 1024 || port > 65535))) {
    throw new Error('Choose port 0 (ephemeral) or 1024–65535');
  }
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'evident-worker-'));
  let server;
  let closing = false;
  async function close() {
    if (closing) return;
    closing = true;
    if (server) await server.close();
    fs.rmSync(home, { recursive: true, force: true });
  }
  try {
    server = await chromium.launchServer({
      headless: true, chromiumSandbox: true, host: '127.0.0.1', port,
      wsPath: '/evident-evidence',
      env: { PATH: '/usr/bin:/bin', HOME: home, TMPDIR: home, LANG: 'C.UTF-8', TZ: 'UTC' },
      args: ['--dns-prefetch-disable', '--force-webrtc-ip-handling-policy=disable_non_proxied_udp'],
    });
    process.once('SIGTERM', () => close().then(() => process.exit(0)));
    process.once('SIGINT', () => close().then(() => process.exit(0)));
    server.on('close', () => { if (!closing) close().then(() => process.exit(0)); });
    process.stdout.write(JSON.stringify({ endpoint: server.wsEndpoint() }) + '\n');
  } catch (error) {
    await close();
    throw error;
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
