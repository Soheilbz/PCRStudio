import { reactRouter } from '@react-router/dev/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';
// The SPA shell is rendered through Vite's local preview server during build.
// Use one loopback family for both listener and request inside containers.
export default defineConfig({
  plugins: [tailwindcss(), reactRouter()],
  preview: { host: '127.0.0.1' },
});
