# ── Base stage ──
FROM node:22-alpine AS base

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

RUN corepack enable

WORKDIR /app

# ── Development stage ──
FROM base AS development

COPY package.json pnpm-lock.yaml ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile --ignore-scripts

COPY . ./
RUN pnpm run postinstall

ENV HOST=0.0.0.0
ENV PORT=3000

EXPOSE 3000

CMD ["pnpm", "run", "dev"]

# ── Build stage ──
FROM base AS build

# Copy lockfile and package manifest first (layer cache for deps)
COPY package.json pnpm-lock.yaml ./

# Install dependencies; skip postinstall (nuxt prepare) since source isn't
# available yet — it will be run explicitly after the source is copied.
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile --ignore-scripts

# Copy the rest of the source and build the Nuxt app
COPY . ./

# Generate .nuxt/ types, path aliases, and auto-imports before building
RUN pnpm run postinstall
RUN pnpm run build

# ── Runtime stage ──
FROM base AS production

# Only the .output directory is needed — Nitro bundles everything
COPY --from=build /app/.output /app/.output

ENV HOST=0.0.0.0
ENV PORT=3000

EXPOSE 3000

CMD ["node", "/app/.output/server/index.mjs"]
