import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "0.0.0.0", // bind to all interfaces so Docker can access it
    port: 3000, // ensure this matches your exposed port
    watch: {
      usePolling: true,
      interval: 100, // enables hot reload for Docker-mounted volumes
    },
  },
});
