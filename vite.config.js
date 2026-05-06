import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  logLevel: 'warn',
  plugins: [
    {
      name: 'django-reminder',
      configureServer(server) {
        server.httpServer.once('listening', () => {
          console.log('\x1b[32m%s\x1b[0m', '  ➜  Django:   http://localhost:8000/ (Use this to view the game)');
        });
      }
    }
  ],
  root: resolve('./frontend/src'),
  base: '/static/',
  server: {
    host: 'localhost',
    port: 5173,
    open: false,
    watch: {
      usePolling: true,
    },
  },
  build: {
    outDir: resolve('./frontend/dist'),
    assetsDir: '',
    manifest: true,
    emptyOutDir: true,
    rollupOptions: {
      input: {
        board: resolve('./frontend/src/js/board.js'),
        auth: resolve('./frontend/src/css/auth.css'),
      },
    },
  },
});
