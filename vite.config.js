import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import Components from "unplugin-vue-components/vite";
import Icons from "unplugin-icons/vite";
import IconsResolver from "unplugin-icons/resolver";
import mkcert from "vite-plugin-mkcert";

export default defineConfig({
  plugins: [
    vue(),
    Icons({
      compiler: "vue3",
    }),
    Components({
      resolvers: [
        IconsResolver({
          enabledCollections: ["mdi"],
        }),
      ],
    }),
    mkcert(),
  ],
  server: {
    https: true,
    port: 5174,
    hmr: {
      overlay: false,
    },
    watch: {
      usePolling: true,
      interval: 1000,
    },
    proxy: {
      "/api": "http://127.0.0.1:5050",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
