import net from 'net';
import ws from '../../frontend/node_modules/ws/index.js';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const envPath = path.resolve(__dirname, '../.env');

// Read DATABASE_URL from .env
let rawUrl = '';
if (fs.existsSync(envPath)) {
  const envContent = fs.readFileSync(envPath, 'utf8');
  const match = envContent.match(/DATABASE_URL=(.+)/);
  if (match) rawUrl = match[1].trim();
}
if (!rawUrl && process.env.DATABASE_URL) {
  rawUrl = process.env.DATABASE_URL.trim();
}

if (!rawUrl) {
  console.error('[NeonProxy] No DATABASE_URL found.');
  process.exit(1);
}

let remoteHost = '';
try {
  const dbUrl = new URL(rawUrl);
  remoteHost = dbUrl.hostname;
} catch (e) {
  console.error('[NeonProxy] Failed to parse DATABASE_URL hostname:', e.message);
  process.exit(1);
}

const wsTargetUrl = `wss://${remoteHost}/v2`;
console.log(`[NeonProxy] Initializing WebSocket tunnel to ${wsTargetUrl}...`);

const server = net.createServer((socket) => {
  const websocket = new ws(wsTargetUrl);

  websocket.on('message', (data) => {
    socket.write(Buffer.from(data));
  });

  websocket.on('close', () => {
    socket.end();
  });

  websocket.on('error', (err) => {
    socket.destroy();
  });

  let sslNegDone = false;

  socket.on('data', (chunk) => {
    // If client asks for SSL (length 8, code 80877103 = 0x04d2162f)
    if (!sslNegDone && chunk.length === 8 && chunk.readInt32BE(4) === 80877103) {
      sslNegDone = true;
      // Respond 'N' to tell client not to use inner SSL (since outer tunnel is WSS)
      socket.write(Buffer.from('N'));
      return;
    }

    if (websocket.readyState === ws.OPEN) {
      websocket.send(chunk);
    } else {
      websocket.once('open', () => {
        websocket.send(chunk);
      });
    }
  });

  socket.on('close', () => {
    websocket.close();
  });

  socket.on('error', (err) => {
    websocket.close();
  });
});

const PORT = process.env.NEON_PROXY_PORT ? parseInt(process.env.NEON_PROXY_PORT, 10) : 5432;
server.listen(PORT, '127.0.0.1', () => {
  console.log(`[NeonProxy] Listening on 127.0.0.1:${PORT} -> Neon WSS :443`);
});
