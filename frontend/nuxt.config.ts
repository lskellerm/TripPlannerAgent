// https://nuxt.com/docs/api/configuration/nuxt-config
import tailwindcss from '@tailwindcss/vite'

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  typescript: {
    strict: true,
    typeCheck: true,
  },

  app: {
    head: {
      title: 'TripPlannerAgent',
      meta: [
        { name: 'description', content: 'AI-powered Airbnb search and trip cost analysis' },
        { name: 'theme-color', content: '#0891B2' },
      ],
      link: [{ rel: 'icon', type: 'image/x-icon', href: '/favicon.ico' }],
    },
  },

  /*
   * Modules to include in the project.
   **/
  modules: ['@nuxt/eslint', '@pinia/nuxt', 'shadcn-nuxt'],

  shadcn: {
    prefix: 'ui',
    componentDir: 'app/components/ui',
  },
  components: [
    {
      path: '~/app/components',
      pathPrefix: false,
    },
  ],

  // Environment-driven runtime configuration.
  // NUXT_PUBLIC_* env vars automatically override matching keys at startup.
  runtimeConfig: {
    // Server-only — never exposed to the browser
    apiKey: '', // NUXT_API_KEY
    public: {
      apiBaseUrl: 'http://localhost:8000', // NUXT_PUBLIC_API_BASE_URL
      wsBaseUrl: 'ws://localhost:8000', // NUXT_PUBLIC_WS_BASE_URL
    },
  },

  // Global CSS file to include in the project.
  css: ['~/assets/css/main.css'],

  vite: {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    plugins: [tailwindcss() as any],
    // Helps Vite prebundle consistently (especially in Docker where caches differ)
    optimizeDeps: {
      include: ['vue', 'vue-router', 'pinia'],
    },

    // Ensure SSR bundle includes these deps instead of leaving runtime imports
    ssr: {
      noExternal: ['vue', 'vue-router', 'pinia'],
    },
  },

  nitro: {
    // Force Vue to be bundled into server chunks instead of externalized.
    // Prevents "does not provide an export named 'default'" errors caused by
    // Rollup CJS→ESM interop generating `import require$$0 from 'vue'` which
    // Node.js rejects because Vue 3's ESM entry has no default export.
    externals: {
      inline: ['vue'],
    },
  },

  ssr: true,
})
