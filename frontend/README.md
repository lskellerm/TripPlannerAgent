# TripPlannerAgent Frontend

Nuxt 3 frontend for the TripPlannerAgent — a conversational AI-powered Airbnb search and trip cost analysis platform.

> **Package manager**: this project uses [pnpm](https://pnpm.io) exclusively. Do not use npm, yarn, or bun.

## Prerequisites

- Node.js 20+
- pnpm (enable via Corepack: `corepack enable && corepack prepare pnpm@latest --activate`)

## Setup

Install dependencies:

```bash
pnpm install
```

## Development Server

Start the development server on `http://localhost:3000`:

```bash
pnpm dev
```

## Production

Build the application for production:

```bash
pnpm build
```

Locally preview the production build:

```bash
pnpm preview
```

## Code Quality

```bash
# Lint
pnpm lint

# Lint and auto-fix
pnpm lint:fix

# Format with Prettier
pnpm format

# Type-check
pnpm typecheck
```

## API Client Generation

After any backend endpoint or schema change, regenerate the typed API client from the FastAPI OpenAPI spec:

```bash
pnpm api:generate
```

Check out the [Nuxt deployment documentation](https://nuxt.com/docs/getting-started/deployment) for more information.
