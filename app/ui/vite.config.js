// Bundles the page (index.html, js/ with its Svelte components, style.css and the npm packages they import) into
// ../dist. Web Awesome is not bundled: its loader fetches each component from /vendor/ when the page first uses it
// (scripts/ui.sh copies it).
import { fileURLToPath } from "node:url";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [svelte()],
  build: { outDir: "../dist", emptyOutDir: true },
  resolve: {
    // dockview-core's ES build has no CSS; its UMD build injects the styles
    alias: {
      "dockview-core": fileURLToPath(new URL("node_modules/dockview-core/dist/dockview-core.js", import.meta.url)),
    },
  },
});
