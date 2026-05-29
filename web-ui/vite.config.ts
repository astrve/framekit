import tailwindcss from "@tailwindcss/vite";
import path from "node:path";
import react from '@vitejs/plugin-react'
import { defineConfig } from "vitest/config";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            { name: "vendor-react", test: /node_modules[\\/](react|react-dom)/, priority: 30 },
            { name: "vendor-router-query", test: /node_modules[\\/]@tanstack/, priority: 25 },
            { name: "vendor-radix", test: /node_modules[\\/]@radix-ui/, priority: 20 },
            { name: "vendor-lucide", test: /node_modules[\\/]lucide-react/, priority: 15 },
            { name: "vendor", test: /node_modules/, priority: 10 },
          ],
        },
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    exclude: ["tests/e2e/**", "node_modules/**", "dist/**"],
    coverage: {
      reporter: ["text", "html"],
    },
  },
})
