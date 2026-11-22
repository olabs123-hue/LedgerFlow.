import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins:[react()],
  base: process.env.VITE_PUBLIC_BASE || '/',
  // Opt-in local same-origin browser session mode. Public showcase is static.
  server: {
    proxy: {
      '/browser': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
});
