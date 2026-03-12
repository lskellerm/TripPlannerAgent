// @ts-check
import withNuxt from './.nuxt/eslint.config.mjs'
import eslintConfigPrettier from 'eslint-config-prettier'
import eslintPluginPrettier from 'eslint-plugin-prettier/recommended'

export default withNuxt(
  eslintPluginPrettier,
  eslintConfigPrettier,
  // Global ignores — auto-generated and non-source files
  {
    ignores: [
      '**/node_modules/**',
      '**/.nuxt/**',
      '**/dist/**',
      '**/.git/**',
      '**/backend/**',
      '**/docker-compose.yml',
      '**/Dockerfile',
      '**/.gitignore',
      '**/.prettierignore',
      'pnpm-lock.yaml',
      'api/**',
    ],
  },
  // Default rules for all source files
  {
    files: ['**/*.{ts,vue,js}'],
    rules: {
      'no-console': 'warn',
    },
  },
  // shadcn-vue components use single-word names and optional props without defaults by convention
  {
    files: ['app/components/ui/**/*.vue'],
    rules: {
      'vue/multi-word-component-names': 'off',
      'vue/require-default-prop': 'off',
    },
  },
)
